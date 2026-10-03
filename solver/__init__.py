def solve(instance):
    from solver.model import solve as run

    return run(instance)


def validate(instance, placements):
    from solver.validate import validate as run

    return run(instance, placements)


def precheck(instance):
    from solver.precheck import precheck as run

    return run(instance)


def explain(instance):
    from solver.explain import explain as run

    return run(instance)


__all__ = ["explain", "precheck", "solve", "validate"]
