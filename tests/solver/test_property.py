from dataclasses import replace

from hypothesis import HealthCheck, given, settings

from solver import explain, precheck, solve, validate
from solver.types import INFEASIBLE

from .test_support import small_instances

generous = settings(
    deadline=None,
    max_examples=25,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)


def shared_participant(first, second):
    return bool(set(first.teachers + first.attendees) & set(second.teachers + second.attendees))


@given(small_instances())
@generous
def test_solutions_pass_the_independent_validator(problem):
    result = solve(problem)
    if result.solved:
        assert validate(problem, result.placements) == []
    elif result.status == INFEASIBLE:
        assert explain(problem).status == INFEASIBLE or precheck(problem)


@given(small_instances())
@generous
def test_moving_a_session_onto_a_clash_is_detected(problem):
    result = solve(problem)
    if not result.solved:
        return
    requirements = problem.requirement_map
    placements = list(result.placements)
    for index, moved in enumerate(placements):
        for target in placements:
            if target.requirement == moved.requirement:
                continue
            if not shared_participant(
                requirements[moved.requirement], requirements[target.requirement]
            ):
                continue
            if target.start not in problem.grid.starts_for(requirements[moved.requirement].length):
                continue
            clashed = list(placements)
            clashed[index] = replace(moved, day=target.day, start=target.start)
            violations = validate(problem, clashed)
            assert violations
            assert any("double booked" in line or "both booked" in line for line in violations)
            return


@given(small_instances())
@generous
def test_explain_names_what_the_solver_could_not_place(problem):
    result = solve(problem)
    if result.status != INFEASIBLE:
        return
    explanation = explain(problem)
    if explanation.status != INFEASIBLE:
        return
    assert explanation.unplaced
    for requirement_id, missing in explanation.unplaced:
        assert any(
            f"Could not place {missing} of" in reason and requirement_id in problem.requirement_map
            for reason in explanation.reasons
        )
