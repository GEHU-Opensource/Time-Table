from datetime import timedelta

import pytest
from django.utils import timezone

from core.tenancy import require_tenant_id
from solver.types import FEASIBLE, INFEASIBLE, UNKNOWN, Grid, Instance, Requirement, Result
from tests.test_services import GRID, solved_result, world
from timetable import bridge, sandbox, services, tasks
from timetable.models import Assignment, Version

__all__ = ["world"]


def test_solve_version_task_calls_run_solve(monkeypatch):
    calls = []
    monkeypatch.setattr(
        services, "run_solve", lambda version_id, tenant_id: calls.append((version_id, tenant_id))
    )
    tasks.solve_version(version_id="v", tenant_id="t")
    assert calls == [("v", "t")]
    assert tasks.solve_version.name == "timetable.solve_version"
    assert tasks.solve_version.retry_strategy is None


def test_full_round_trip_ends_in_draft_with_rows(world, monkeypatch):
    monkeypatch.setenv(sandbox.INLINE_ENV, "1")
    seen = []

    def fake_solve(instance):
        seen.append(instance)
        return solved_result(world)

    monkeypatch.setattr(bridge, "solve_instance", fake_solve)
    version = services.start_solve(world["draft"], world["actor"])
    assert version.status == Version.Status.SOLVING
    tasks.solve_version(version_id=str(version.pk), tenant_id=str(require_tenant_id()))
    version.refresh_from_db()
    assert version.status == Version.Status.DRAFT
    assert Assignment.objects.filter(version=version).count() == 11
    assert len(seen) == 1
    assert seen[0].seed == version.number
    assert version.solver_stats["wall_seconds"] == 1.5
    assert version.solver_stats["status"] == FEASIBLE


def test_run_solve_skips_versions_not_solving(world, monkeypatch):
    monkeypatch.setenv(sandbox.INLINE_ENV, "1")

    def boom(instance):
        raise AssertionError("solver must not run")

    monkeypatch.setattr(bridge, "solve_instance", boom)
    assert services.run_solve(str(world["draft"].pk), str(require_tenant_id())) is None
    world["draft"].refresh_from_db()
    assert world["draft"].status == Version.Status.DRAFT


def test_inline_sandbox_turns_exceptions_into_crash_result(monkeypatch):
    monkeypatch.setenv(sandbox.INLINE_ENV, "1")

    def boom(instance):
        raise RuntimeError("bad model")

    monkeypatch.setattr(bridge, "solve_instance", boom)
    result = sandbox.run(Instance(grid=Grid.from_json(GRID), resources=(), requirements=()))
    assert result.status == UNKNOWN
    assert result.reasons == ("solver crashed",)


def test_spawned_sandbox_returns_a_result_for_a_broken_instance(monkeypatch):
    monkeypatch.delenv(sandbox.INLINE_ENV, raising=False)
    ghost = Requirement(
        "q", "GHOST", length=1, sessions=1, teachers=("nobody",), attendees=("none",)
    )
    instance = Instance(
        grid=Grid.from_json(GRID), resources=(), requirements=(ghost,), max_seconds=5, workers=1
    )
    result = sandbox.run(instance)
    assert isinstance(result, Result)
    assert result.status in {UNKNOWN, INFEASIBLE}
    assert not result.placements


def test_periodic_tasks_cover_live_tenants(world, monkeypatch):
    flips, resets = [], []
    monkeypatch.setattr(services, "flip_live", lambda on: flips.append((require_tenant_id(), on)))
    monkeypatch.setattr(
        services, "reset_stale_solving", lambda now: resets.append((require_tenant_id(), now))
    )
    stamp = int(timezone.now().timestamp())
    tasks.flip_live_all(timestamp=stamp)
    tasks.reset_stale_all(timestamp=stamp)
    tenant_id = require_tenant_id()
    assert flips == [(tenant_id, timezone.localdate())]
    assert len(resets) == 1 and resets[0][0] == tenant_id
    assert timezone.now() - resets[0][1] < timedelta(seconds=5)


def test_periodic_tasks_are_registered():
    registered = {
        periodic.task.name for periodic in tasks.app.periodic_registry.periodic_tasks.values()
    }
    assert {"timetable.flip_live_all", "timetable.reset_stale_all"} <= registered
    assert "timetable.solve_version" in tasks.app.tasks


@pytest.mark.parametrize("status", [FEASIBLE, UNKNOWN])
def test_result_solved_flag(status):
    assert Result(status=status).solved == (status == FEASIBLE)
