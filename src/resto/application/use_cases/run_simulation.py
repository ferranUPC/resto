"""Simulation Runner (code): Scenario + seed -> SimulationResult (DoD §2.4, §4.6; ADR-0017).

`run_simulation` is the stored path: it is what the Coordinator calls. `run_ephemeral` is the
tool-shaped path behind `probe_run` / `calibration_run`: same Runner, no `Scenario`, and no
repository argument at all, so those runs cannot reach the results store.

Identity: `result_id = hash(scenario_id, seed, mode, sumo_version)`, computed before SUMO starts.
An existing *ok* result for that id is returned without running anything ("zero redundant
simulations", §1); a failed one is re-run. `content_hash` is the hash of the deterministic
artifacts only (cfg, additionals, edgedata, tripinfo), which is what the reproducibility criterion
compares; `statistics` and `summary` carry wall-clock timings and are kept but not hashed.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from resto.application.ports.repositories import ResultRepository
from resto.application.ports.sumo import RunOutput, SumoRunner
from resto.domain.constants import SUMO_VERSION
from resto.domain.entities.scenario import Scenario
from resto.domain.entities.simulation_result import RunMode, RunStatus, SimulationResult
from resto.domain.services.content_hash import compute_content_hash
from resto.domain.services.ids import result_id_for
from resto.domain.value_objects.artifact_ref import ArtifactRef

REPRODUCIBLE_KINDS = frozenset({"sumocfg", "additional", "edgedata", "tripinfo"})


def run_simulation(
    scenario: Scenario,
    seed: int,
    *,
    runner: SumoRunner,
    results: ResultRepository,
    out_dir: Path,
) -> SimulationResult:
    """Runs `scenario` with `seed`, stores and returns the `SimulationResult`.

    Outputs go to `<out_dir>/<result_id>/`. Batch only until E2.5.
    """
    if scenario.is_online:
        raise NotImplementedError("online scenarios need the E2.5 runner")
    mode = RunMode.BATCH
    result_id = result_id_for(scenario.scenario_id, seed, mode.value, SUMO_VERSION)
    existing = results.get(result_id)
    if existing is not None and existing.status is RunStatus.OK:
        return existing

    output = runner.run_batch(scenario.sumocfg, seed, out_dir / result_id)
    result = SimulationResult(
        result_id=result_id,
        scenario_id=scenario.scenario_id,
        seed=seed,
        mode=mode,
        status=RunStatus.OK if output.ok else RunStatus.FAILED,
        content_hash=reproducibility_hash(output.artifacts),
        artifacts=output.artifacts,
        kpis=output.kpis,
        error=output.error,
        wall_clock_s=output.wall_clock_s,
    )
    results.store(result)
    return result


def run_ephemeral(
    sumocfg: ArtifactRef, seed: int, *, runner: SumoRunner, out_dir: Path
) -> RunOutput:
    """One batch run of a cfg that is not (yet) a `Scenario`: probe and calibration runs. Never
    stored - there is no repository to store into."""
    return runner.run_batch(sumocfg, seed, out_dir)


def reproducibility_hash(artifacts: Iterable[ArtifactRef]) -> str:
    deterministic = sorted(
        (a.kind, a.content_hash) for a in artifacts if a.kind in REPRODUCIBLE_KINDS
    )
    return compute_content_hash("run", deterministic)
