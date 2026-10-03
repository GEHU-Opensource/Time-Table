import re
import uuid
from datetime import datetime, timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import IntegrityError, connection, transaction
from django.db.models import DateTimeField, Max, Prefetch
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast
from django.template.loader import render_to_string
from django.utils import timezone

from core.audit import audit
from core.models import Tenant
from core.tenancy import require_tenant_id, tenant_scope
from solver.types import INFEASIBLE, Grid, Instance, Placement, to_minutes
from solver.types import Requirement as SolverRequirement
from solver.types import Resource as SolverResource
from timetable import bridge, sandbox
from timetable.models import (
    Assignment,
    Requirement,
    RequirementResource,
    Resource,
    Timetable,
    Version,
)

DRAFT = Version.Status.DRAFT
SOLVING = Version.Status.SOLVING
FAILED = Version.Status.FAILED
PUBLISHED = Version.Status.PUBLISHED

TEACHER = RequirementResource.Role.TEACHER
ATTENDEE = RequirementResource.Role.ATTENDEE
FIXED_ROOM = RequirementResource.Role.FIXED_ROOM

WORKER_LOST = "worker lost"
VALIDATOR_DISAGREES = "solver and validator disagree"


class ServiceError(Exception):
    pass


class NotDraft(ServiceError):
    pass


class Conflict(ServiceError):
    def __init__(self, violations):
        super().__init__("; ".join(violations))
        self.violations = list(violations)


def parse_grid(grid):
    try:
        parsed = Grid.from_json(grid)
        minutes = [(to_minutes(start), to_minutes(end)) for start, end in parsed.periods]
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ServiceError("grid is malformed") from exc
    if not parsed.days:
        raise ServiceError("grid needs at least one day")
    if len(set(parsed.days)) != len(parsed.days):
        raise ServiceError("grid day labels must be unique")
    if not parsed.periods:
        raise ServiceError("grid needs at least one period")
    previous_end = -1
    for start, end in minutes:
        if start >= end or start < previous_end:
            raise ServiceError("grid periods must be in clock order")
        previous_end = end
    if any(index not in range(len(parsed.periods)) for index in parsed.breaks_after):
        raise ServiceError("grid breaks must follow an existing period")
    return parsed


def actor_user(actor):
    if actor is not None and getattr(actor, "is_authenticated", False):
        return actor
    return None


def tenant_settings():
    return Tenant.objects.get(pk=require_tenant_id()).settings or {}


def solver_max_seconds():
    configured = (
        tenant_settings().get("solver", {}).get("max_seconds", settings.SOLVER_DEFAULT_SECONDS)
    )
    return min(float(configured), float(settings.SOLVER_MAX_SECONDS))


def create_timetable(*, name, department, grid, start_date, end_date, actor):
    parsed = parse_grid(grid)
    if start_date > end_date:
        raise ServiceError("start date is after end date")
    try:
        with transaction.atomic():
            timetable = Timetable.objects.create(
                name=name,
                department=department,
                grid=parsed.to_json(),
                start_date=start_date,
                end_date=end_date,
            )
            audit(
                actor,
                "timetable.created",
                timetable,
                after={
                    "department": str(department.pk) if department is not None else None,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days": len(parsed.days),
                    "periods": len(parsed.periods),
                },
            )
    except IntegrityError as exc:
        raise ServiceError("a timetable with this name already exists") from exc
    return timetable


def create_draft(timetable, *, parent=None, reason="", actor):
    if parent is not None and parent.timetable_id != timetable.pk:
        raise ServiceError("parent version belongs to another timetable")
    with transaction.atomic():
        Timetable.objects.select_for_update().get(pk=timetable.pk)
        highest = Version.objects.filter(timetable=timetable).aggregate(Max("number"))[
            "number__max"
        ]
        draft = Version.objects.create(
            timetable=timetable,
            number=(highest or 0) + 1,
            parent=parent,
            status=DRAFT,
            grid=parent.grid if parent is not None else timetable.grid,
            reason=reason,
            created_by=actor_user(actor),
        )
        if parent is not None:
            copy_requirements(parent, draft)
        audit(
            actor,
            "version.created",
            draft,
            after={"number": draft.number, "parent": str(parent.pk) if parent else None},
        )
    return draft


def copy_requirements(source, target):
    if target.status != DRAFT:
        raise NotDraft("requirements can only be copied into a draft")
    tenant_id = require_tenant_id()
    originals = list(source.requirements.prefetch_related("participants"))
    copies = [
        Requirement(
            tenant_id=tenant_id,
            version=target,
            subject_id=original.subject_id,
            sessions=original.sessions,
            length=original.length,
            room_tag=original.room_tag,
            rooms_needed=original.rooms_needed,
            fixed_slots=list(original.fixed_slots),
        )
        for original in originals
    ]
    Requirement.objects.bulk_create(copies)
    RequirementResource.objects.bulk_create(
        [
            RequirementResource(
                tenant_id=tenant_id,
                requirement=copy,
                resource_id=participant.resource_id,
                role=participant.role,
            )
            for original, copy in zip(originals, copies, strict=True)
            for participant in original.participants.all()
        ]
    )
    return {
        str(original.pk): str(copy.pk) for original, copy in zip(originals, copies, strict=True)
    }


def active_version(timetable, on):
    return (
        Version.objects.filter(timetable=timetable, status=PUBLISHED, effective_from__lte=on)
        .order_by("-effective_from")
        .first()
    )


def slot_mapping(source, target):
    day_index = {label: index for index, label in enumerate(target.days)}
    mapping = {}
    for day, label in enumerate(source.days):
        if label not in day_index:
            continue
        for period in range(len(source.periods)):
            start, end = source.minutes(period)
            mapping[(day, period)] = tuple(
                (day_index[label], index) for index in target.overlapping(start, end)
            )
    return mapping


def version_range(version):
    timetable = version.timetable
    return version.effective_from or timetable.start_date, timetable.end_date


def overlapping_published_versions(timetable, range_start, range_end):
    found = {}
    active = active_version(timetable, range_start)
    if active is not None:
        found[active.pk] = active
    future = Version.objects.filter(
        timetable=timetable,
        status=PUBLISHED,
        effective_from__gt=range_start,
        effective_from__lte=range_end,
    )
    for version in future:
        found[version.pk] = version
    return list(found.values())


def blocked_slots(version):
    grid = Grid.from_json(version.grid)
    range_start, range_end = version_range(version)
    blocked = set()
    others = (
        Timetable.objects.filter(archived=False)
        .exclude(pk=version.timetable_id)
        .filter(start_date__lte=range_end, end_date__gte=range_start)
    )
    for other in others:
        for published in overlapping_published_versions(other, range_start, range_end):
            mapping = slot_mapping(Grid.from_json(published.grid), grid)
            rows = Assignment.objects.filter(version=published).values_list(
                "resource_id", "day", "period"
            )
            for resource_id, day, period in rows:
                for mapped_day, mapped_period in mapping.get((day, period), ()):
                    blocked.add((str(resource_id), mapped_day, mapped_period))
    return frozenset(blocked)


def slot_pairs(values, grid):
    pairs = set()
    for item in values or []:
        day, period = int(item[0]), int(item[1])
        if 0 <= day < len(grid.days) and 0 <= period < len(grid.periods):
            pairs.add((day, period))
    return frozenset(pairs)


def solver_resources(grid):
    return tuple(
        SolverResource(
            id=str(resource.pk),
            kind=str(resource.kind),
            capacity=resource.capacity,
            tags=frozenset(resource.tags),
            max_load=resource.max_load,
            unavailable=slot_pairs(resource.unavailable, grid),
            preferred=slot_pairs(resource.preferred, grid),
            parent=str(resource.parent_id) if resource.parent_id else None,
        )
        for resource in Resource.objects.filter(active=True)
    )


def participants_prefetch():
    return Prefetch(
        "participants",
        queryset=RequirementResource.objects.select_related("resource").order_by(
            "resource__kind", "resource__code"
        ),
    )


def requirements_with_participants(version):
    return list(
        Requirement.objects.filter(version=version)
        .select_related("subject")
        .prefetch_related(participants_prefetch())
    )


def ids_by_role(requirement, role):
    return tuple(
        str(participant.resource_id)
        for participant in requirement.participants.all()
        if participant.role == role
    )


def requirement_key(requirement):
    return (
        str(requirement.subject_id),
        tuple(sorted(str(p.resource_id) for p in requirement.participants.all())),
        requirement.sessions,
        requirement.length,
    )


def attendee_positions(requirements):
    return {
        str(requirement.pk): {
            attendee: index for index, attendee in enumerate(ids_by_role(requirement, ATTENDEE))
        }
        for requirement in requirements
    }


def room_ids():
    return {
        str(pk)
        for pk in Resource.objects.filter(kind=Resource.Kind.ROOM).values_list("pk", flat=True)
    }


def assignment_rows(version):
    rows = Assignment.objects.filter(version=version).values_list(
        "requirement_id", "session", "resource_id", "day", "period", "serves_id"
    )
    return [
        (
            str(requirement_id),
            session,
            str(resource_id),
            day,
            period,
            str(serves_id) if serves_id else None,
        )
        for requirement_id, session, resource_id, day, period, serves_id in rows
    ]


def version_placements(version, requirements=None):
    requirements = (
        requirements if requirements is not None else requirements_with_participants(version)
    )
    return bridge.placements_from_rows(
        assignment_rows(version), room_ids(), attendee_positions(requirements)
    )


def hints_from_parent(version, child_requirements):
    if version.parent_id is None:
        return ()
    parent_requirements = requirements_with_participants(version.parent)
    child_by_key = {}
    for requirement in child_requirements:
        child_by_key.setdefault(requirement_key(requirement), str(requirement.pk))
    matched = {}
    for requirement in parent_requirements:
        child_id = child_by_key.pop(requirement_key(requirement), None)
        if child_id is not None:
            matched[str(requirement.pk)] = child_id
    hints = []
    for placement in version_placements(version.parent, parent_requirements):
        child_id = matched.get(placement.requirement)
        if child_id is None:
            continue
        hints.append(
            Placement(
                requirement=child_id,
                session=placement.session,
                day=placement.day,
                start=placement.start,
                rooms=placement.rooms,
            )
        )
    return tuple(hints)


def solver_requirements(requirements, grid):
    return tuple(
        SolverRequirement(
            id=str(requirement.pk),
            subject=requirement.subject.code,
            length=requirement.length,
            sessions=requirement.sessions,
            teachers=ids_by_role(requirement, TEACHER),
            attendees=ids_by_role(requirement, ATTENDEE),
            rooms_needed=requirement.rooms_needed,
            room_tag=requirement.room_tag or None,
            fixed_rooms=ids_by_role(requirement, FIXED_ROOM),
            fixed_slots=tuple(sorted(slot_pairs(requirement.fixed_slots, grid))),
        )
        for requirement in requirements
    )


def build_instance(version):
    grid = Grid.from_json(version.grid)
    requirements = requirements_with_participants(version)
    return Instance(
        grid=grid,
        resources=solver_resources(grid),
        requirements=solver_requirements(requirements, grid),
        blocked=blocked_slots(version),
        hints=hints_from_parent(version, requirements),
        max_seconds=solver_max_seconds(),
        workers=settings.SOLVER_WORKERS,
        seed=version.number,
        max_model_size=settings.SOLVER_MAX_MODEL_SIZE,
    )


def locked(version):
    return Version.objects.select_for_update().select_related("timetable").get(pk=version.pk)


UUID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def labels_for(version):
    labels = {str(resource.pk): resource.code for resource in Resource.objects.all()}
    for requirement in requirements_with_participants(version):
        attendees = [
            participant.resource.code
            for participant in requirement.participants.all()
            if participant.role == ATTENDEE
        ]
        labels[str(requirement.pk)] = f"{requirement.subject.code} for {'+'.join(attendees)}"
    return labels


def humanize(text, labels):
    return UUID_PATTERN.sub(lambda match: labels.get(match.group(0), match.group(0)), str(text))


def mark_failed(version, reasons, extra=None):
    labels = labels_for(version)
    stats = {**version.solver_stats, **(extra or {})}
    stats["reasons"] = [humanize(reason, labels) for reason in reasons]
    if stats.get("unplaced"):
        stats["unplaced"] = [[humanize(item[0], labels), *item[1:]] for item in stats["unplaced"]]
    stats["finished_at"] = timezone.now().isoformat()
    version.status = FAILED
    version.solver_stats = stats
    version.save(update_fields=["status", "solver_stats"])


def recent_solve_count(since):
    started = Cast(KeyTextTransform("started_at", "solver_stats"), DateTimeField())
    return Version.objects.annotate(started=started).filter(started__gte=since).count()


def start_solve(version, actor):
    tenant_id = require_tenant_id()
    with transaction.atomic():
        version = locked(version)
        if version.status not in {DRAFT, FAILED}:
            raise NotDraft("only draft or failed versions can be solved")
        if not Requirement.objects.filter(version=version).exists():
            raise ServiceError("add at least one requirement before solving")
        if Version.objects.filter(timetable_id=version.timetable_id, status=SOLVING).exists():
            raise ServiceError("another version of this timetable is already solving")
        since = timezone.now() - timedelta(hours=1)
        if recent_solve_count(since) >= settings.SOLVES_PER_TENANT_PER_HOUR:
            raise ServiceError("solve limit reached for this hour, try again later")
        started_at = timezone.now().isoformat()
        instance = build_instance(version)
        problems = list(bridge.precheck_instance(instance))
        if problems:
            mark_failed(version, problems, {"started_at": started_at})
            audit(
                actor, "version.failed", version, after={"reasons": problems, "stage": "precheck"}
            )
            return version
        version.status = SOLVING
        version.solver_stats = {"started_at": started_at, "max_seconds": instance.max_seconds}
        version.save(update_fields=["status", "solver_stats"])
        from timetable import tasks

        tasks.solve_version.configure(lock=f"solve:{tenant_id}").defer(
            version_id=str(version.pk), tenant_id=str(tenant_id)
        )
        audit(actor, "version.solve_started", version, after={"started_at": started_at})
    return version


def run_solve(version_id, tenant_id):
    tenant_id = uuid.UUID(str(tenant_id))
    with tenant_scope(tenant_id):
        version = Version.objects.select_for_update().filter(pk=version_id).first()
        if version is None or version.status != SOLVING:
            return None
        instance = build_instance(version)
    result = sandbox.run(instance)
    with tenant_scope(tenant_id):
        version = Version.objects.select_for_update().filter(pk=version_id).first()
        if version is None or version.status != SOLVING:
            return None
        return apply_result(version, result, instance=instance)


def write_occupancy(version, instance, placements):
    tenant_id = require_tenant_id()
    Assignment.objects.filter(version=version).delete()
    Assignment.objects.bulk_create(
        [
            Assignment(
                tenant_id=tenant_id,
                version=version,
                requirement_id=requirement_id,
                session=session,
                resource_id=resource_id,
                day=day,
                period=period,
                serves_id=serves_id,
                is_live=False,
            )
            for requirement_id, session, resource_id, day, period, serves_id in (
                bridge.occupancy_rows(instance, placements)
            )
        ]
    )


def apply_result(version, result, instance=None):
    instance = instance if instance is not None else build_instance(version)
    if result.solved:
        violations = list(bridge.validate_placements(instance, result.placements))
        if violations:
            mark_failed(version, [VALIDATOR_DISAGREES, *violations], result.stats)
            audit(
                None, "version.failed", version, after={"reasons": version.solver_stats["reasons"]}
            )
            return version
        write_occupancy(version, instance, result.placements)
        version.status = DRAFT
        version.solver_stats = {
            **version.solver_stats,
            **result.stats,
            "status": result.status,
            "finished_at": timezone.now().isoformat(),
        }
        version.save(update_fields=["status", "solver_stats"])
        audit(
            None,
            "version.solved",
            version,
            after={"status": result.status, "placements": len(result.placements)},
        )
        return version
    reasons = list(result.reasons)
    extra = {**result.stats, "status": result.status}
    if result.unplaced:
        extra["unplaced"] = [list(item) for item in result.unplaced]
    if result.status == INFEASIBLE:
        explanation = bridge.explain_instance(instance)
        extra["unplaced"] = [list(item) for item in explanation.unplaced]
        reasons.extend(reason for reason in explanation.reasons if reason not in reasons)
    mark_failed(version, reasons, extra)
    audit(None, "version.failed", version, after={"status": result.status, "reasons": reasons})
    return version


def reopen(version, actor):
    with transaction.atomic():
        version = locked(version)
        if version.status not in {DRAFT, FAILED}:
            raise NotDraft("only draft or failed versions can be reopened")
        Assignment.objects.filter(version=version).delete()
        version.status = DRAFT
        version.save(update_fields=["status"])
        audit(actor, "version.reopened", version)
    return version


def tenant_lock():
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [str(require_tenant_id())])


def activate(timetable, target):
    try:
        with transaction.atomic():
            Assignment.objects.filter(version__timetable=timetable, is_live=True).exclude(
                version=target
            ).update(is_live=False)
            Assignment.objects.filter(version=target).update(is_live=True)
    except IntegrityError as exc:
        raise Conflict([f"live slot clash: {exc}".splitlines()[0]]) from exc


def validate_publish_date(version, effective_from, today):
    timetable = version.timetable
    if effective_from < today:
        raise ServiceError("effective date cannot be in the past")
    if not timetable.start_date <= effective_from <= timetable.end_date:
        raise ServiceError("effective date is outside the timetable date range")
    latest = Version.objects.filter(timetable=timetable, status=PUBLISHED).aggregate(
        Max("effective_from")
    )["effective_from__max"]
    if latest is not None and effective_from <= latest:
        raise ServiceError("effective date must be after the latest published version")


def publish(version, *, effective_from, actor):
    with transaction.atomic():
        tenant_lock()
        version = locked(version)
        if version.status != DRAFT:
            raise NotDraft("only draft versions can be published")
        if not Assignment.objects.filter(version=version).exists():
            raise ServiceError("nothing to publish: solve the version first")
        today = timezone.localdate()
        validate_publish_date(version, effective_from, today)
        version.effective_from = effective_from
        instance = build_instance(version)
        placements = version_placements(version)
        violations = list(bridge.validate_placements(instance, placements))
        if violations:
            raise Conflict(violations)
        version.status = PUBLISHED
        version.published_at = timezone.now()
        version.save(update_fields=["status", "published_at", "effective_from"])
        if effective_from <= today:
            activate(version.timetable, version)
        audit(
            actor,
            "version.published",
            version,
            after={"effective_from": effective_from.isoformat(), "live": effective_from <= today},
        )
        messages = publication_messages(version)
        transaction.on_commit(lambda: send_messages(messages))
    return version


def clock_range(grid, start, end):
    return f"{grid.periods[start][0]}-{grid.periods[end][1]}"


def teacher_lines(version, grid):
    lines = {}
    codes = {}
    groups = {}
    rows = Assignment.objects.filter(version=version).select_related(
        "resource", "requirement__subject"
    )
    for row in rows:
        codes[str(row.resource_id)] = row.resource.code
        key = (str(row.requirement_id), row.session, row.day)
        group = groups.setdefault(
            key,
            {
                "subject": row.requirement.subject.code,
                "periods": set(),
                "teachers": set(),
                "rooms": set(),
            },
        )
        group["periods"].add(row.period)
        if row.resource.kind == Resource.Kind.TEACHER:
            group["teachers"].add(row.resource)
        elif row.resource.kind == Resource.Kind.ROOM:
            group["rooms"].add(row.resource.code)
    for (_requirement_id, _session, day), group in sorted(
        groups.items(), key=lambda item: (item[0][2], min(item[1]["periods"]))
    ):
        time = clock_range(grid, min(group["periods"]), max(group["periods"]))
        rooms = ", ".join(sorted(group["rooms"])) or "no room"
        line = f"{grid.days[day]} {time}: {group['subject']} in {rooms}"
        for teacher in group["teachers"]:
            lines.setdefault(teacher, []).append(line)
    return lines


def publication_messages(version):
    grid = Grid.from_json(version.grid)
    messages = []
    for teacher, lines in teacher_lines(version, grid).items():
        if teacher.user_id is None:
            continue
        email = teacher.user.email if teacher.user else ""
        if not email:
            continue
        body = render_to_string(
            "email/published.txt.pug",
            {
                "timetable_name": version.timetable.name,
                "version_number": version.number,
                "effective_from": version.effective_from.isoformat(),
                "lines": lines,
            },
        )
        messages.append(
            EmailMessage(
                subject=f"Timetable published: {version.timetable.name}",
                body="\n".join(line.strip() for line in body.splitlines()).strip() + "\n",
                to=[email],
            )
        )
    return messages


def send_messages(messages):
    for message in messages:
        message.send(fail_silently=True)


def flip_live(on):
    with transaction.atomic():
        tenant_lock()
        for timetable in Timetable.objects.filter(archived=False):
            target = active_version(timetable, on)
            if target is None:
                continue
            stale_others = (
                Assignment.objects.filter(version__timetable=timetable, is_live=True)
                .exclude(version=target)
                .exists()
            )
            pending = Assignment.objects.filter(version=target, is_live=False).exists()
            if not (stale_others or pending):
                continue
            try:
                activate(timetable, target)
            except Conflict as exc:
                audit(None, "version.live_clash", target, after={"reasons": exc.violations})
                continue
            audit(None, "version.went_live", target, after={"on": on.isoformat()})


def reset_stale_solving(now):
    grace = settings.STALE_SOLVE_GRACE
    reset = []
    with transaction.atomic():
        for version in Version.objects.select_for_update().filter(status=SOLVING):
            started_at = version.solver_stats.get("started_at")
            started = datetime.fromisoformat(started_at) if started_at else version.created_at
            max_seconds = float(version.solver_stats.get("max_seconds") or solver_max_seconds())
            if started + timedelta(seconds=max_seconds) + grace < now:
                mark_failed(version, [WORKER_LOST])
                audit(None, "version.failed", version, after={"reasons": [WORKER_LOST]})
                reset.append(version)
    return reset


def version_cells(version, grid, requirements):
    codes = {str(pk): code for pk, code in Resource.objects.values_list("pk", "code")}
    kinds = {str(pk): kind for pk, kind in Resource.objects.values_list("pk", "kind")}
    subjects = {str(requirement.pk): requirement.subject.code for requirement in requirements}
    groups = {}
    for requirement_id, session, resource_id, day, period, serves_id in assignment_rows(version):
        group = groups.setdefault(
            (requirement_id, session, day, period), {"teachers": [], "rooms": [], "attendees": []}
        )
        kind = kinds.get(resource_id)
        if kind == Resource.Kind.TEACHER:
            group["teachers"].append(codes[resource_id])
        elif kind == Resource.Kind.ROOM:
            group["rooms"].append((serves_id, codes[resource_id]))
        else:
            group["attendees"].append(resource_id)
    cells = {}
    for (requirement_id, _session, day, period), group in groups.items():
        for attendee in group["attendees"]:
            rooms = sorted(code for serves, code in group["rooms"] if serves in (None, attendee))
            cells[(codes[attendee], day, period)] = {
                "subject": subjects.get(requirement_id, ""),
                "teachers": sorted(group["teachers"]),
                "rooms": rooms,
            }
    return cells


def aligned_cell(cells, code, reference, other, day, period):
    label = reference.days[day]
    if label not in other.days:
        return None
    other_day = other.days.index(label)
    for other_period in other.overlapping(*reference.minutes(period)):
        cell = cells.get((code, other_day, other_period))
        if cell is not None:
            return cell
    return None


def compare(version_a, version_b):
    grid_a = Grid.from_json(version_a.grid)
    grid_b = Grid.from_json(version_b.grid)
    cells_a = version_cells(version_a, grid_a, requirements_with_participants(version_a))
    cells_b = version_cells(version_b, grid_b, requirements_with_participants(version_b))
    codes = sorted({code for code, _, _ in cells_a} | {code for code, _, _ in cells_b})
    sections, changes = [], []
    for code in codes:
        table_a, table_b = [], []
        for day in range(len(grid_a.days)):
            row_a, row_b = [], []
            for period in range(len(grid_a.periods)):
                cell_a = cells_a.get((code, day, period))
                cell_b = aligned_cell(cells_b, code, grid_a, grid_b, day, period)
                row_a.append(cell_a)
                row_b.append(cell_b)
                if cell_a != cell_b:
                    changes.append(
                        {
                            "section": code,
                            "subject": (cell_b or cell_a or {}).get("subject", ""),
                            "day": grid_a.days[day],
                            "time": clock_range(grid_a, period, period),
                            "from": cell_a,
                            "to": cell_b,
                        }
                    )
            table_a.append(row_a)
            table_b.append(row_b)
        sections.append({"resource": code, "grid_a": table_a, "grid_b": table_b})
    return {
        "days": list(grid_a.days),
        "periods": [list(period) for period in grid_a.periods],
        "sections": sections,
        "changes": changes,
    }
