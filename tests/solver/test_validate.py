from dataclasses import replace

import pytest

from solver import validate
from solver.types import Placement

from .test_support import (
    basic_resources,
    batch,
    grid,
    instance,
    requirement,
    room,
    section,
    teacher,
)


def lessons():
    return [
        requirement("Q1", sessions=2),
        requirement("Q2", teachers=("T2",), attendees=("G1",), rooms_needed=0),
        requirement(
            "Q3", teachers=("T2",), attendees=("G1", "G2"), rooms_needed=2, room_tag="lab", length=2
        ),
    ]


def good_placements():
    return (
        Placement("Q1", 0, 0, 0, ("R1",)),
        Placement("Q1", 1, 1, 2, ("R1",)),
        Placement("Q2", 0, 0, 2, ()),
        Placement("Q3", 0, 2, 4, ("L1", "L2")),
    )


def problem(**overrides):
    return instance(basic_resources(), lessons(), **overrides)


def swap(placements, index, **changes):
    placements = list(placements)
    placements[index] = replace(placements[index], **changes)
    return tuple(placements)


def test_valid_solution_has_no_violations():
    assert validate(problem(), good_placements()) == []


def test_missing_session_is_reported():
    violations = validate(problem(), good_placements()[1:])
    assert any("Q1 has 1 placed sessions, expected 2" in line for line in violations)


def test_repeated_session_number_is_reported():
    violations = validate(problem(), swap(good_placements(), 1, session=0))
    assert any("repeats a session number" in line for line in violations)


def test_unknown_requirement_is_reported():
    violations = validate(problem(), good_placements() + (Placement("ZZ", 0, 0, 0, ()),))
    assert any("unknown requirement ZZ" in line for line in violations)


def test_session_outside_grid_is_reported():
    violations = validate(problem(), swap(good_placements(), 0, day=9))
    assert any("Q1 session 0 is on day 9" in line for line in violations)
    violations = validate(problem(), swap(good_placements(), 3, start=7))
    assert any("runs past the grid" in line for line in violations)


def test_session_crossing_a_break_is_reported():
    violations = validate(problem(), swap(good_placements(), 3, start=1))
    assert any("crosses a break" in line for line in violations)


def test_teacher_double_booking_is_reported():
    violations = validate(problem(), swap(good_placements(), 1, day=0, start=0))
    assert any("T1 is double booked at Mon 09:00" in line for line in violations)


def test_room_double_booking_is_reported():
    extra = instance(
        basic_resources(), lessons() + [requirement("Q4", teachers=("T2",), attendees=("S1",))]
    )
    placements = good_placements()[:2] + (
        Placement("Q2", 0, 3, 0, ()),
        Placement("Q3", 0, 2, 4, ("L1", "L2")),
        Placement("Q4", 0, 0, 0, ("R1",)),
    )
    violations = validate(extra, placements)
    assert any("R1 is double booked" in line for line in violations)
    assert any("S1 is double booked" in line for line in violations)


def test_batch_and_section_clash_is_reported():
    violations = validate(problem(), swap(good_placements(), 2, day=0, start=0))
    assert any("G1 and its section S1 are both booked at Mon 09:00" in line for line in violations)


def test_sibling_batches_may_overlap():
    siblings = instance(
        basic_resources(),
        [
            requirement("Q1", attendees=("G1",), rooms_needed=0),
            requirement("Q2", teachers=("T2",), attendees=("G2",), rooms_needed=0),
        ],
    )
    placements = (Placement("Q1", 0, 0, 0, ()), Placement("Q2", 0, 0, 0, ()))
    assert validate(siblings, placements) == []


def test_room_count_and_existence_are_checked():
    violations = validate(problem(), swap(good_placements(), 0, rooms=()))
    assert any("has 0 rooms, needs 1" in line for line in violations)
    violations = validate(problem(), swap(good_placements(), 0, rooms=("R9",)))
    assert any("unknown room R9" in line for line in violations)
    violations = validate(problem(), swap(good_placements(), 0, rooms=("T1",)))
    assert any("T1 which is not a room" in line for line in violations)


def test_room_tag_and_capacity_are_checked():
    violations = validate(problem(), swap(good_placements(), 3, rooms=("R1", "R2")))
    assert any("not tagged lab" in line for line in violations)
    violations = validate(problem(), swap(good_placements(), 0, rooms=("L1",)))
    assert any("needs capacity 60 but L1 holds 30" in line for line in violations)


def test_split_rooms_are_checked_per_attendee():
    resources = basic_resources() + (batch("G3", "S1", capacity=50),)
    lab = requirement(
        "Q3", teachers=("T2",), attendees=("G1", "G3"), rooms_needed=2, room_tag="lab", length=2
    )
    violations = validate(instance(resources, [lab]), (Placement("Q3", 0, 0, 0, ("L1", "L2")),))
    assert any("puts G3 (50) in L2 (30)" in line for line in violations)
    violations = validate(instance(resources, [lab]), (Placement("Q3", 0, 0, 0, ("L1", "L1")),))
    assert any("same room twice" in line for line in violations)


def test_fixed_rooms_are_checked():
    pinned = instance(basic_resources(), [requirement("Q1", fixed_rooms=("R2",))])
    violations = validate(pinned, (Placement("Q1", 0, 0, 0, ("R1",)),))
    assert any("must use fixed room R2" in line for line in violations)
    split = instance(
        basic_resources(),
        [
            requirement(
                "Q3",
                teachers=("T2",),
                attendees=("G1", "G2"),
                rooms_needed=2,
                room_tag="lab",
                length=2,
                fixed_rooms=("L2",),
            )
        ],
    )
    violations = validate(split, (Placement("Q3", 0, 0, 0, ("L1", "L2")),))
    assert any("must use L2 for G1" in line for line in violations)


def test_fixed_slots_are_checked():
    pinned = instance(basic_resources(), [requirement("Q1", fixed_slots=((2, 3),))])
    assert validate(pinned, (Placement("Q1", 0, 2, 3, ("R1",)),)) == []
    violations = validate(pinned, (Placement("Q1", 0, 2, 2, ("R1",)),))
    assert any("must be at day 2 period 3" in line for line in violations)


def test_unavailable_and_blocked_are_checked():
    resources = tuple(
        teacher("T1", unavailable=frozenset({(0, 0)})) if resource.id == "T1" else resource
        for resource in basic_resources()
    )
    violations = validate(instance(resources, lessons()), good_placements())
    assert any("T1 is unavailable at Mon 09:00" in line for line in violations)
    violations = validate(problem(blocked=frozenset({("R1", 0, 0)})), good_placements())
    assert any("R1 is blocked at Mon 09:00" in line for line in violations)
    violations = validate(problem(blocked=frozenset({("L2", 2, 5)})), good_placements())
    assert any("L2 is blocked at Wed 14:15" in line for line in violations)


def test_teacher_load_is_checked():
    resources = tuple(
        teacher("T1", max_load=1) if resource.id == "T1" else resource
        for resource in basic_resources()
    )
    violations = validate(instance(resources, lessons()), good_placements())
    assert any("T1 teaches 2 periods, above the load limit of 1" in line for line in violations)


def test_sessions_per_day_rule_is_checked():
    violations = validate(problem(), swap(good_placements(), 1, day=0, start=5))
    assert any("Q1 has 2 sessions on Mon, at most 1 allowed" in line for line in violations)
    crowded = instance(basic_resources(), [requirement("Q1", sessions=7)])
    placements = tuple(
        Placement("Q1", index, index % 5, 2 * (index // 5), ("R1",)) for index in range(7)
    )
    assert validate(crowded, placements) == []
    placements = tuple(Placement("Q1", index, 0, index, ("R1",)) for index in range(7))
    violations = validate(crowded, placements)
    assert any("Q1 has 7 sessions on Mon, at most 2 allowed" in line for line in violations)


@pytest.mark.parametrize("periods", [3, 4])
def test_single_block_grid_accepts_full_length_sessions(periods):
    single = grid(days=1, periods=periods, breaks_after=())
    resources = (teacher("T1"), section("S1"), room("R1"))
    problem_grid = instance(resources, [requirement("Q1", length=periods)], grid=single)
    assert validate(problem_grid, (Placement("Q1", 0, 0, 0, ("R1",)),)) == []
