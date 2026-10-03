from datetime import date, timedelta

import pytest
from django.utils import timezone

from core.models import AuditEvent, User
from core.tenancy import require_tenant_id
from solver.types import FEASIBLE, INFEASIBLE, UNKNOWN, Grid, Placement, Result
from timetable import bridge, services
from timetable.models import (
    Assignment,
    Requirement,
    RequirementResource,
    Resource,
    Subject,
    Version,
)

GRID = {
    "days": ["Mon", "Tue"],
    "periods": [["09:00", "09:55"], ["10:00", "10:55"], ["11:00", "11:55"]],
    "breaks_after": [1],
}
SHIFTED_GRID = {
    "days": ["Mon", "Tue", "Wed"],
    "periods": [["09:30", "10:30"], ["10:30", "11:30"], ["14:00", "15:00"]],
    "breaks_after": [],
}
TODAY = date(2026, 10, 2)
START = date(2026, 8, 1)
END = date(2026, 12, 31)


def make_timetable(name, actor, grid=GRID, department=None, start=START, end=END):
    return services.create_timetable(
        name=name, department=department, grid=grid, start_date=start, end_date=end, actor=actor
    )


def teacher(code, user=None):
    return Resource.objects.create(kind=Resource.Kind.TEACHER, code=code, max_load=20, user=user)


def room(code, capacity=60):
    return Resource.objects.create(kind=Resource.Kind.ROOM, code=code, capacity=capacity)


def section(code, strength=50):
    return Resource.objects.create(kind=Resource.Kind.SECTION, code=code, capacity=strength)


def subject(code, length=1):
    return Subject.objects.create(code=code, name=code, length=length)


def add_requirement(
    version, subj, teachers, attendees, sessions=1, length=1, rooms_needed=1, fixed_rooms=()
):
    requirement = Requirement.objects.create(
        version=version,
        subject=subj,
        sessions=sessions,
        length=length,
        rooms_needed=rooms_needed,
    )
    for resource in teachers:
        RequirementResource.objects.create(
            requirement=requirement, resource=resource, role=RequirementResource.Role.TEACHER
        )
    for resource in attendees:
        RequirementResource.objects.create(
            requirement=requirement, resource=resource, role=RequirementResource.Role.ATTENDEE
        )
    for resource in fixed_rooms:
        RequirementResource.objects.create(
            requirement=requirement, resource=resource, role=RequirementResource.Role.FIXED_ROOM
        )
    return requirement


def occupy(version, requirement, session, day, start, rooms, serves=None):
    tenant_id = require_tenant_id()
    participants = list(requirement.participants.select_related("resource"))
    rows = []
    for period in range(start, start + requirement.length):
        for participant in participants:
            if participant.role == RequirementResource.Role.FIXED_ROOM:
                continue
            rows.append(
                Assignment(
                    tenant_id=tenant_id,
                    version=version,
                    requirement=requirement,
                    session=session,
                    resource=participant.resource,
                    day=day,
                    period=period,
                )
            )
        for index, item in enumerate(rooms):
            rows.append(
                Assignment(
                    tenant_id=tenant_id,
                    version=version,
                    requirement=requirement,
                    session=session,
                    resource=item,
                    day=day,
                    period=period,
                    serves=serves[index] if serves else None,
                )
            )
    Assignment.objects.bulk_create(rows)
    return rows


def no_violations(instance, placements):
    return []


def blocked_violations(instance, placements):
    violations = []
    requirements = instance.requirement_map
    for placement in placements:
        requirement = requirements[placement.requirement]
        occupants = (*requirement.teachers, *requirement.attendees, *placement.rooms)
        for period in range(placement.start, placement.start + requirement.length):
            for resource in occupants:
                if (resource, placement.day, period) in instance.blocked:
                    violations.append(f"blocked {resource} at {placement.day}/{period}")
    return violations


def clean_precheck(instance):
    return []


@pytest.fixture
def world(scope, admin_user, monkeypatch):
    monkeypatch.setattr(bridge, "validate_placements", no_violations)
    monkeypatch.setattr(bridge, "precheck_instance", clean_precheck)
    timetable = make_timetable("CSE Odd", admin_user)
    draft = services.create_draft(timetable, actor=admin_user)
    data = {
        "actor": admin_user,
        "timetable": timetable,
        "draft": draft,
        "t1": teacher("T1"),
        "t2": teacher("T2"),
        "r1": room("R1"),
        "r2": room("R2"),
        "s1": section("S1"),
        "s2": section("S2"),
        "math": subject("MATH"),
        "phys": subject("PHYS"),
    }
    data["req_math"] = add_requirement(draft, data["math"], [data["t1"]], [data["s1"]], sessions=2)
    data["req_phys"] = add_requirement(
        draft, data["phys"], [data["t2"]], [data["s1"], data["s2"]], rooms_needed=2
    )
    return data


def solved_result(world):
    return Result(
        status=FEASIBLE,
        placements=(
            Placement(str(world["req_math"].pk), 0, 0, 0, (str(world["r1"].pk),)),
            Placement(str(world["req_math"].pk), 1, 1, 2, (str(world["r1"].pk),)),
            Placement(
                str(world["req_phys"].pk), 0, 0, 1, (str(world["r1"].pk), str(world["r2"].pk))
            ),
        ),
        stats={"wall_seconds": 1.5},
    )


def solved_draft(world):
    draft = world["draft"]
    draft.status = Version.Status.SOLVING
    draft.save(update_fields=["status"])
    return services.apply_result(draft, solved_result(world))


def test_create_timetable_rejects_bad_grids(scope, admin_user):
    with pytest.raises(services.ServiceError):
        make_timetable("A", admin_user, grid={"days": [], "periods": [["09:00", "10:00"]]})
    with pytest.raises(services.ServiceError):
        make_timetable("B", admin_user, grid={"days": ["Mon"], "periods": []})
    with pytest.raises(services.ServiceError):
        make_timetable(
            "C",
            admin_user,
            grid={"days": ["Mon"], "periods": [["10:00", "11:00"], ["09:00", "09:55"]]},
        )
    with pytest.raises(services.ServiceError):
        make_timetable("D", admin_user, grid={"days": ["Mon"], "periods": [["10:00", "09:00"]]})
    with pytest.raises(services.ServiceError):
        make_timetable("E", admin_user, grid={"days": ["Mon"], "periods": [["x", "y"]]})
    with pytest.raises(services.ServiceError):
        make_timetable("F", admin_user, start=END, end=START)


def test_create_timetable_persists_and_audits(scope, admin_user, department):
    timetable = make_timetable("CSE", admin_user, department=department)
    assert timetable.grid == Grid.from_json(GRID).to_json()
    assert timetable.department == department
    event = AuditEvent.objects.get(action="timetable.created")
    assert event.object_id == timetable.pk
    assert event.actor == admin_user
    with pytest.raises(services.ServiceError):
        make_timetable("CSE", admin_user)


def test_create_draft_numbers_and_copies(world):
    draft = world["draft"]
    assert draft.number == 1
    assert draft.status == Version.Status.DRAFT
    assert draft.grid == world["timetable"].grid
    assert draft.created_by == world["actor"]
    child = services.create_draft(
        world["timetable"], parent=draft, reason="tweak", actor=world["actor"]
    )
    assert child.number == 2
    assert child.parent == draft
    assert child.reason == "tweak"
    copied = list(child.requirements.order_by("subject__code"))
    assert [r.subject.code for r in copied] == ["MATH", "PHYS"]
    assert {r.pk for r in copied}.isdisjoint({world["req_math"].pk, world["req_phys"].pk})
    assert copied[0].sessions == 2
    assert copied[1].rooms_needed == 2
    roles = sorted(copied[1].participants.values_list("role", flat=True))
    assert roles == ["attendee", "attendee", "teacher"]
    assert AuditEvent.objects.filter(action="version.created").count() == 2


def test_create_draft_rejects_foreign_parent(world):
    other = make_timetable("Other", world["actor"])
    with pytest.raises(services.ServiceError):
        services.create_draft(other, parent=world["draft"], actor=world["actor"])


def test_copy_requirements_needs_a_draft_target(world):
    target = services.create_draft(world["timetable"], actor=world["actor"])
    target.status = Version.Status.SOLVING
    target.save(update_fields=["status"])
    with pytest.raises(services.NotDraft):
        services.copy_requirements(world["draft"], target)


def publish_as(version, effective_from):
    Version.objects.filter(pk=version.pk).update(
        status=Version.Status.PUBLISHED, effective_from=effective_from, published_at=timezone.now()
    )
    version.refresh_from_db()
    return version


def test_active_version_picks_latest_effective(world):
    timetable = world["timetable"]
    assert services.active_version(timetable, TODAY) is None
    first = publish_as(world["draft"], date(2026, 8, 1))
    second = services.create_draft(timetable, actor=world["actor"])
    second = publish_as(second, date(2026, 10, 15))
    assert services.active_version(timetable, date(2026, 9, 1)) == first
    assert services.active_version(timetable, date(2026, 10, 15)) == second
    assert services.active_version(timetable, date(2026, 7, 1)) is None


def test_blocked_slots_maps_other_grid_by_clock_time(world):
    other = make_timetable("ECE Odd", world["actor"], grid=SHIFTED_GRID)
    other_draft = services.create_draft(other, actor=world["actor"])
    shared_teacher = world["t1"]
    req = add_requirement(other_draft, world["phys"], [shared_teacher], [world["s2"]])
    occupy(other_draft, req, 0, 0, 0, [world["r2"]])
    occupy(other_draft, req, 1, 2, 2, [world["r2"]])
    publish_as(other_draft, START)
    blocked = services.blocked_slots(world["draft"])
    teacher_id = str(shared_teacher.pk)
    assert (teacher_id, 0, 0) in blocked
    assert (teacher_id, 0, 1) in blocked
    assert (teacher_id, 0, 2) not in blocked
    assert (str(world["r2"].pk), 0, 0) in blocked
    assert (str(world["s2"].pk), 0, 1) in blocked
    assert not any(day == 2 for _, day, _ in blocked)
    assert not any(day == 1 for _, day, _ in blocked)


def test_blocked_slots_ignores_archived_and_non_overlapping(world):
    other = make_timetable("Spring", world["actor"], start=date(2027, 1, 1), end=date(2027, 5, 1))
    other_draft = services.create_draft(other, actor=world["actor"])
    req = add_requirement(other_draft, world["phys"], [world["t1"]], [world["s2"]])
    occupy(other_draft, req, 0, 0, 0, [world["r2"]])
    publish_as(other_draft, date(2027, 1, 1))
    assert services.blocked_slots(world["draft"]) == frozenset()


def test_build_instance_groups_participants_by_role(world):
    world["t1"].unavailable = [[0, 0], [9, 9]]
    world["t1"].save()
    fixed = add_requirement(
        world["draft"],
        subject("LAB", 2),
        [world["t2"]],
        [world["s2"]],
        length=2,
        fixed_rooms=[world["r2"]],
    )
    fixed.fixed_slots = [[1, 0]]
    fixed.room_tag = "lab"
    fixed.save()
    instance = services.build_instance(world["draft"])
    assert instance.grid == Grid.from_json(GRID)
    assert {r.kind for r in instance.resources} == {"teacher", "room", "section"}
    t1 = instance.resource(str(world["t1"].pk))
    assert t1.unavailable == frozenset({(0, 0)})
    assert t1.max_load == 20
    assert instance.resource(str(world["s1"].pk)).capacity == 50
    by_id = instance.requirement_map
    phys = by_id[str(world["req_phys"].pk)]
    assert phys.teachers == (str(world["t2"].pk),)
    assert set(phys.attendees) == {str(world["s1"].pk), str(world["s2"].pk)}
    assert phys.rooms_needed == 2
    lab = by_id[str(fixed.pk)]
    assert lab.fixed_rooms == (str(world["r2"].pk),)
    assert lab.fixed_slots == ((1, 0),)
    assert lab.room_tag == "lab"
    assert lab.length == 2
    assert instance.seed == world["draft"].number
    assert instance.max_seconds == 120
    assert instance.hints == ()
    assert instance.blocked == frozenset()


def test_build_instance_caps_max_seconds_from_tenant_settings(world, tenant, settings):
    tenant.settings = {"solver": {"max_seconds": 5000}}
    tenant.save()
    assert services.build_instance(world["draft"]).max_seconds == settings.SOLVER_MAX_SECONDS
    tenant.settings = {"solver": {"max_seconds": 30}}
    tenant.save()
    assert services.build_instance(world["draft"]).max_seconds == 30


def test_build_instance_hints_only_for_unchanged_requirements(world):
    solved_draft(world)
    child = services.create_draft(world["timetable"], parent=world["draft"], actor=world["actor"])
    copies = {r.subject.code: r for r in child.requirements.select_related("subject")}
    RequirementResource.objects.filter(
        requirement=copies["PHYS"], role=RequirementResource.Role.TEACHER
    ).update(resource=world["t1"])
    instance = services.build_instance(child)
    hinted = {hint.requirement for hint in instance.hints}
    assert hinted == {str(copies["MATH"].pk)}
    assert sorted((h.session, h.day, h.start, h.rooms) for h in instance.hints) == [
        (0, 0, 0, (str(world["r1"].pk),)),
        (1, 1, 2, (str(world["r1"].pk),)),
    ]


def test_start_solve_requires_requirements(world):
    empty = services.create_draft(world["timetable"], actor=world["actor"])
    with pytest.raises(services.ServiceError):
        services.start_solve(empty, world["actor"])


def test_start_solve_precheck_failure_marks_failed(world, monkeypatch):
    monkeypatch.setattr(bridge, "precheck_instance", lambda instance: ["teacher T1 is overloaded"])
    version = services.start_solve(world["draft"], world["actor"])
    assert version.status == Version.Status.FAILED
    assert version.solver_stats["reasons"] == ["teacher T1 is overloaded"]
    assert "started_at" in version.solver_stats
    assert AuditEvent.objects.filter(action="version.failed", object_id=version.pk).exists()
    assert not AuditEvent.objects.filter(action="version.solve_started").exists()


def test_start_solve_queues_job(world):
    from procrastinate.contrib.django.models import ProcrastinateJob

    version = services.start_solve(world["draft"], world["actor"])
    assert version.status == Version.Status.SOLVING
    job = ProcrastinateJob.objects.get(task_name="timetable.solve_version")
    assert job.args == {"version_id": str(version.pk), "tenant_id": str(require_tenant_id())}
    assert job.lock == f"solve:{require_tenant_id()}"
    assert job.queueing_lock is None
    assert AuditEvent.objects.filter(action="version.solve_started", object_id=version.pk).exists()
    with pytest.raises(services.NotDraft):
        services.start_solve(version, world["actor"])


def test_start_solve_rate_limit(world, settings):
    settings.SOLVES_PER_TENANT_PER_HOUR = 1
    services.start_solve(world["draft"], world["actor"])
    other = make_timetable("Second", world["actor"])
    draft = services.create_draft(other, actor=world["actor"])
    add_requirement(draft, world["math"], [world["t2"]], [world["s2"]])
    with pytest.raises(services.ServiceError, match="limit"):
        services.start_solve(draft, world["actor"])


def test_apply_result_writes_occupancy_rows(world):
    version = solved_draft(world)
    assert version.status == Version.Status.DRAFT
    rows = Assignment.objects.filter(version=version)
    assert rows.count() == 2 * (1 + 1 + 1) + 1 * (1 + 2 + 2)
    phys_rooms = rows.filter(requirement=world["req_phys"], resource__kind="room").order_by(
        "resource__code"
    )
    assert [r.serves for r in phys_rooms] == [world["s1"], world["s2"]]
    math_room = rows.get(requirement=world["req_math"], session=0, resource=world["r1"])
    assert math_room.serves is None
    assert not rows.filter(is_live=True).exists()
    assert version.solver_stats["wall_seconds"] == 1.5
    assert "finished_at" in version.solver_stats
    assert AuditEvent.objects.filter(action="version.solved", object_id=version.pk).exists()


def test_apply_result_rejects_validator_disagreement(world, monkeypatch):
    monkeypatch.setattr(bridge, "validate_placements", lambda i, p: ["T1 double booked"])
    version = services.apply_result(world["draft"], solved_result(world))
    assert version.status == Version.Status.FAILED
    assert version.solver_stats["reasons"] == ["solver and validator disagree", "T1 double booked"]
    assert not Assignment.objects.filter(version=version).exists()


def test_apply_result_infeasible_stores_reasons_and_unplaced(world, monkeypatch):
    explained = Result(
        status=INFEASIBLE,
        unplaced=((str(world["req_phys"].pk), 0),),
        reasons=("PHYS needs two rooms but only one fits",),
    )
    monkeypatch.setattr(bridge, "explain_instance", lambda instance: explained)
    version = services.apply_result(
        world["draft"], Result(status=INFEASIBLE, reasons=("no feasible placement",))
    )
    assert version.status == Version.Status.FAILED
    assert version.solver_stats["reasons"] == [
        "no feasible placement",
        "PHYS needs two rooms but only one fits",
    ]
    label = version.solver_stats["unplaced"][0][0]
    assert str(world["req_phys"].pk) not in label
    assert label.startswith(f"{world['req_phys'].subject.code} for ")
    assert version.solver_stats["unplaced"][0][1] == 0
    assert AuditEvent.objects.filter(action="version.failed", object_id=version.pk).exists()


def test_apply_result_unknown_does_not_explain(world, monkeypatch):
    def boom(instance):
        raise AssertionError("explain must not run")

    monkeypatch.setattr(bridge, "explain_instance", boom)
    version = services.apply_result(
        world["draft"], Result(status=UNKNOWN, reasons=("solver timed out",))
    )
    assert version.status == Version.Status.FAILED
    assert version.solver_stats["reasons"] == ["solver timed out"]


def test_reopen_clears_rows_and_returns_to_draft(world):
    version = solved_draft(world)
    version = services.apply_result(version, Result(status=UNKNOWN, reasons=("x",)))
    assert version.status == Version.Status.FAILED
    version = services.reopen(version, world["actor"])
    assert version.status == Version.Status.DRAFT
    assert not Assignment.objects.filter(version=version).exists()
    assert AuditEvent.objects.filter(action="version.reopened").exists()
    published = publish_as(services.create_draft(world["timetable"], actor=world["actor"]), TODAY)
    with pytest.raises(services.NotDraft):
        services.reopen(published, world["actor"])


def test_reset_stale_solving(world, settings):
    version = services.start_solve(world["draft"], world["actor"])
    now = timezone.now()
    assert services.reset_stale_solving(now) == []
    late = now + timedelta(seconds=120) + settings.STALE_SOLVE_GRACE + timedelta(seconds=1)
    reset = services.reset_stale_solving(late)
    assert [v.pk for v in reset] == [version.pk]
    version.refresh_from_db()
    assert version.status == Version.Status.FAILED
    assert version.solver_stats["reasons"] == ["worker lost"]
    event = AuditEvent.objects.get(action="version.failed", object_id=version.pk)
    assert event.actor is None


def test_compare_shape_and_changes(world):
    first = solved_draft(world)
    child = services.create_draft(world["timetable"], parent=first, actor=world["actor"])
    copies = {r.subject.code: r for r in child.requirements.select_related("subject")}
    occupy(child, copies["MATH"], 0, 0, 0, [world["r2"]])
    occupy(child, copies["MATH"], 1, 1, 2, [world["r2"]])
    occupy(
        child,
        copies["PHYS"],
        0,
        1,
        0,
        [world["r1"], world["r2"]],
        serves=[world["s1"], world["s2"]],
    )
    diff = services.compare(first, child)
    assert set(diff) == {"days", "periods", "sections", "changes"}
    assert diff["days"] == ["Mon", "Tue"]
    assert [s["resource"] for s in diff["sections"]] == ["S1", "S2"]
    s1 = diff["sections"][0]
    assert len(s1["grid_a"]) == 2 and all(len(row) == 3 for row in s1["grid_a"])
    assert s1["grid_a"][0][0] == {"subject": "MATH", "teachers": ["T1"], "rooms": ["R1"]}
    assert s1["grid_b"][0][0] == {"subject": "MATH", "teachers": ["T1"], "rooms": ["R2"]}
    assert s1["grid_a"][0][1] == {"subject": "PHYS", "teachers": ["T2"], "rooms": ["R1"]}
    assert s1["grid_b"][0][1] is None
    assert s1["grid_b"][1][0] == {"subject": "PHYS", "teachers": ["T2"], "rooms": ["R1"]}
    assert diff["sections"][1]["grid_b"][1][0]["rooms"] == ["R2"]
    changes = {(c["section"], c["day"], c["time"]) for c in diff["changes"]}
    assert ("S1", "Mon", "09:00-09:55") in changes
    assert ("S1", "Mon", "10:00-10:55") in changes
    assert ("S1", "Tue", "09:00-09:55") in changes
    assert ("S1", "Tue", "11:00-11:55") in changes
    room_change = next(
        c for c in diff["changes"] if c["day"] == "Mon" and c["time"] == "09:00-09:55"
    )
    assert room_change["from"]["rooms"] == ["R1"] and room_change["to"]["rooms"] == ["R2"]
    assert room_change["subject"] == "MATH"


def test_compare_aligns_different_grids_by_clock(world):
    first = solved_draft(world)
    other = make_timetable("Shifted", world["actor"], grid=SHIFTED_GRID)
    other_draft = services.create_draft(other, actor=world["actor"])
    req = add_requirement(other_draft, world["math"], [world["t1"]], [world["s1"]])
    occupy(other_draft, req, 0, 0, 0, [world["r1"]])
    diff = services.compare(first, other_draft)
    s1 = next(s for s in diff["sections"] if s["resource"] == "S1")
    assert s1["grid_b"][0][0] == {"subject": "MATH", "teachers": ["T1"], "rooms": ["R1"]}
    assert s1["grid_b"][0][1] == {"subject": "MATH", "teachers": ["T1"], "rooms": ["R1"]}
    assert s1["grid_b"][0][2] is None


def test_actor_user_ignores_anonymous():
    from django.contrib.auth.models import AnonymousUser

    assert services.actor_user(AnonymousUser()) is None
    assert services.actor_user(None) is None
    user = User(email="x@y.z", name="X")
    assert services.actor_user(user) is user
