import json
import time

from solver import precheck, solve, validate

from .test_support import FIXTURES, load_fixture


def test_fixture_holds_only_pseudonyms():
    with (FIXTURES / "cse_section.json").open() as handle:
        text = handle.read()
    data = json.loads(text)
    for resource in data["resources"]:
        assert resource["id"].split("-")[0][:1] in {"T", "R", "L", "S"}
    assert "Mr." not in text and "Ms." not in text
    assert all(len(requirement["teachers"]) >= 1 for requirement in data["requirements"])


def test_cse_section_solves_within_twenty_seconds_and_validates():
    problem = load_fixture("cse_section.json")
    assert precheck(problem) == []
    started = time.monotonic()
    result = solve(problem)
    elapsed = time.monotonic() - started
    assert result.solved, result
    assert elapsed < 20
    assert result.stats["wall_time"] < 20
    assert validate(problem, result.placements) == []
    assert len(result.placements) == sum(
        requirement.sessions for requirement in problem.requirements
    )


def test_cse_section_labs_land_in_distinct_free_labs():
    problem = load_fixture("cse_section.json")
    result = solve(problem)
    labs = [placement for placement in result.placements if len(placement.rooms) == 2]
    assert len(labs) == 3
    for placement in labs:
        assert len(set(placement.rooms)) == 2
        assert all(room.startswith("L") for room in placement.rooms)
        for room in placement.rooms:
            for period in range(placement.start, placement.start + 2):
                assert (room, placement.day, period) not in problem.blocked
