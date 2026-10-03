from datetime import timedelta

import pytest
from django.utils import timezone

from timetable import grids, services
from timetable.models import Assignment, Requirement, RequirementResource, Resource, Subject
from timetable.views import assignment_rows

GRID = {
    "days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
    "periods": [
        ["09:00", "09:55"],
        ["09:55", "10:50"],
        ["11:10", "12:05"],
        ["12:05", "13:00"],
        ["13:20", "14:15"],
        ["14:15", "15:10"],
    ],
    "breaks_after": [1, 3],
}

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def inline_solver(monkeypatch):
    monkeypatch.setenv("TT_SOLVER_INLINE", "1")


@pytest.fixture
def world(scope, department):
    teachers = [
        Resource.objects.create(kind="teacher", code=f"T{i}", max_load=20, department=department)
        for i in range(1, 4)
    ]
    rooms = {
        "R1": Resource.objects.create(kind="room", code="R1", capacity=80, tags=["lecture"]),
        "L1": Resource.objects.create(kind="room", code="L1", capacity=35, tags=["lab"]),
        "L2": Resource.objects.create(kind="room", code="L2", capacity=35, tags=["lab"]),
    }
    section = Resource.objects.create(
        kind="section", code="CSE-5A", capacity=70, department=department
    )
    batches = [
        Resource.objects.create(
            kind="batch", code=f"CSE-5A-G{i}", capacity=35, parent=section, department=department
        )
        for i in (1, 2)
    ]
    subjects = {
        code: Subject.objects.create(code=code, name=code, length=length, department=department)
        for code, length in [("OS", 1), ("DBMS", 1), ("MATH", 1), ("DBMS-LAB", 2)]
    }
    return {
        "teachers": teachers,
        "rooms": rooms,
        "section": section,
        "batches": batches,
        "subjects": subjects,
    }


def add_requirement(version, subject, teachers, attendees, sessions, room_tag, rooms_needed=1):
    requirement = Requirement.objects.create(
        version=version,
        subject=subject,
        sessions=sessions,
        length=subject.length,
        room_tag=room_tag,
        rooms_needed=rooms_needed,
    )
    for teacher in teachers:
        RequirementResource.objects.create(
            requirement=requirement, resource=teacher, role="teacher"
        )
    for attendee in attendees:
        RequirementResource.objects.create(
            requirement=requirement, resource=attendee, role="attendee"
        )
    return requirement


def solve(version, tenant, actor):
    services.start_solve(version, actor)
    version.refresh_from_db()
    assert version.status == "solving", version.solver_stats
    services.run_solve(str(version.pk), str(tenant.id))
    version.refresh_from_db()
    assert version.status == "draft", version.solver_stats
    return version


def slots_by_subject(version):
    found = {}
    rows = Assignment.objects.filter(version=version).select_related("requirement__subject")
    for row in rows:
        found.setdefault(row.requirement.subject.code, set()).add((row.day, row.period))
    return found


def assert_no_clashes(rows):
    seen = set()
    for row in rows:
        key = (row.resource_id, row.day, row.period)
        assert key not in seen, key
        seen.add(key)


def make_timetable(name, department, actor, days=90):
    today = timezone.localdate()
    return services.create_timetable(
        name=name,
        department=department,
        grid=GRID,
        start_date=today - timedelta(days=30),
        end_date=today + timedelta(days=days),
        actor=actor,
    )


def test_generate_publish_change_and_second_timetable(scope, department, admin_user, world):
    teachers = world["teachers"]
    section = world["section"]
    batches = world["batches"]
    subjects = world["subjects"]
    today = timezone.localdate()

    timetable = make_timetable("B.Tech CSE Sem 5", department, admin_user)
    first = services.create_draft(timetable, actor=admin_user)
    add_requirement(first, subjects["OS"], [teachers[0]], [section], 4, "lecture")
    add_requirement(first, subjects["DBMS"], [teachers[1]], [section], 3, "lecture")
    add_requirement(first, subjects["MATH"], [teachers[2]], [section], 4, "lecture")
    add_requirement(first, subjects["DBMS-LAB"], [teachers[1]], batches, 1, "lab", rooms_needed=2)

    solve(first, scope, admin_user)
    rows = list(Assignment.objects.filter(version=first))
    assert len(rows) == 4 * 3 + 3 * 3 + 4 * 3 + 1 * 2 * 5
    assert_no_clashes(rows)
    lab_rooms = {
        row.resource.code
        for row in rows
        if row.requirement.subject.code == "DBMS-LAB" and row.resource.kind == "room"
    }
    assert lab_rooms == {"L1", "L2"}
    assert all(
        row.serves_id is not None
        for row in rows
        if row.requirement.subject.code == "DBMS-LAB" and row.resource.kind == "room"
    )

    section_grid = grids.build_grid(first.grid, assignment_rows([first.pk]), section.pk)
    shown = {
        entry.subject for row in section_grid.rows for cell in row.cells for entry in cell.entries
    }
    assert shown == {"OS", "DBMS", "MATH", "DBMS-LAB"}

    services.publish(first, effective_from=today, actor=admin_user)
    first.refresh_from_db()
    assert first.status == "published"
    assert not Assignment.objects.filter(version=first, is_live=False).exists()
    assert services.active_version(timetable, today) == first

    before = slots_by_subject(first)

    second = services.create_draft(
        timetable, parent=first, reason="T2 left; T1 takes DBMS", actor=admin_user
    )
    assert Requirement.objects.filter(version=second).count() == 4
    dbms = Requirement.objects.get(version=second, subject=subjects["DBMS"])
    RequirementResource.objects.filter(requirement=dbms, role="teacher").update(
        resource=teachers[0]
    )
    solve(second, scope, admin_user)
    after = slots_by_subject(second)
    assert after["OS"] == before["OS"]
    assert after["MATH"] == before["MATH"]
    assert after["DBMS-LAB"] == before["DBMS-LAB"]
    assert_no_clashes(list(Assignment.objects.filter(version=second)))

    tomorrow = today + timedelta(days=1)
    services.publish(second, effective_from=tomorrow, actor=admin_user)
    first.refresh_from_db()
    assert first.status == "published"
    assert Assignment.objects.filter(version=first, is_live=True).count() == len(rows)
    assert not Assignment.objects.filter(version=second, is_live=True).exists()
    assert services.active_version(timetable, today) == first
    assert services.active_version(timetable, tomorrow) == second

    services.flip_live(tomorrow)
    assert not Assignment.objects.filter(version=first, is_live=True).exists()
    assert not Assignment.objects.filter(version=second, is_live=False).exists()
    assert Assignment.objects.filter(version=first).count() == len(rows)

    comparison = services.compare(first, second)
    assert "changes" in comparison

    other = make_timetable("B.Tech ECE Sem 3", None, admin_user)
    ece = Resource.objects.create(kind="section", code="ECE-3A", capacity=60)
    draft = services.create_draft(other, actor=admin_user)
    add_requirement(draft, subjects["OS"], [teachers[0]], [ece], 4, "lecture")
    solve(draft, scope, admin_user)
    services.publish(draft, effective_from=today, actor=admin_user)

    live = list(Assignment.objects.filter(is_live=True))
    assert_no_clashes(live)
    t1_slots = [(row.day, row.period) for row in live if row.resource_id == teachers[0].pk]
    assert len(t1_slots) == len(set(t1_slots)) == 4 + 3 + 4


def test_infeasible_input_fails_with_reasons(scope, department, admin_user, world):
    teachers = world["teachers"]
    section = world["section"]
    subjects = world["subjects"]
    teachers[0].max_load = 2
    teachers[0].save()

    timetable = make_timetable("Overloaded", department, admin_user)
    draft = services.create_draft(timetable, actor=admin_user)
    add_requirement(draft, subjects["OS"], [teachers[0]], [section], 4, "lecture")
    services.start_solve(draft, admin_user)
    draft.refresh_from_db()
    assert draft.status == "failed"
    assert draft.solver_stats["reasons"]
    assert any("T1" in reason for reason in draft.solver_stats["reasons"])
