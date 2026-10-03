from solver import explain, solve
from solver.types import INFEASIBLE, TOO_LARGE

from .test_support import basic_resources, grid, instance, requirement, room, section, teacher


def test_explain_names_the_unplaced_requirement():
    small = grid(days=1, periods=2, breaks_after=())
    resources = (
        teacher("T1"),
        teacher("T2", unavailable=frozenset({(0, 0), (0, 1)})),
        section("S1"),
        section("S2"),
        room("R1"),
        room("R2"),
    )
    lessons = [
        requirement("Q1", subject="DS", sessions=2),
        requirement("Q2", subject="OS", teachers=("T2",), attendees=("S2",), sessions=2),
    ]
    problem = instance(resources, lessons, grid=small)
    assert solve(problem).status == INFEASIBLE
    result = explain(problem)
    assert result.status == INFEASIBLE
    assert result.unplaced == (("Q2", 2),)
    assert result.reasons == ("Could not place 2 of 2 sessions of OS for S2 with T2",)
    assert {placement.requirement for placement in result.placements} == {"Q1"}


def test_explain_reports_partial_placement_counts():
    small = grid(days=1, periods=3, breaks_after=())
    resources = (teacher("T1"), section("S1"), room("R1"))
    problem = instance(resources, [requirement("Q1", subject="Maths", sessions=5)], grid=small)
    result = explain(problem)
    assert result.status == INFEASIBLE
    assert result.unplaced == (("Q1", 2),)
    assert result.reasons == ("Could not place 2 of 5 sessions of Maths for S1 with T1",)
    assert len(result.placements) == 3


def test_explain_on_feasible_instance_places_everything():
    problem = instance(basic_resources(), [requirement("Q1", sessions=2)])
    result = explain(problem)
    assert result.solved
    assert result.unplaced == ()
    assert result.reasons == ()
    assert len(result.placements) == 2


def test_explain_respects_the_size_guard():
    problem = instance(basic_resources(), [requirement("Q1")], max_model_size=1)
    assert explain(problem).status == TOO_LARGE


def test_explain_reports_unknown_references():
    result = explain(instance(basic_resources(), [requirement("Q1", attendees=("S9",))]))
    assert result.status == INFEASIBLE
    assert "S9" in result.reasons[0]
