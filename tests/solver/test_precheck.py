from solver import precheck
from solver.types import Resource

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


def test_clean_instance_passes():
    assert precheck(instance(basic_resources(), [requirement("Q1", sessions=3)])) == []


def test_unknown_references_are_named():
    problem = instance(
        basic_resources(),
        [requirement("Q1", teachers=("T9",), attendees=("S9",), fixed_rooms=("R9",))],
    )
    messages = precheck(problem)
    assert "Requirement Q1 references unknown teacher T9" in messages
    assert "Requirement Q1 references unknown attendee S9" in messages
    assert "Requirement Q1 references unknown room R9" in messages


def test_wrong_kinds_and_missing_subject_are_named():
    problem = instance(
        basic_resources(),
        [requirement("Q1", teachers=("R1",), attendees=("T1",), subject=" ")],
    )
    messages = precheck(problem)
    assert "Requirement Q1 lists R1 as a teacher" in messages
    assert "Requirement Q1 lists T1 as an attendee" in messages
    assert "Requirement Q1 has no subject" in messages


def test_empty_attendees_are_named():
    messages = precheck(instance(basic_resources(), [requirement("Q1", attendees=())]))
    assert "Requirement Q1 has no attendees" in messages


def test_batch_parent_must_be_a_section():
    resources = basic_resources() + (batch("G3", "T1"), batch("G4", "ZZ"))
    messages = precheck(instance(resources, [requirement("Q1")]))
    assert "Batch G3 has parent T1 which is not a section" in messages
    assert "Batch G4 has no parent section" in messages


def test_overloaded_teacher_is_named():
    resources = (teacher("T1", max_load=5), section("S1"), room("R1"))
    messages = precheck(instance(resources, [requirement("Q1", sessions=3, length=2)]))
    assert "Teacher T1 needs 6 periods but has 5 free" in messages
    busy = frozenset(grid().slots())
    resources = (teacher("T1", unavailable=frozenset(list(busy)[:38])), section("S1"), room("R1"))
    messages = precheck(instance(resources, [requirement("Q1", sessions=3)]))
    assert "Teacher T1 needs 3 periods but has 2 free" in messages


def test_overloaded_attendee_counts_parent_sessions():
    small = grid(days=1, periods=4, breaks_after=())
    lessons = [
        requirement("Q1", sessions=3, rooms_needed=0),
        requirement("Q2", teachers=("T2",), attendees=("G1",), sessions=2, rooms_needed=0),
    ]
    messages = precheck(instance(basic_resources(), lessons, grid=small))
    assert "Batch G1 needs 5 periods (including 3 of S1) but has 4 free" in messages


def test_length_that_fits_no_block_is_named():
    small = grid(days=1, periods=3, breaks_after=(1,))
    messages = precheck(instance(basic_resources(), [requirement("Q1", length=3)], grid=small))
    assert "Requirement Q1 length 3 fits in no block" in messages


def test_fixed_slots_must_sit_inside_grid_and_block():
    lessons = [requirement("Q1", sessions=2, length=2, fixed_slots=((7, 0), (0, 1)))]
    messages = precheck(instance(basic_resources(), lessons))
    assert "Requirement Q1 fixes day 7 outside the grid" in messages
    assert any("fixes a session at day 0 period 1 that does not fit" in line for line in messages)
    too_many = [requirement("Q1", sessions=1, fixed_slots=((0, 0), (1, 0)))]
    messages = precheck(instance(basic_resources(), too_many))
    assert "Requirement Q1 fixes 2 slots but has 1 sessions" in messages


def test_fixed_slot_collisions_are_named():
    lessons = [
        requirement("Q1", fixed_slots=((0, 0),)),
        requirement("Q2", teachers=("T2",), attendees=("G1",), fixed_slots=((0, 0),)),
        requirement("Q3", attendees=("G2",), fixed_slots=((0, 0),)),
    ]
    messages = precheck(instance(basic_resources(), lessons))
    assert "S1 has fixed sessions of Q1 and Q2 and Q3 both at day 0 period 0" in messages
    assert "T1 has fixed sessions of Q1 and Q3 both at day 0 period 0" in messages


def test_room_supply_is_compared_with_demand():
    small = grid(days=1, periods=2, breaks_after=())
    lessons = [
        requirement("Q1", sessions=2),
        requirement("Q2", teachers=("T2",), attendees=("G1",), sessions=2),
    ]
    resources = (teacher("T1"), teacher("T2"), section("S1"), batch("G1", "S1"), room("R1"))
    messages = precheck(instance(resources, lessons, grid=small))
    assert (
        "Rooms tagged class with capacity >= 30 are needed for 4 periods but only 2 are free"
        in messages
    )


def test_missing_candidate_rooms_are_named():
    resources = (teacher("T1"), section("S1"), batch("G1", "S1"), batch("G2", "S1"), room("R1"))
    lab = requirement("Q1", attendees=("G1", "G2"), rooms_needed=2, room_tag="lab")
    messages = precheck(instance(resources, [lab]))
    assert (
        "Requirement Q1 needs 1 x a room tagged lab with capacity >= 30 but only 0 exist"
        in messages
    )
    one_lab = resources + (room("L1", capacity=30, tags=("lab",)),)
    messages = precheck(instance(one_lab, [lab]))
    assert "Requirement Q1 needs 2 distinct rooms but only 1 qualify" in messages


def test_fixed_room_must_qualify():
    messages = precheck(instance(basic_resources(), [requirement("Q1", fixed_rooms=("L1",))]))
    assert (
        "Fixed room L1 for requirement Q1 is not a room tagged class with capacity >= 60"
        in messages
    )


def test_participant_without_a_long_enough_free_slot_is_named():
    busy = frozenset((day, period) for day, period in grid().slots() if period % 2 == 0)
    resources = (teacher("T1", unavailable=busy), section("S1"), room("R1"))
    messages = precheck(instance(resources, [requirement("Q1", length=2)]))
    assert "T1 has no free slot of length 2 for requirement Q1" in messages


def test_blocked_unknown_resource_is_named():
    problem = instance(basic_resources(), [requirement("Q1")], blocked=frozenset({("ZZ", 0, 0)}))
    assert "Blocked slot references unknown resource ZZ" in precheck(problem)


def test_section_with_parent_is_rejected():
    resources = basic_resources() + (Resource("S2", "section", capacity=10, parent="S1"),)
    assert "Section S2 must not have a parent" in precheck(instance(resources, [requirement("Q1")]))
