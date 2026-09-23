"""`run_simulation` / `run_ephemeral` (E2.1, ADR-0017) with a fake runner: identity, dedupe on
ok results only, failed runs stored with SUMO's message, ephemeral runs unable to store."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from resto.adapters.persistence.memory import InMemoryResultRepository
from resto.application.ports.sumo import RunOutput
from resto.application.use_cases.run_simulation import (
    reproducibility_hash,
    run_ephemeral,
    run_simulation,
)
from resto.domain.constants import SUMO_VERSION
from resto.domain.entities.scenario import Scenario
from resto.domain.entities.simulation_result import RunMode, RunStatus
from resto.domain.services.ids import result_id_for
from resto.domain.value_objects.kpis import Kpis
from resto.domain.value_objects.mechanism import StaticFileMechanism
from tests.unit.application.use_cases._doubles import FakeRunner
from tests.unit.domain._fixtures import artifact, static_intervention
from tests.unit.domain._samples import scenario as online_scenario

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

    result = run_simulation(batch_scenario(), 7, runner=runner, results=results, out_dir=tmp_path)

    expected_id = result_id_for("s-batch", 7, RunMode.BATCH.value, SUMO_VERSION)
    assert result.result_id == expected_id
    assert runner.calls == [(batch_scenario().sumocfg, 7, tmp_path / expected_id)]
    assert result.status is RunStatus.OK
    assert result.kpis == KPIS
    assert result.wall_clock_s == 1.5
    assert result.sumo_version == SUMO_VERSION
    assert results.get(expected_id) == result


def test_an_existing_ok_result_is_returned_without_running_sumo(tmp_path: Path) -> None:
    runner = FakeRunner([ok_output()])
    results = InMemoryResultRepository()
    first = run_simulation(batch_scenario(), 7, runner=runner, results=results, out_dir=tmp_path)

    second = run_simulation(batch_scenario(), 7, runner=runner, results=results, out_dir=tmp_path)

    assert second == first
    assert len(runner.calls) == 1


def test_a_failed_run_is_stored_with_sumos_message_and_rerun_next_time(tmp_path: Path) -> None:
    runner = FakeRunner([failed_output(), ok_output()])
    results = InMemoryResultRepository()

    failed = run_simulation(batch_scenario(), 7, runner=runner, results=results, out_dir=tmp_path)
    retried = run_simulation(batch_scenario(), 7, runner=runner, results=results, out_dir=tmp_path)

    assert failed.status is RunStatus.FAILED
    assert failed.error is not None and "NOPE" in failed.error
    assert failed.kpis is None
    assert retried.status is RunStatus.OK
    assert retried.result_id == failed.result_id
    assert results.get(failed.result_id) == retried
    assert len(runner.calls) == 2


def test_content_hash_covers_only_the_deterministic_artifacts() -> None:
    with_clock_a = ok_output().artifacts + (artifact("summary.xml", "sum-1", "summary"),)
    with_clock_b = tuple(
        dataclasses.replace(a, content_hash="other-clock")
        if a.kind in ("statistics", "summary")
        else a
        for a in with_clock_a
    )
    other_edgedata = ok_output("ed2").artifacts

    assert reproducibility_hash(with_clock_a) == reproducibility_hash(with_clock_b)
    assert reproducibility_hash(with_clock_a) != reproducibility_hash(other_edgedata)


def test_online_scenarios_are_refused_until_e2_5(tmp_path: Path) -> None:
    with pytest.raises(NotImplementedError):
        run_simulation(
            online_scenario(),
            1,
            runner=FakeRunner([]),
            results=InMemoryResultRepository(),
            out_dir=tmp_path,
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
