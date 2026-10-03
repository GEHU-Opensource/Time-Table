from io import BytesIO

import pytest
from openpyxl import Workbook, load_workbook

from core.models import AuditEvent
from timetable import excel
from timetable.models import (
    Assignment,
    Requirement,
    RequirementResource,
    Resource,
    Subject,
    Timetable,
    Version,
)

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
PERIODS = [
    ("09:00", "09:50", "no"),
    ("09:50", "10:40", "no"),
    ("10:40", "11:30", "yes"),
    ("11:45", "12:35", "no"),
    ("12:35", "13:25", "no"),
    ("14:00", "14:50", "no"),
    ("14:50", "15:40", "no"),
]
GRID = {
    "days": DAYS,
    "periods": [[start, end] for start, end, _ in PERIODS],
    "breaks_after": [2],
}

DEFAULT_SHEETS = {
    "Grid": [
        ["name", "CSE Sem 3"],
        ["department", "CSE"],
        ["start_date", "2026-01-05"],
        ["end_date", "2026-05-15"],
        ["days", ",".join(DAYS)],
        ["period", "start", "end", "break_after"],
        *[[index + 1, start, end, flag] for index, (start, end, flag) in enumerate(PERIODS)],
    ],
    "Teachers": [
        ["code", "name", "department", "max_per_week", "unavailable", "prefers"],
        ["T01", "Asha", "CSE", 18, "Sat; Mon P1-P2", ""],
        ["T02", "Bala", "CSE", 16, "", "Tue P3"],
    ],
    "Rooms": [
        ["code", "capacity", "tags"],
        ["R1", 60, "lecture"],
        ["R3", 30, "lab,computers"],
    ],
    "Sections": [
        ["code", "strength", "department", "parent"],
        ["CSE-A", 60, "CSE", ""],
        ["CSE-A1", 30, "CSE", "CSE-A"],
    ],
    "Subjects": [
        ["code", "name", "length", "kind"],
        ["MATH", "Mathematics", 1, "lecture"],
        ["DSLAB", "Data Structures Lab", 2, "lab"],
    ],
    "Requirements": [
        ["sections", "subject", "teachers", "per_week", "room_tag", "rooms", "fixed"],
        ["CSE-A", "MATH", "T01+T02", 2, "lecture", 1, ""],
        ["CSE-A1", "DSLAB", "T02", 1, "lab", 1, "Mon P1 in R3"],
    ],
}


def workbook_bytes(overrides=None, extra_sheets=None):
    sheets = {**DEFAULT_SHEETS, **(overrides or {})}
    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, rows in sheets.items():
        sheet = workbook.create_sheet(name)
        for row in rows:
            sheet.append(row)
    for name, rows in (extra_sheets or {}).items():
        sheet = workbook.create_sheet(name)
        for row in rows:
            sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def rows_with(sheet_name, replacement_rows):
    return {sheet_name: [DEFAULT_SHEETS[sheet_name][0], *replacement_rows]}


@pytest.fixture
def fake_services(monkeypatch):
    from timetable import services

    def create_timetable(*, name, department, grid, start_date, end_date, actor):
        return Timetable.objects.create(
            name=name,
            department=department,
            grid=grid,
            start_date=start_date,
            end_date=end_date,
        )

    def create_draft(timetable, *, parent=None, reason="", actor):
        return Version.objects.create(
            timetable=timetable,
            number=timetable.versions.count() + 1,
            parent=parent,
            grid=timetable.grid,
            reason=reason,
            created_by=actor,
        )

    monkeypatch.setattr(services, "create_timetable", create_timetable)
    monkeypatch.setattr(services, "create_draft", create_draft)
    return services


def test_parse_default_workbook_has_no_errors():
    plan = excel.parse_workbook(workbook_bytes())

    assert plan.errors == []
    assert plan.grid == GRID
    assert plan.timetable == {
        "name": "CSE Sem 3",
        "department": "CSE",
        "start_date": "2026-01-05",
        "end_date": "2026-05-15",
    }
    assert plan.summary["teachers"] == 2
    assert plan.summary["sections"] == 1
    assert plan.summary["batches"] == 1
    assert plan.summary["requirements"] == 2


def test_unavailable_text_parsing():
    plan = excel.parse_workbook(workbook_bytes())

    asha = next(row for row in plan.teachers if row["code"] == "T01")
    saturday = [[5, period] for period in range(len(PERIODS))]
    assert asha["unavailable"] == [*saturday, [0, 0], [0, 1]]
    bala = next(row for row in plan.teachers if row["code"] == "T02")
    assert bala["preferred"] == [[1, 2]]


def test_parse_slots_directly():
    assert excel.parse_slots("Sat", GRID) == [[5, period] for period in range(7)]
    assert excel.parse_slots("Mon P1-P2", GRID) == [[0, 0], [0, 1]]
    assert excel.parse_slots("mon p2, P4-P5; Tue P1", GRID) == [[0, 1], [0, 3], [0, 4], [1, 0]]
    with pytest.raises(ValueError, match="unknown day"):
        excel.parse_slots("Sun", GRID)
    with pytest.raises(ValueError, match="outside"):
        excel.parse_slots("Mon P9", GRID)


def test_fixed_text_parsing():
    assert excel.parse_fixed("Mon P1 in R3", GRID) == ([[0, 0]], ["R3"])
    assert excel.parse_fixed("Sat P7", GRID) == ([[5, 6]], [])
    assert excel.parse_fixed("Mon P1 in R3; Tue P2 in R1", GRID) == ([[0, 0], [1, 1]], ["R3", "R1"])
    with pytest.raises(ValueError, match="bad fixed slot"):
        excel.parse_fixed("whenever", GRID)


def test_unknown_teacher_is_row_numbered_and_apply_raises(scope, admin_user, fake_services):
    plan = excel.parse_workbook(
        workbook_bytes(
            rows_with(
                "Requirements",
                [
                    ["CSE-A", "MATH", "T01", 2, "", 1, ""],
                    ["CSE-A", "MATH", "XY99", 2, "", 1, ""],
                ],
            )
        )
    )

    assert "Requirements row 3: unknown teacher XY99" in plan.errors
    with pytest.raises(ValueError, match="unknown teacher XY99"):
        excel.apply(plan, admin_user)
    assert not Timetable.objects.exists()


def test_personal_data_header_rejected():
    plan = excel.parse_workbook(
        workbook_bytes(
            {
                "Teachers": [
                    ["code", "name", "department", "max_per_week", "unavailable", "Phone"],
                    ["T01", "Asha", "CSE", 18, "", "999"],
                ]
            }
        )
    )

    assert any("personal data columns are not accepted" in error for error in plan.errors)
    assert plan.teachers == []


def test_oversize_data_rejected():
    plan = excel.parse_workbook(excel.ZIP_MAGIC + bytes(excel.MAX_BYTES))

    assert plan.errors == ["file larger than 5 MiB"]


def test_non_zip_bytes_rejected():
    plan = excel.parse_workbook(b"<html>not a workbook</html>")

    assert plan.errors == ["file is not an .xlsx workbook"]


def test_corrupt_zip_rejected():
    plan = excel.parse_workbook(excel.ZIP_MAGIC + b"garbage" * 10)

    assert plan.errors == ["file could not be read as an .xlsx workbook"]


def test_unknown_sheet_rejected():
    plan = excel.parse_workbook(workbook_bytes(extra_sheets={"Students": [["name"]]}))

    assert plan.errors == ["unknown sheets: Students"]


def test_extra_columns_ignored_but_reported():
    plan = excel.parse_workbook(
        workbook_bytes(
            {
                "Rooms": [
                    ["code", "capacity", "tags", "building"],
                    ["R1", 60, "lecture", "Main"],
                    ["R3", 30, "lab", "Annex"],
                ]
            }
        )
    )

    assert plan.errors == []
    assert plan.summary["ignored_columns"] == {"Rooms": ["building"]}


def test_grid_validation_errors():
    plan = excel.parse_workbook(
        workbook_bytes(
            {
                "Grid": [
                    ["name", "Broken"],
                    ["start_date", "2026-01-05"],
                    ["end_date", "2026-05-15"],
                    ["days", "Mon,Tue"],
                    ["period", "start", "end", "break_after"],
                    [1, "09:00", "09:50", "no"],
                    [3, "9:50", "09:40", "maybe"],
                ]
            }
        )
    )

    assert "Grid row 7: period must be 2" in plan.errors
    assert "Grid row 7: start must be before end" in plan.errors
    assert "Grid row 7: break_after must be yes or no" in plan.errors


def test_safe_cell_prefixes_formula_looking_text():
    for prefix in ("=", "+", "-", "@", "\t", "\r"):
        assert excel.safe_cell(f"{prefix}SUM(A1)") == f"'{prefix}SUM(A1)"
    assert excel.safe_cell("MATH / T01 / R1") == "MATH / T01 / R1"
    assert excel.safe_cell(None) == ""


def test_sheet_title_sanitised_and_deduplicated():
    used = set()

    assert excel.sheet_title("A[B]:C*D?E/F\\G", used) == "ABCDEFG"
    assert excel.sheet_title("abcdefg", used) == "abcdefg (2)"
    long_name = "X" * 40
    assert excel.sheet_title(long_name, used) == "X" * 31
    assert excel.sheet_title(long_name, used) == "X" * 27 + " (2)"
    assert excel.sheet_title("[]", used) == "Sheet"


def test_round_trip_parse_apply_export(scope, admin_user, fake_services):
    plan = excel.parse_workbook(workbook_bytes())
    summary = excel.apply(plan, admin_user)

    version = Version.objects.get(id=summary["version_id"])
    assert version.status == Version.Status.DRAFT
    assert summary["created"]["teachers"] == 2
    assert summary["created"]["rooms"] == 2
    assert summary["created"]["sections"] == 1
    assert summary["created"]["batches"] == 1
    assert summary["created"]["subjects"] == 2
    assert summary["created"]["departments"] == 1
    assert summary["created"]["timetables"] == 1
    assert summary["requirements"] == 2
    assert version.timetable.department.name == "CSE"
    assert version.timetable.grid == GRID

    asha = Resource.objects.get(kind="teacher", code="T01")
    assert asha.max_load == 18
    assert asha.department.name == "CSE"
    assert [0, 0] in asha.unavailable
    batch = Resource.objects.get(kind="batch", code="CSE-A1")
    assert batch.parent.code == "CSE-A"
    assert Resource.objects.get(kind="room", code="R3").tags == ["lab", "computers"]
    assert Subject.objects.get(code="DSLAB").length == 2

    lab = Requirement.objects.get(version=version, subject__code="DSLAB")
    assert lab.fixed_slots == [[0, 0]]
    assert lab.length == 2
    fixed_room = lab.participants.get(role="fixed_room")
    assert fixed_room.resource.code == "R3"
    math = Requirement.objects.get(version=version, subject__code="MATH")
    assert math.sessions == 2
    assert sorted(p.resource.code for p in math.participants.filter(role="teacher")) == [
        "T01",
        "T02",
    ]
    assert [p.resource.code for p in math.participants.filter(role="attendee")] == ["CSE-A"]

    event = AuditEvent.objects.get(action="data.imported")
    assert event.object_id == version.id
    assert event.after["requirements"] == 2
    assert "T01" not in str(event.after)

    section = Resource.objects.get(kind="section", code="CSE-A")
    teachers = {r.code: r for r in Resource.objects.filter(kind="teacher")}
    room = Resource.objects.get(kind="room", code="R1")
    Assignment.objects.bulk_create(
        Assignment(
            tenant_id=version.tenant_id,
            version=version,
            requirement=math,
            session=0,
            resource=resource,
            day=0,
            period=0,
            serves=section,
        )
        for resource in (section, teachers["T01"], teachers["T02"], room)
    )
    Assignment.objects.bulk_create(
        Assignment(
            tenant_id=version.tenant_id,
            version=version,
            requirement=lab,
            session=0,
            resource=resource,
            day=0,
            period=period,
            serves=batch,
        )
        for resource in (batch, teachers["T02"], Resource.objects.get(kind="room", code="R3"))
        for period in (1, 2)
    )

    exported = load_workbook(BytesIO(excel.export_version(version)))

    assert exported.sheetnames == ["CSE-A", "CSE-A1", "T01", "T02", "R1", "R3", "Requirements"]
    section_sheet = exported["CSE-A"]
    assert [cell.value for cell in section_sheet[1]] == ["Period", *DAYS]
    assert section_sheet["A2"].value == "09:00-09:50"
    assert section_sheet["B2"].value == "MATH / T01+T02 / R1"
    assert section_sheet["B3"].value == "DSLAB (CSE-A1) / T02 / R3"
    assert section_sheet["B4"].value == "DSLAB (CSE-A1) / T02 / R3"
    assert section_sheet["C2"].value in (None, "")
    assert exported["CSE-A1"]["B3"].value == "DSLAB / T02 / R3"
    assert exported["T01"]["B2"].value == "MATH / CSE-A / R1"
    assert exported["T02"]["B2"].value == "MATH / CSE-A / R1"
    assert exported["T02"]["B3"].value == "DSLAB / CSE-A1 / R3"
    assert exported["R1"]["B2"].value == "MATH / CSE-A / T01+T02"
    requirements = exported["Requirements"]
    assert [cell.value for cell in requirements[1]] == list(excel.COLUMNS["Requirements"])
    rows = {row[1]: row for row in requirements.iter_rows(min_row=2, values_only=True)}
    assert rows["MATH"] == ("CSE-A", "MATH", "T01+T02", "2", "lecture", "1", None)
    assert rows["DSLAB"] == ("CSE-A1", "DSLAB", "T02", "1", "lab", "1", "Mon P1 in R3")
    assert not exported.defined_names
    for sheet in exported.worksheets:
        for row in sheet.iter_rows():
            assert all(cell.hyperlink is None for cell in row)


def test_second_import_updates_and_reuses_timetable(scope, admin_user, fake_services):
    first = excel.apply(excel.parse_workbook(workbook_bytes()), admin_user)
    second = excel.apply(
        excel.parse_workbook(
            workbook_bytes(
                rows_with(
                    "Teachers",
                    [
                        ["T01", "Asha", "CSE", 20, "", ""],
                        ["T02", "Bala", "CSE", 16, "", ""],
                    ],
                )
            )
        ),
        admin_user,
    )

    assert second["timetable_id"] == first["timetable_id"]
    assert second["version_id"] != first["version_id"]
    assert second["updated"]["teachers"] == 2
    assert second["updated"]["timetables"] == 1
    assert "created" in second and "teachers" not in second["created"]
    assert Resource.objects.get(kind="teacher", code="T01").max_load == 20
    assert Version.objects.filter(timetable_id=first["timetable_id"]).count() == 2


def test_hod_cannot_import_into_another_department(scope, hod_user, fake_services):
    plan = excel.parse_workbook(
        workbook_bytes(
            {
                "Grid": [
                    *DEFAULT_SHEETS["Grid"][:1],
                    ["department", "ECE"],
                    *DEFAULT_SHEETS["Grid"][2:],
                ]
            }
        )
    )

    with pytest.raises(ValueError, match="outside your department"):
        excel.apply(plan, hod_user)
    assert not Timetable.objects.exists()


def test_formula_cells_are_never_evaluated_on_import():
    plan = excel.parse_workbook(
        workbook_bytes(rows_with("Subjects", [['=CONCAT("MA","TH")', "Hack", 1, "lecture"]]))
    )

    assert "Subjects row 2: code is required" in plan.errors
    assert plan.subjects == []


def test_formula_looking_text_is_prefixed_in_export(scope, admin_user):
    timetable = Timetable.objects.create(
        name="Hack", grid=GRID, start_date="2026-01-05", end_date="2026-05-15"
    )
    version = Version.objects.create(timetable=timetable, number=1, grid=GRID)
    subject = Subject.objects.create(code="=HACK", name="Hack", length=1)
    teacher = Resource.objects.create(kind="teacher", code="T01", max_load=10)
    section = Resource.objects.create(kind="section", code="-CSE", capacity=60)
    requirement = Requirement.objects.create(version=version, subject=subject, sessions=1)
    RequirementResource.objects.bulk_create(
        [
            RequirementResource(
                tenant_id=version.tenant_id,
                requirement=requirement,
                resource=teacher,
                role="teacher",
            ),
            RequirementResource(
                tenant_id=version.tenant_id,
                requirement=requirement,
                resource=section,
                role="attendee",
            ),
        ]
    )
    Assignment.objects.bulk_create(
        Assignment(
            tenant_id=version.tenant_id,
            version=version,
            requirement=requirement,
            session=0,
            resource=resource,
            day=2,
            period=3,
            serves=section,
        )
        for resource in (section, teacher)
    )

    exported = load_workbook(BytesIO(excel.export_version(version)))

    assert exported.sheetnames == ["-CSE", "T01", "Requirements"]
    assert exported["-CSE"]["D5"].value == "'=HACK / T01 / -"
    assert exported["-CSE"]["D5"].data_type == "s"
    assert exported["T01"]["D5"].value == "'=HACK / -CSE / -"
    assert exported["Requirements"]["A2"].value == "'-CSE"
    assert exported["Requirements"]["B2"].value == "'=HACK"
    assert exported["Requirements"]["B2"].data_type == "s"


def test_requirement_participants_are_unique_per_resource(scope, admin_user, fake_services):
    plan = excel.parse_workbook(
        workbook_bytes(
            rows_with("Requirements", [["CSE-A, CSE-A", "MATH", "T01,T01", 2, "", 1, ""]])
        )
    )
    summary = excel.apply(plan, admin_user)

    requirement = Requirement.objects.get(version_id=summary["version_id"])
    assert RequirementResource.objects.filter(requirement=requirement).count() == 2
