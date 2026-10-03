from solver.model import Build, estimate_booleans
from solver.precheck import reference_errors
from solver.types import FEASIBLE, INFEASIBLE, OPTIMAL, TOO_LARGE, Result


def describe_unplaced(requirement, missing):
    attendees = ", ".join(requirement.attendees)
    teachers = ", ".join(requirement.teachers)
    with_teachers = f" with {teachers}" if teachers else ""
    return (
        f"Could not place {missing} of {requirement.sessions} sessions of "
        f"{requirement.subject} for {attendees}{with_teachers}"
    )


def explain(instance):
    errors = reference_errors(instance)
    if errors:
        return Result(status=INFEASIBLE, reasons=tuple(errors))
    estimate = estimate_booleans(instance)
    if estimate > instance.max_model_size:
        return Result(
            status=TOO_LARGE,
            reasons=(
                f"Model needs about {estimate} booleans, above the limit of "
                f"{instance.max_model_size}",
            ),
            stats={"booleans": estimate},
        )
    build = Build(instance, relaxed=True)
    solver, status = build.run()
    stats = build.stats(solver, status)
    if status not in {OPTIMAL, FEASIBLE}:
        return Result(status=status, stats=stats)
    placements = build.placements(solver)
    placed_count = {}
    for placement in placements:
        placed_count[placement.requirement] = placed_count.get(placement.requirement, 0) + 1
    unplaced, reasons = [], []
    for requirement in instance.requirements:
        missing = requirement.sessions - placed_count.get(requirement.id, 0)
        if missing > 0:
            unplaced.append((requirement.id, missing))
            reasons.append(describe_unplaced(requirement, missing))
    if unplaced:
        status = INFEASIBLE
    return Result(
        status=status,
        placements=placements,
        unplaced=tuple(unplaced),
        reasons=tuple(reasons),
        stats=stats,
    )
