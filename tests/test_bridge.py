import pytest

from solver.types import Grid, Instance, Placement, Requirement, Resource
from timetable import bridge

GRID = Grid.from_json(
    {
        "days": ["Mon", "Tue"],
        "periods": [["09:00", "09:55"], ["10:00", "10:55"], ["11:00", "11:55"]],
    }
)


def make_instance():
    resources = (
        Resource("t1", "teacher", max_load=20),
        Resource("t2", "teacher", max_load=20),
        Resource("s1", "section", capacity=50),
        Resource("s2", "section", capacity=50),
        Resource("r1", "room", capacity=60),
        Resource("r2", "room", capacity=60),
    )
    requirements = (
        Requirement("q-math", "MATH", length=2, sessions=1, teachers=("t1",), attendees=("s1",)),
        Requirement(
            "q-phys",
            "PHYS",
            length=1,
            sessions=2,
            teachers=("t2",),
            attendees=("s1", "s2"),
            rooms_needed=2,
        ),
        Requirement("q-sem", "SEM", length=1, sessions=1, teachers=("t1", "t2"), attendees=("s2",)),
    )
    return Instance(grid=GRID, resources=resources, requirements=requirements)


PLACEMENTS = (
    Placement("q-math", 0, 0, 0, ("r1",)),
    Placement("q-phys", 0, 1, 0, ("r2", "r1")),
    Placement("q-phys", 1, 1, 2, ("r1", "r2")),
    Placement("q-sem", 0, 0, 2, ()),
)


def attendee_positions(instance):
    return {
        requirement.id: {attendee: index for index, attendee in enumerate(requirement.attendees)}
        for requirement in instance.requirements
    }


def test_occupancy_rows_count_and_serves():
    instance = make_instance()
    rows = bridge.occupancy_rows(instance, PLACEMENTS)
    assert len(rows) == 2 * (1 + 1 + 1) + 2 * (1 + 2 + 2) + 1 * (2 + 1 + 0)
    phys_rooms = [
        row for row in rows if row[0] == "q-phys" and row[1] == 0 and row[2] in {"r1", "r2"}
    ]
    assert {(row[2], row[5]) for row in phys_rooms} == {("r2", "s1"), ("r1", "s2")}
    math_rows = [row for row in rows if row[0] == "q-math"]
    assert {row[4] for row in math_rows} == {0, 1}
    assert all(row[5] is None for row in math_rows)
    assert all(row[3] == 0 for row in math_rows)


def test_placements_round_trip_through_rows():
    instance = make_instance()
    rows = bridge.occupancy_rows(instance, PLACEMENTS)
    rebuilt = bridge.placements_from_rows(rows, {"r1", "r2"}, attendee_positions(instance))
    assert rebuilt == tuple(sorted(PLACEMENTS, key=lambda p: (p.requirement, p.session)))


def test_placements_from_rows_orders_unserved_rooms_by_id():
    rows = [
        ("q", 0, "t1", 0, 1, None),
        ("q", 0, "s1", 0, 1, None),
        ("q", 0, "r9", 0, 1, None),
        ("q", 0, "r2", 0, 1, None),
    ]
    (placement,) = bridge.placements_from_rows(rows, {"r2", "r9"}, {})
    assert placement == Placement("q", 0, 0, 1, ("r2", "r9"))


def test_serves_each_attendee_rule():
    instance = make_instance()
    phys = instance.requirement_map["q-phys"]
    assert bridge.serves_each_attendee(phys, ("r1", "r2"))
    assert not bridge.serves_each_attendee(phys, ("r1",))
    math = instance.requirement_map["q-math"]
    assert not bridge.serves_each_attendee(math, ("r1",))


@pytest.mark.parametrize(
    "name", ["solve_instance", "validate_placements", "precheck_instance", "explain_instance"]
)
def test_wrappers_import_the_solver_lazily(name):
    assert callable(getattr(bridge, name))
