from solver import solve, validate
from solver.types import FEASIBLE, INFEASIBLE, OPTIMAL, TOO_LARGE, Placement

from .test_support import (
    basic_resources,
    batch,
    grid,
    instance,
    placement_map,
    requirement,
    room,
    section,
    teacher,
)


def solved(result):
    assert result.status in {OPTIMAL, FEASIBLE}, result
    return placement_map(result.placements)


def test_basic_instance_solves_and_validates():
    problem = instance(basic_resources(), [requirement("Q1", sessions=3), requirement("Q2")])
    result = solve(problem)
    placements = solved(result)
    assert len(placements) == 4
    assert validate(problem, result.placements) == []


def test_sessions_never_cross_a_break():
    small = grid(days=1, periods=3, breaks_after=(1,))
    problem = instance(basic_resources(), [requirement("Q1", length=2)], grid=small)
    placements = solved(solve(problem))
    assert placements["Q1", 0].start == 0


def test_long_session_that_fits_no_block_is_infeasible():
    small = grid(days=1, periods=3, breaks_after=(1,))
    problem = instance(basic_resources(), [requirement("Q1", length=3)], grid=small)
    assert solve(problem).status == INFEASIBLE


def test_teacher_cannot_be_in_two_places():
    small = grid(days=1, periods=2, breaks_after=())
    resources = basic_resources() + (section("S2"),)
    two = [requirement("Q1"), requirement("Q2", attendees=("S2",))]
    placements = solved(solve(instance(resources, two, grid=small)))
    assert placements["Q1", 0].start != placements["Q2", 0].start
    three = two + [requirement("Q3", attendees=("S2",))]
    assert solve(instance(resources + (section("S3"),), three, grid=small)).status == INFEASIBLE


def test_section_cannot_attend_two_sessions_at_once():
    small = grid(days=1, periods=2, breaks_after=())
    resources = basic_resources() + (teacher("T3"),)
    three = [
        requirement("Q1"),
        requirement("Q2", teachers=("T2",)),
        requirement("Q3", teachers=("T3",)),
    ]
    assert solve(instance(resources, three, grid=small)).status == INFEASIBLE
    assert solved(solve(instance(resources, three[:2], grid=small)))


def test_batch_excludes_its_section_but_not_its_sibling():
    small = grid(days=1, periods=1, breaks_after=())
    resources = basic_resources() + (teacher("T3"),)
    siblings = [
        requirement("Q1", attendees=("G1",), rooms_needed=0),
        requirement("Q2", teachers=("T2",), attendees=("G2",), rooms_needed=0),
    ]
    placements = solved(solve(instance(resources, siblings, grid=small)))
    assert placements["Q1", 0].start == placements["Q2", 0].start == 0
    with_parent = siblings + [requirement("Q3", teachers=("T3",), rooms_needed=0)]
    assert solve(instance(resources, with_parent, grid=small)).status == INFEASIBLE


def test_single_room_must_hold_all_attendees():
    resources = (teacher("T1"), section("S1", capacity=60), room("R1", capacity=30))
    assert solve(instance(resources, [requirement("Q1")])).status == INFEASIBLE
    bigger = (teacher("T1"), section("S1", capacity=60), room("R1", capacity=60))
    assert solved(solve(instance(bigger, [requirement("Q1")])))["Q1", 0].rooms == ("R1",)


def test_split_rooms_serve_attendees_positionally():
    resources = (
        teacher("T1"),
        section("S1"),
        batch("G1", "S1", capacity=30),
        batch("G2", "S1", capacity=50),
        room("L1", capacity=30, tags=("lab",)),
        room("L2", capacity=50, tags=("lab",)),
    )
    lab = requirement("Q1", attendees=("G1", "G2"), rooms_needed=2, room_tag="lab", length=2)
    placements = solved(solve(instance(resources, [lab])))
    assert placements["Q1", 0].rooms == ("L1", "L2")
    too_small = resources[:-1] + (room("L2", capacity=30, tags=("lab",)),)
    assert solve(instance(too_small, [lab])).status == INFEASIBLE


def test_room_tag_is_required():
    resources = (teacher("T1"), section("S1"), room("R1"))
    assert solve(instance(resources, [requirement("Q1", room_tag="lab")])).status == INFEASIBLE
    assert solved(solve(instance(resources, [requirement("Q1", room_tag=None)])))


def test_fixed_rooms_are_used():
    problem = instance(basic_resources(), [requirement("Q1", fixed_rooms=("R2",), sessions=2)])
    placements = solved(solve(problem))
    assert all(placement.rooms == ("R2",) for placement in placements.values())


def test_no_room_when_rooms_needed_is_zero():
    problem = instance(basic_resources(), [requirement("Q1", rooms_needed=0)])
    assert solved(solve(problem))["Q1", 0].rooms == ()


def test_fixed_slots_pin_the_first_sessions():
    pinned = requirement("Q1", sessions=3, fixed_slots=((2, 3), (4, 6)))
    problem = instance(basic_resources(), [pinned])
    placements = solved(solve(problem))
    assert (placements["Q1", 0].day, placements["Q1", 0].start) == (2, 3)
    assert (placements["Q1", 1].day, placements["Q1", 1].start) == (4, 6)
    assert validate(problem, tuple(placements.values())) == []


def test_fixed_slot_outside_a_block_is_infeasible():
    pinned = requirement("Q1", length=2, fixed_slots=((0, 1),))
    assert solve(instance(basic_resources(), [pinned])).status == INFEASIBLE


def test_unavailable_slots_are_avoided():
    free = (3, 5)
    busy = frozenset(slot for slot in grid().slots() if slot != free)
    resources = (teacher("T1", unavailable=busy), section("S1"), room("R1"))
    placement = solved(solve(instance(resources, [requirement("Q1")])))["Q1", 0]
    assert (placement.day, placement.start) == free


def test_blocked_slots_apply_to_participants_and_rooms():
    blocked = frozenset({("R1", day, period) for day, period in grid().slots()})
    problem = instance(basic_resources(), [requirement("Q1")], blocked=blocked)
    assert solved(solve(problem))["Q1", 0].rooms == ("R2",)
    teacher_blocked = frozenset({("T1", day, period) for day, period in grid().slots()})
    assert (
        solve(instance(basic_resources(), [requirement("Q1")], blocked=teacher_blocked)).status
        == INFEASIBLE
    )


def test_teacher_max_load_is_hard():
    resources = (teacher("T1", max_load=2), section("S1"), room("R1"))
    assert solve(instance(resources, [requirement("Q1", sessions=3)])).status == INFEASIBLE
    enough = (teacher("T1", max_load=3), section("S1"), room("R1"))
    assert solved(solve(instance(enough, [requirement("Q1", sessions=3)])))


def test_sessions_spread_over_distinct_days_and_are_ordered():
    problem = instance(basic_resources(), [requirement("Q1", sessions=4)])
    placements = solved(solve(problem))
    days = [placements["Q1", index].day for index in range(4)]
    assert len(set(days)) == 4
    keys = [(placements["Q1", index].day, placements["Q1", index].start) for index in range(4)]
    assert keys == sorted(keys)


def test_more_sessions_than_days_share_days_evenly():
    problem = instance(basic_resources(), [requirement("Q1", sessions=7)])
    result = solve(problem)
    placements = solved(result)
    per_day = {}
    for placement in placements.values():
        per_day[placement.day] = per_day.get(placement.day, 0) + 1
    assert max(per_day.values()) <= 2
    assert validate(problem, result.placements) == []


def test_preferred_slots_attract_the_session():
    resources = (teacher("T1", preferred=frozenset({(3, 5)})), section("S1"), room("R1"))
    result = solve(instance(resources, [requirement("Q1")]))
    placement = solved(result)["Q1", 0]
    assert (placement.day, placement.start) == (3, 5)
    assert result.stats["objective"] == -1


def test_gaps_between_sessions_are_closed():
    one_day = grid(days=1, periods=6, breaks_after=())
    resources = (
        teacher("T1"),
        teacher("T2"),
        section("S1"),
        batch("G1", "S1"),
        room("R1"),
        room("R2"),
    )
    lessons = [requirement("Q1"), requirement("Q2", teachers=("T2",), attendees=("G1",))]
    result = solve(instance(resources, lessons, grid=one_day))
    placements = solved(result)
    assert abs(placements["Q1", 0].start - placements["Q2", 0].start) == 1
    assert result.stats["objective"] == 0


def test_hints_are_kept_when_still_feasible():
    problem = instance(
        basic_resources(), [requirement("Q1", sessions=3), requirement("Q2", sessions=2)], seed=3
    )
    first = solve(problem)
    hinted = instance(
        basic_resources(),
        problem.requirements,
        hints=first.placements,
        seed=11,
    )
    second = solve(hinted)
    assert placement_map(second.placements) == placement_map(first.placements)
    assert second.stats["objective"] == first.stats["objective"]


def test_hints_move_only_the_disturbed_session():
    lessons = [requirement("Q1", sessions=3), requirement("Q2", teachers=("T2",), sessions=2)]
    problem = instance(basic_resources(), lessons, seed=5)
    first = placement_map(solve(problem).placements)
    victim = first["Q1", 1]
    resources = tuple(
        teacher("T1", unavailable=frozenset({(victim.day, victim.start)}))
        if resource.id == "T1"
        else resource
        for resource in basic_resources()
    )
    second = solve(instance(resources, lessons, hints=tuple(first.values()), seed=5))
    placements = solved(second)
    moved = [key for key, placement in placements.items() if first[key] != placement]
    assert moved == [("Q1", 1)]
    assert (placements["Q1", 1].day, placements["Q1", 1].start) != (victim.day, victim.start)


def test_too_large_guard_refuses_before_building():
    problem = instance(basic_resources(), [requirement("Q1", sessions=3)], max_model_size=10)
    result = solve(problem)
    assert result.status == TOO_LARGE
    assert "booleans" in result.reasons[0]
    assert result.stats["booleans"] > 10


def test_stats_describe_the_run():
    problem = instance(basic_resources(), [requirement("Q1")], seed=42, workers=2, max_seconds=7)
    stats = solve(problem).stats
    assert set(stats) >= {
        "status",
        "objective",
        "wall_time",
        "num_conflicts",
        "num_branches",
        "booleans",
        "ortools",
        "seed",
        "workers",
        "max_seconds",
    }
    assert (stats["seed"], stats["workers"], stats["max_seconds"]) == (42, 2, 7)


def test_unknown_resource_is_reported_not_raised():
    problem = instance(basic_resources(), [requirement("Q1", teachers=("T9",))])
    result = solve(problem)
    assert result.status == INFEASIBLE
    assert "T9" in result.reasons[0]


def test_placements_are_placement_objects():
    result = solve(instance(basic_resources(), [requirement("Q1")]))
    assert all(isinstance(placement, Placement) for placement in result.placements)
