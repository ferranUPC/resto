"""`run_simulation` / `run_ephemeral` (E2.1, ADR-0017; ADR-0031) with a fake runner: identity,
dedupe on ok results only, a failed run returned but never stored, ephemeral runs unable to
store."""

from __future__ import annotations

from pathlib import Path

import pytest

from resto.adapters.persistence.memory import InMemoryResultRepository
from resto.adapters.sumo.run_directories import FilesystemRunDirectories
from resto.application.ports.sumo import RunOutput
from resto.application.use_cases.run_simulation import (
    attempt_dir,
    run_ephemeral,
    run_simulation,
)
from resto.domain.constants import SUMO_VERSION
from resto.domain.entities.scenario import Scenario
from resto.domain.entities.simulation_result import RunMode, RunStatus
from resto.domain.services.ids import result_id_for
from resto.domain.value_objects.kpis import Kpis
from resto.domain.value_objects.mechanism import StaticFileMechanism
from tests.unit.application._doubles import FakeRunner
from tests.unit.domain._fixtures import artifact, static_intervention
from tests.unit.domain._samples import scenario as online_scenario

RUN_DIRS = FilesystemRunDirectories()
KPIS = Kpis(mean_delay=24.4, mean_travel_time=85.4, teleports=0, departed=50, arrived=43)


def batch_scenario() -> Scenario:
    return Scenario(
        scenario_id="s-batch",
        network_id="abc123",
        demand_id="t1",
        interventions=(static_intervention(),),
        mechanisms=(StaticFileMechanism(file_kind="rerouter", path=Path("r.add.xml")),),
        sumocfg=artifact("s.sumocfg", "c1", "sumocfg"),
        content_hash="c1",
    )


def ok_output(digest: str = "ed1") -> RunOutput:
    return RunOutput(
        ok=True,
        error=None,
        artifacts=(
            artifact("run.sumocfg", "cfg1", "sumocfg"),
            artifact("edgedata.xml", digest, "edgedata"),
            artifact("statistics.xml", "st-with-clock", "statistics"),
        ),
        wall_clock_s=1.5,
        kpis=KPIS,
    )


def failed_output() -> RunOutput:
    return RunOutput(
        ok=False,
        error="Error: The edge 'NOPE' within the route is not known.",
        artifacts=(artifact("run.sumocfg", "cfg1", "sumocfg"),),
        wall_clock_s=0.1,
    )


def test_result_id_is_the_request_hash_and_the_run_goes_to_its_own_directory(
    tmp_path: Path,
) -> None:
    runner = FakeRunner([ok_output()])
    results = InMemoryResultRepository()

    result = run_simulation(
        batch_scenario(),
        7,
        runner=runner,
        results=results,
        run_dirs=RUN_DIRS,
        out_dir=tmp_path,
        attempt="study-1",
    )

    expected_id = result_id_for("s-batch", 7, RunMode.BATCH.value, SUMO_VERSION)
    assert result.result_id == expected_id
    assert runner.calls == [
        (batch_scenario().sumocfg, 7, attempt_dir(tmp_path, expected_id, "study-1"))
    ]
    assert result.status is RunStatus.OK
    assert result.kpis == KPIS
    assert result.wall_clock_s == 1.5
    assert result.sumo_version == SUMO_VERSION
    assert results.get(expected_id) == result
    assert (tmp_path / expected_id).is_dir()  # promoted from the staging directory


def test_an_existing_ok_result_is_returned_without_running_sumo(tmp_path: Path) -> None:
    runner = FakeRunner([ok_output()])
    results = InMemoryResultRepository()
    first = run_simulation(
        batch_scenario(),
        7,
        runner=runner,
        results=results,
        run_dirs=RUN_DIRS,
        out_dir=tmp_path,
        attempt="study-1",
    )

    second = run_simulation(
        batch_scenario(),
        7,
        runner=runner,
        results=results,
        run_dirs=RUN_DIRS,
        out_dir=tmp_path,
        attempt="study-2",
    )

    assert second == first
    assert len(runner.calls) == 1


def test_a_failed_run_is_returned_but_not_stored_and_the_retry_stores_the_ok_one(
    tmp_path: Path,
) -> None:
    runner = FakeRunner([failed_output(), ok_output()])
    results = InMemoryResultRepository()

    failed = run_simulation(
        batch_scenario(),
        7,
        runner=runner,
        results=results,
        run_dirs=RUN_DIRS,
        out_dir=tmp_path,
        attempt="study-1",
    )
    assert failed.status is RunStatus.FAILED
    assert failed.error is not None and "NOPE" in failed.error
    assert failed.kpis is None
    assert results.get(failed.result_id) is None  # a failed run is never stored (ADR-0031)

    retried = run_simulation(
        batch_scenario(),
        7,
        runner=runner,
        results=results,
        run_dirs=RUN_DIRS,
        out_dir=tmp_path,
        attempt="study-2",
    )

    assert retried.status is RunStatus.OK
    assert retried.result_id == failed.result_id
    assert results.get(failed.result_id) == retried
    assert len(runner.calls) == 2

    failed_dir = attempt_dir(tmp_path, failed.result_id, "study-1")
    assert failed_dir.is_dir()  # the failed attempt's own directory survives the retry
    assert (tmp_path / failed.result_id).is_dir()  # the retry's ok result got the canonical one


def test_online_scenarios_are_refused_until_e2_5(tmp_path: Path) -> None:
    with pytest.raises(NotImplementedError):
        run_simulation(
            online_scenario(),
            1,
            runner=FakeRunner([]),
            results=InMemoryResultRepository(),
            run_dirs=RUN_DIRS,
            out_dir=tmp_path,
            attempt="study-1",
        )


def test_ephemeral_runs_return_the_raw_output_and_take_no_repository(tmp_path: Path) -> None:
    runner = FakeRunner([ok_output()])
    cfg = artifact("probe.sumocfg", "p1", "sumocfg")

    output = run_ephemeral(cfg, 5, runner=runner, out_dir=tmp_path / "probe")

    assert output == ok_output()
    assert runner.calls == [(cfg, 5, tmp_path / "probe")]


def test_run_output_invariants_mirror_simulation_result() -> None:
    with pytest.raises(ValueError):
        RunOutput(ok=True, error=None, artifacts=(), wall_clock_s=0.0)
    with pytest.raises(ValueError):
        RunOutput(ok=False, error="", artifacts=(), wall_clock_s=0.0)


def test_the_result_id_with_the_pinned_version_is_the_one_computed_before(tmp_path: Path) -> None:
    runner = FakeRunner([ok_output()], version=SUMO_VERSION)
    results = InMemoryResultRepository()

    result = run_simulation(
        batch_scenario(),
        7,
        runner=runner,
        results=results,
        run_dirs=RUN_DIRS,
        out_dir=tmp_path,
        attempt="a",
    )

    assert result.result_id == result_id_for("s-batch", 7, "batch", SUMO_VERSION)  # as before
    assert result.sumo_version == SUMO_VERSION


def test_a_runner_on_another_sumo_version_never_produces_a_stored_result(tmp_path: Path) -> None:
    runner = FakeRunner([ok_output()], version="1.20.0")
    results = InMemoryResultRepository()

    with pytest.raises(ValueError, match="results must come from SUMO"):
        run_simulation(
            batch_scenario(),
            7,
            runner=runner,
            results=results,
            run_dirs=RUN_DIRS,
            out_dir=tmp_path,
            attempt="a",
        )

    assert results.get(result_id_for("s-batch", 7, "batch", "1.20.0")) is None
