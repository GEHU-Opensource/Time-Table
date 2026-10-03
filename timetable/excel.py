import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from io import BytesIO
from types import SimpleNamespace

from django.core.exceptions import PermissionDenied
from django.db import transaction
from openpyxl import Workbook, load_workbook

from core.perms import Perm, can

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000
MAX_SHEETS = 20
MAX_ERRORS = 200
MAX_CODE = 30
MAX_NAME = 120
MAX_ROOMS = 8
TITLE_LIMIT = 31
ZIP_MAGIC = b"PK\x03\x04"
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
TITLE_FORBIDDEN = re.compile(r"[\[\]:*?/\\]")

GRID, TEACHERS, ROOMS, SECTIONS, SUBJECTS, REQUIREMENTS = SHEETS = (
    "Grid",
    "Teachers",
    "Rooms",
    "Sections",
    "Subjects",
    "Requirements",
)
COLUMNS = {
    GRID: ("period", "start", "end", "break_after"),
    TEACHERS: ("code", "name", "department", "max_per_week", "unavailable", "prefers"),
    ROOMS: ("code", "capacity", "tags"),
    SECTIONS: ("code", "strength", "department", "parent"),
    SUBJECTS: ("code", "name", "length", "kind"),
    REQUIREMENTS: ("sections", "subject", "teachers", "per_week", "room_tag", "rooms", "fixed"),
}
REQUIRED = {
    GRID: ("period", "start", "end"),
    TEACHERS: ("code", "max_per_week"),
    ROOMS: ("code", "capacity"),
    SECTIONS: ("code", "strength"),
    SUBJECTS: ("code", "name"),
    REQUIREMENTS: ("sections", "subject", "teachers", "per_week"),
}
GRID_KEYS = ("days", "name", "department", "start_date", "end_date")
PERSONAL = frozenset({"phone", "mobile", "cgpa", "hostel", "address", "email", "dob"})
YES = frozenset({"yes", "y", "true", "1"})
NO = frozenset({"", "no", "n", "false", "0"})
SUBJECT_KINDS = frozenset({"", "lecture", "lab"})
TEACHER, ROOM, SECTION, BATCH = "teacher", "room", "section", "batch"
PLURAL = {TEACHER: "teachers", ROOM: "rooms", SECTION: "sections", BATCH: "batches"}
SHEET_ORDER = (SECTION, BATCH, TEACHER, ROOM)
ROLE_TEACHER, ROLE_ATTENDEE, ROLE_FIXED_ROOM = "teacher", "attendee", "fixed_room"

CLOCK = re.compile(r"^(\d{1,2}):(\d{2})(?::\d{2})?$")
INTEGER = re.compile(r"^-?\d+(?:\.0+)?$")
PERIOD_RANGE = re.compile(r"^P?(\d+)(?:\s*-\s*P?(\d+))?$", re.IGNORECASE)
FIXED_SLOT = re.compile(r"^(\S+)\s+P?(\d+)(?:\s+in\s+(\S+))?$", re.IGNORECASE)
TEACHER_SPLIT = re.compile(r"[+,]")


@dataclass
class ImportPlan:
    errors: list[str] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    grid: dict | None = None
    teachers: list[dict] = field(default_factory=list)
    rooms: list[dict] = field(default_factory=list)
    sections: list[dict] = field(default_factory=list)
    subjects: list[dict] = field(default_factory=list)
    requirements: list[dict] = field(default_factory=list)
    timetable: dict | None = None

    def error(self, message):
        if len(self.errors) < MAX_ERRORS:
            self.errors.append(message)

    def row_error(self, sheet, number, message):
        self.error(f"{sheet} row {number}: {message}")


def cell_text(value):
    return "" if value is None else str(value).strip()


def as_int(text):
    return int(float(text)) if INTEGER.match(text) else None


def as_clock(text):
    match = CLOCK.match(text)
    if not match:
        return None
    hours, minutes = int(match.group(1)), int(match.group(2))
    if hours > 23 or minutes > 59:
        return None
    return f"{hours:02d}:{minutes:02d}"


def as_date(text):
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def split_list(text, separator=","):
    return [part.strip() for part in text.split(separator) if part.strip()]


def day_lookup(grid):
    return {label.lower(): index for index, label in enumerate(grid["days"])}


def parse_period_tokens(text, period_count):
    indexes = []
    for token in split_list(text):
        match = PERIOD_RANGE.match(token)
        if not match:
            raise ValueError(f"bad period '{token}'")
        first = int(match.group(1))
        last = int(match.group(2) or first)
        if not 1 <= first <= last <= period_count:
            raise ValueError(f"period '{token}' outside 1-{period_count}")
        indexes.extend(range(first - 1, last))
    return indexes


def parse_slots(text, grid):
    days = day_lookup(grid)
    period_count = len(grid["periods"])
    slots = []
    for segment in split_list(text, ";"):
        parts = segment.split(None, 1)
        day = days.get(parts[0].lower())
        if day is None:
            raise ValueError(f"unknown day '{parts[0]}'")
        if len(parts) == 1:
            indexes = range(period_count)
        else:
            indexes = parse_period_tokens(parts[1], period_count)
        for index in indexes:
            slot = [day, index]
            if slot not in slots:
                slots.append(slot)
    return slots


def parse_fixed(text, grid):
    days = day_lookup(grid)
    period_count = len(grid["periods"])
    slots, rooms = [], []
    for segment in split_list(text, ";"):
        match = FIXED_SLOT.match(segment)
        if not match:
            raise ValueError(f"bad fixed slot '{segment}'")
        day = days.get(match.group(1).lower())
        if day is None:
            raise ValueError(f"unknown day '{match.group(1)}'")
        period = int(match.group(2))
        if not 1 <= period <= period_count:
            raise ValueError(f"period 'P{period}' outside 1-{period_count}")
        slot = [day, period - 1]
        if slot not in slots:
            slots.append(slot)
        room = match.group(3)
        if room and room not in rooms:
            rooms.append(room)
    return slots, rooms


def read_rows(sheet, plan):
    rows = []
    for number, values in enumerate(sheet.iter_rows(values_only=True), start=1):
        if number > MAX_ROWS:
            plan.error(f"{sheet.title}: more than {MAX_ROWS} rows")
            break
        texts = [cell_text(value) for value in values]
        if any(texts):
            rows.append((number, texts))
    return rows


def header_index(name, texts, plan):
    columns = [text.lower() for text in texts]
    personal = sorted(PERSONAL & set(columns))
    if personal:
        plan.error(f"{name}: personal data columns are not accepted ({', '.join(personal)})")
        return None
    missing = [column for column in REQUIRED[name] if column not in columns]
    if missing:
        plan.error(f"{name}: missing columns {', '.join(missing)}")
        return None
    extra = [
        text for text, column in zip(texts, columns, strict=True) if column not in COLUMNS[name]
    ]
    extra = [text for text in extra if text]
    if extra:
        plan.summary.setdefault("ignored_columns", {})[name] = extra
    return {column: index for index, column in enumerate(columns) if column in COLUMNS[name]}


def record_from(name, index, texts):
    record = {column: "" for column in COLUMNS[name]}
    for column, position in index.items():
        record[column] = texts[position] if position < len(texts) else ""
    return record


def read_table(name, rows, plan):
    if not rows:
        plan.error(f"{name}: sheet is empty")
        return []
    index = header_index(name, rows[0][1], plan)
    if index is None:
        return []
    return [(number, record_from(name, index, texts)) for number, texts in rows[1:]]


def parse_grid(rows, plan):
    meta, periods, index = {}, [], None
    for number, texts in rows:
        key = texts[0].lower()
        if key in GRID_KEYS:
            meta[key] = texts[1] if len(texts) > 1 else ""
        elif key == "period":
            index = header_index(GRID, texts, plan)
            if index is None:
                return
        elif index is not None:
            periods.append((number, record_from(GRID, index, texts)))
        else:
            plan.row_error(GRID, number, "expected a key row or the period header")
    if index is None:
        plan.error("Grid: period header not found")
        return
    plan.grid = parse_periods(periods, meta, plan)
    plan.timetable = parse_timetable_meta(meta, plan)


def parse_periods(periods, meta, plan):
    days = split_list(meta.get("days", ""))
    if not days:
        plan.error("Grid: days row is missing or empty")
    if len({day.lower() for day in days}) != len(days):
        plan.error("Grid: duplicate day labels")
    slots, breaks = [], []
    for expected, (number, record) in enumerate(periods, start=1):
        if as_int(record["period"]) != expected:
            plan.row_error(GRID, number, f"period must be {expected}")
        start, end = as_clock(record["start"]), as_clock(record["end"])
        if start is None or end is None:
            plan.row_error(GRID, number, "start and end must be HH:MM")
        elif start >= end:
            plan.row_error(GRID, number, "start must be before end")
        flag = record["break_after"].lower()
        if flag in YES:
            breaks.append(expected - 1)
        elif flag not in NO:
            plan.row_error(GRID, number, "break_after must be yes or no")
        slots.append([start or "", end or ""])
    if not slots:
        plan.error("Grid: no period rows")
    return {"days": days, "periods": slots, "breaks_after": breaks}


def parse_timetable_meta(meta, plan):
    name = meta.get("name", "")
    if not name:
        plan.error("Grid: name row is required")
    elif len(name) > MAX_NAME:
        plan.error(f"Grid: name longer than {MAX_NAME} characters")
    start, end = as_date(meta.get("start_date", "")), as_date(meta.get("end_date", ""))
    if start is None or end is None:
        plan.error("Grid: start_date and end_date must be YYYY-MM-DD")
    elif start > end:
        plan.error("Grid: start_date must not be after end_date")
    return {
        "name": name,
        "department": meta.get("department", ""),
        "start_date": start.isoformat() if start else "",
        "end_date": end.isoformat() if end else "",
    }


def valid_code(sheet, number, code, seen, plan):
    if not code:
        plan.row_error(sheet, number, "code is required")
        return False
    if len(code) > MAX_CODE:
        plan.row_error(sheet, number, f"code longer than {MAX_CODE} characters")
        return False
    if code in seen:
        plan.row_error(sheet, number, f"duplicate code {code}")
        return False
    seen.add(code)
    return True


def slots_or_error(sheet, number, column, text, plan):
    if not text or plan.grid is None:
        return []
    try:
        return parse_slots(text, plan.grid)
    except ValueError as exc:
        plan.row_error(sheet, number, f"{column}: {exc}")
        return []


def parse_teachers(records, plan):
    seen = set()
    for number, record in records:
        if not valid_code(TEACHERS, number, record["code"], seen, plan):
            continue
        max_load = as_int(record["max_per_week"])
        if max_load is None or max_load < 0:
            plan.row_error(TEACHERS, number, "max_per_week must be a whole number")
            continue
        plan.teachers.append(
            {
                "code": record["code"],
                "name": record["name"][:MAX_NAME],
                "department": record["department"],
                "max_load": max_load,
                "unavailable": slots_or_error(
                    TEACHERS, number, "unavailable", record["unavailable"], plan
                ),
                "preferred": slots_or_error(TEACHERS, number, "prefers", record["prefers"], plan),
            }
        )


def parse_rooms(records, plan):
    seen = set()
    for number, record in records:
        if not valid_code(ROOMS, number, record["code"], seen, plan):
            continue
        capacity = as_int(record["capacity"])
        if capacity is None or capacity < 1:
            plan.row_error(ROOMS, number, "capacity must be a positive whole number")
            continue
        tags = split_list(record["tags"])
        if any(len(tag) > MAX_CODE for tag in tags):
            plan.row_error(ROOMS, number, f"tags longer than {MAX_CODE} characters")
            continue
        plan.rooms.append({"code": record["code"], "capacity": capacity, "tags": tags})


def parse_sections(records, plan):
    seen = set()
    candidates = []
    for number, record in records:
        if not valid_code(SECTIONS, number, record["code"], seen, plan):
            continue
        strength = as_int(record["strength"])
        if strength is None or strength < 0:
            plan.row_error(SECTIONS, number, "strength must be a whole number")
            continue
        candidates.append((number, record, strength))
    parents = {record["code"] for _, record, _ in candidates if not record["parent"]}
    for number, record, strength in candidates:
        if record["parent"] and record["parent"] not in parents:
            plan.row_error(SECTIONS, number, f"unknown parent section {record['parent']}")
            continue
        plan.sections.append(
            {
                "code": record["code"],
                "capacity": strength,
                "department": record["department"],
                "parent": record["parent"],
                "kind": BATCH if record["parent"] else SECTION,
            }
        )


def parse_subjects(records, plan):
    seen = set()
    for number, record in records:
        if not valid_code(SUBJECTS, number, record["code"], seen, plan):
            continue
        length = as_int(record["length"] or "1")
        if length is None or not 1 <= length <= 4:
            plan.row_error(SUBJECTS, number, "length must be between 1 and 4")
            continue
        if record["kind"].lower() not in SUBJECT_KINDS:
            plan.row_error(SUBJECTS, number, "kind must be lecture or lab")
            continue
        if not record["name"]:
            plan.row_error(SUBJECTS, number, "name is required")
            continue
        plan.subjects.append(
            {
                "code": record["code"],
                "name": record["name"][:MAX_NAME],
                "length": length,
                "kind": record["kind"].lower(),
            }
        )


def parse_requirements(records, plan):
    teachers = {row["code"] for row in plan.teachers}
    rooms = {row["code"] for row in plan.rooms}
    attendees = {row["code"] for row in plan.sections}
    subjects = {row["code"] for row in plan.subjects}
    for number, record in records:
        problems = []
        section_codes = split_list(record["sections"])
        if not section_codes:
            problems.append("sections is required")
        problems.extend(
            f"unknown section {code}" for code in section_codes if code not in attendees
        )
        if record["subject"] not in subjects:
            problems.append(f"unknown subject {record['subject'] or '(blank)'}")
        teacher_codes = [code.strip() for code in TEACHER_SPLIT.split(record["teachers"])]
        teacher_codes = list(dict.fromkeys(code for code in teacher_codes if code))
        if not teacher_codes:
            problems.append("teachers is required")
        problems.extend(f"unknown teacher {code}" for code in teacher_codes if code not in teachers)
        per_week = as_int(record["per_week"])
        if per_week is None or per_week < 1:
            problems.append("per_week must be a positive whole number")
        rooms_needed = as_int(record["rooms"] or "1")
        if rooms_needed is None or not 0 <= rooms_needed <= MAX_ROOMS:
            problems.append(f"rooms must be between 0 and {MAX_ROOMS}")
        if len(record["room_tag"]) > MAX_CODE:
            problems.append(f"room_tag longer than {MAX_CODE} characters")
        fixed_slots, fixed_rooms = [], []
        if record["fixed"] and plan.grid is not None:
            try:
                fixed_slots, fixed_rooms = parse_fixed(record["fixed"], plan.grid)
            except ValueError as exc:
                problems.append(f"fixed: {exc}")
        problems.extend(f"unknown room {code}" for code in fixed_rooms if code not in rooms)
        if per_week is not None and len(fixed_slots) > per_week:
            problems.append("more fixed slots than per_week")
        for problem in problems:
            plan.row_error(REQUIREMENTS, number, problem)
        if problems:
            continue
        plan.requirements.append(
            {
                "sections": list(dict.fromkeys(section_codes)),
                "subject": record["subject"],
                "teachers": teacher_codes,
                "per_week": per_week,
                "room_tag": record["room_tag"],
                "rooms": rooms_needed,
                "fixed_slots": fixed_slots,
                "fixed_rooms": fixed_rooms,
            }
        )


def open_workbook(data, plan):
    if len(data) > MAX_BYTES:
        plan.error(f"file larger than {MAX_BYTES // (1024 * 1024)} MiB")
        return None
    if not data.startswith(ZIP_MAGIC):
        plan.error("file is not an .xlsx workbook")
        return None
    try:
        return load_workbook(BytesIO(data), read_only=True, data_only=True)
    except Exception:
        plan.error("file could not be read as an .xlsx workbook")
        return None


def parse_workbook(data):
    plan = ImportPlan()
    workbook = open_workbook(bytes(data), plan)
    if workbook is None:
        return plan
    try:
        names = list(workbook.sheetnames)
        if len(names) > MAX_SHEETS:
            plan.error(f"more than {MAX_SHEETS} sheets")
            return plan
        unknown = [name for name in names if name not in SHEETS]
        if unknown:
            plan.error(f"unknown sheets: {', '.join(unknown)}")
            return plan
        missing = [name for name in SHEETS if name not in names]
        if missing:
            plan.error(f"missing sheets: {', '.join(missing)}")
            return plan
        rows = {name: read_rows(workbook[name], plan) for name in SHEETS}
    finally:
        workbook.close()
    parse_grid(rows[GRID], plan)
    parse_teachers(read_table(TEACHERS, rows[TEACHERS], plan), plan)
    parse_rooms(read_table(ROOMS, rows[ROOMS], plan), plan)
    parse_sections(read_table(SECTIONS, rows[SECTIONS], plan), plan)
    parse_subjects(read_table(SUBJECTS, rows[SUBJECTS], plan), plan)
    parse_requirements(read_table(REQUIREMENTS, rows[REQUIREMENTS], plan), plan)
    plan.summary.update(
        {
            "teachers": len(plan.teachers),
            "rooms": len(plan.rooms),
            "sections": sum(row["kind"] == SECTION for row in plan.sections),
            "batches": sum(row["kind"] == BATCH for row in plan.sections),
            "subjects": len(plan.subjects),
            "requirements": len(plan.requirements),
            "errors": len(plan.errors),
        }
    )
    return plan


def department_names(plan):
    names = [plan.timetable["department"]] if plan.timetable else []
    names.extend(row["department"] for row in plan.teachers)
    names.extend(row["department"] for row in plan.sections)
    return sorted({name for name in names if name})


def ensure_writable(actor, obj, label):
    if not can(actor, Perm.DATA_IMPORT, obj, write=True):
        raise ValueError(f"{label} is outside your department")


def upsert_resource(model, actor, kind, code, fields, created, updated):
    bucket = PLURAL[kind]
    label = f"{bucket} {code}"
    resource = model.objects.filter(kind=kind, code=code).first()
    if resource is None:
        resource = model(kind=kind, code=code, **fields)
        if kind != ROOM:
            ensure_writable(actor, resource, label)
        resource.save()
        created[bucket] += 1
        return resource
    if kind != ROOM:
        ensure_writable(actor, resource, label)
        ensure_writable(actor, SimpleNamespace(department_id=fields["department_id"]), label)
    for name, value in fields.items():
        setattr(resource, name, value)
    resource.active = True
    resource.save()
    updated[bucket] += 1
    return resource


def apply_departments(plan, model, created, updated):
    departments = {}
    for name in department_names(plan):
        department, was_created = model.objects.get_or_create(name=name)
        departments[name] = department
        (created if was_created else updated)["departments"] += 1
    return departments


def apply_resources(plan, actor, Resource, departments, created, updated):
    resources = {}
    for row in plan.teachers:
        fields = {
            "name": row["name"],
            "department_id": departments[row["department"]].id if row["department"] else None,
            "max_load": row["max_load"],
            "unavailable": row["unavailable"],
            "preferred": row["preferred"],
        }
        resources[(TEACHER, row["code"])] = upsert_resource(
            Resource, actor, TEACHER, row["code"], fields, created, updated
        )
    for row in plan.rooms:
        fields = {"capacity": row["capacity"], "tags": row["tags"], "department_id": None}
        resources[(ROOM, row["code"])] = upsert_resource(
            Resource, actor, ROOM, row["code"], fields, created, updated
        )
    for kind in (SECTION, BATCH):
        for row in plan.sections:
            if row["kind"] != kind:
                continue
            fields = {
                "capacity": row["capacity"],
                "department_id": departments[row["department"]].id if row["department"] else None,
                "parent": resources[(SECTION, row["parent"])] if row["parent"] else None,
            }
            resources[(kind, row["code"])] = upsert_resource(
                Resource, actor, kind, row["code"], fields, created, updated
            )
    return resources


def apply_subjects(plan, actor, Subject, department, created, updated):
    subjects = {}
    for row in plan.subjects:
        subject = Subject.objects.filter(code=row["code"]).first()
        label = f"subjects {row['code']}"
        if subject is None:
            subject = Subject(code=row["code"], department=department)
            created["subjects"] += 1
        else:
            ensure_writable(actor, subject, label)
            updated["subjects"] += 1
        subject.name, subject.length, subject.active = row["name"], row["length"], True
        ensure_writable(actor, subject, label)
        subject.save()
        subjects[row["code"]] = subject
    return subjects


def apply_timetable(plan, actor, Timetable, services, department, created, updated):
    name = plan.timetable["name"]
    timetable = Timetable.objects.filter(name=name).first()
    if timetable is not None:
        ensure_writable(actor, timetable, f"timetable {name}")
        updated["timetables"] += 1
        return timetable
    ensure_writable(
        actor,
        SimpleNamespace(department_id=department.id if department else None),
        f"timetable {name}",
    )
    created["timetables"] += 1
    return services.create_timetable(
        name=name,
        department=department,
        grid=plan.grid,
        start_date=date.fromisoformat(plan.timetable["start_date"]),
        end_date=date.fromisoformat(plan.timetable["end_date"]),
        actor=actor,
    )


def apply_requirements(plan, version, Requirement, RequirementResource, resources, subjects):
    attendee_kind = {row["code"]: row["kind"] for row in plan.sections}
    participants = []
    for row in plan.requirements:
        subject = subjects[row["subject"]]
        requirement = Requirement.objects.create(
            version=version,
            subject=subject,
            sessions=row["per_week"],
            length=subject.length,
            room_tag=row["room_tag"],
            rooms_needed=row["rooms"],
            fixed_slots=row["fixed_slots"],
        )
        members = [(resources[(TEACHER, code)], ROLE_TEACHER) for code in row["teachers"]]
        members += [
            (resources[(attendee_kind[code], code)], ROLE_ATTENDEE) for code in row["sections"]
        ]
        members += [(resources[(ROOM, code)], ROLE_FIXED_ROOM) for code in row["fixed_rooms"]]
        participants.extend(
            RequirementResource(
                tenant_id=version.tenant_id, requirement=requirement, resource=resource, role=role
            )
            for resource, role in members
        )
    RequirementResource.objects.bulk_create(participants)
    return len(plan.requirements)


def apply(plan, actor):
    if plan.errors:
        raise ValueError("; ".join(plan.errors))
    if plan.grid is None or plan.timetable is None:
        raise ValueError("plan has no grid")
    if not can(actor, Perm.DATA_IMPORT):
        raise PermissionDenied
    from core.audit import audit
    from core.models import Department
    from timetable import services
    from timetable.models import Requirement, RequirementResource, Resource, Subject, Timetable

    created, updated = Counter(), Counter()
    with transaction.atomic():
        departments = apply_departments(plan, Department, created, updated)
        department = departments.get(plan.timetable["department"])
        resources = apply_resources(plan, actor, Resource, departments, created, updated)
        subjects = apply_subjects(plan, actor, Subject, department, created, updated)
        timetable = apply_timetable(plan, actor, Timetable, services, department, created, updated)
        version = services.create_draft(timetable, reason="Excel import", actor=actor)
        requirement_count = apply_requirements(
            plan, version, Requirement, RequirementResource, resources, subjects
        )
        summary = {
            "created": dict(created),
            "updated": dict(updated),
            "requirements": requirement_count,
            "timetable_id": str(timetable.id),
            "version_id": str(version.id),
        }
        audit(
            actor,
            "data.imported",
            version,
            after={
                "created": dict(created),
                "updated": dict(updated),
                "requirements": requirement_count,
            },
        )
    return summary


def safe_cell(text):
    text = "" if text is None else str(text)
    return "'" + text if text.startswith(FORMULA_PREFIXES) else text


def sheet_title(name, used):
    base = TITLE_FORBIDDEN.sub("", str(name)).strip(" '")[:TITLE_LIMIT].strip(" '") or "Sheet"
    title, counter = base, 1
    while title.lower() in used:
        counter += 1
        suffix = f" ({counter})"
        title = base[: TITLE_LIMIT - len(suffix)].rstrip() + suffix
    used.add(title.lower())
    return title


def joined(codes):
    return "+".join(sorted(codes)) or "-"


def group_assignments(assignments):
    groups = {}
    for row in assignments:
        key = (row.requirement_id, row.session, row.day)
        group = groups.setdefault(
            key,
            {
                "subject": row.requirement.subject.code,
                "day": row.day,
                "periods": set(),
                "members": set(),
                TEACHER: set(),
                ROOM: set(),
                "attendees": set(),
                "parents": defaultdict(set),
            },
        )
        group["periods"].add(row.period)
        group["members"].add(row.resource_id)
        resource = row.resource
        if resource.kind in (SECTION, BATCH):
            group["attendees"].add(resource.code)
            if resource.parent_id is not None:
                group["parents"][resource.parent_id].add(resource.code)
        else:
            group[resource.kind].add(resource.code)
    return groups


def line_for(resource, group, batches=()):
    subject = group["subject"]
    if batches:
        subject = f"{subject} ({'+'.join(sorted(batches))})"
    if resource.kind in (SECTION, BATCH):
        return f"{subject} / {joined(group[TEACHER])} / {joined(group[ROOM])}"
    if resource.kind == TEACHER:
        return f"{subject} / {joined(group['attendees'])} / {joined(group[ROOM])}"
    return f"{subject} / {joined(group['attendees'])} / {joined(group[TEACHER])}"


def cells_for(resource, groups):
    cells = defaultdict(list)
    for group in groups.values():
        if resource.id in group["members"]:
            text = line_for(resource, group)
        elif resource.kind == SECTION and group["parents"].get(resource.id):
            text = line_for(resource, group, group["parents"][resource.id])
        else:
            continue
        for period in sorted(group["periods"]):
            cells[(group["day"], period)].append(text)
    return cells


def write_grid_sheet(workbook, used, title, cells, grid):
    sheet = workbook.create_sheet(sheet_title(title, used))
    days = grid["days"]
    sheet.append([safe_cell("Period"), *[safe_cell(day) for day in days]])
    for index, (start, end) in enumerate(grid["periods"]):
        sheet.append(
            [
                safe_cell(f"{start}-{end}"),
                *[safe_cell("\n".join(cells.get((day, index), []))) for day in range(len(days))],
            ]
        )


def fixed_text(requirement, grid, rooms):
    parts = []
    for day, start in requirement.fixed_slots:
        label = f"{grid['days'][day]} P{start + 1}"
        if rooms:
            label += f" in {'+'.join(sorted(rooms))}"
        parts.append(label)
    return "; ".join(parts)


def write_requirements_sheet(workbook, used, requirements, grid):
    sheet = workbook.create_sheet(sheet_title(REQUIREMENTS, used))
    sheet.append([safe_cell(column) for column in COLUMNS[REQUIREMENTS]])
    for requirement in requirements:
        by_role = defaultdict(set)
        for participant in requirement.participants.all():
            by_role[participant.role].add(participant.resource.code)
        sheet.append(
            [
                safe_cell(",".join(sorted(by_role[ROLE_ATTENDEE]))),
                safe_cell(requirement.subject.code),
                safe_cell("+".join(sorted(by_role[ROLE_TEACHER]))),
                safe_cell(str(requirement.sessions)),
                safe_cell(requirement.room_tag),
                safe_cell(str(requirement.rooms_needed)),
                safe_cell(fixed_text(requirement, grid, by_role[ROLE_FIXED_ROOM])),
            ]
        )


def export_version(version):
    from timetable.models import Assignment

    grid = version.grid
    requirements = list(
        version.requirements.select_related("subject").prefetch_related("participants__resource")
    )
    assignments = list(
        Assignment.objects.filter(version=version).select_related(
            "resource", "requirement__subject"
        )
    )
    resources = {}
    for requirement in requirements:
        for participant in requirement.participants.all():
            resources[participant.resource_id] = participant.resource
    for row in assignments:
        resources[row.resource_id] = row.resource
    groups = group_assignments(assignments)
    workbook = Workbook()
    workbook.remove(workbook.active)
    used = set()
    ordered = sorted(resources.values(), key=lambda item: (SHEET_ORDER.index(item.kind), item.code))
    for resource in ordered:
        write_grid_sheet(workbook, used, resource.code, cells_for(resource, groups), grid)
    write_requirements_sheet(workbook, used, requirements, grid)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
