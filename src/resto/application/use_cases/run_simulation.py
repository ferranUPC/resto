"""Simulation Runner (code): Scenario + seed -> SimulationResult (DoD §2.4, §4.6; ADR-0017;
ADR-0031).

`run_simulation` is the stored path: it is what the Executor calls. `run_ephemeral` is the
tool-shaped path behind `probe_run` / `calibration_run`: same Runner, no `Scenario`, and no
repository argument at all, so those runs cannot reach the results store.

Identity: `result_id = hash(scenario_id, seed, mode, sumo_version)`, computed before SUMO starts.
An existing *ok* result for that id is returned without running anything ("zero redundant
simulations", §1); a failed one is re-run. `content_hash` is the hash of the deterministic
artifacts only (cfg, additionals, edgedata, tripinfo), which is what the reproducibility criterion
compares; `statistics` and `summary` carry wall-clock timings and are kept but not hashed.

Only an *ok* result is ever stored (ADR-0031): `result_id` names the request, not one attempt, so
a repository must never see two different contents under it (DATABASE_MCP_CONTRACT.md §3). A
failed run is returned to the caller — who reports it through the trace and its own logs — and
never reaches `results.store`. SUMO writes into a per-attempt staging directory,
`<out_dir>/<result_id>.<attempt>/`, named after the caller's own `attempt` label (a `study_id`, or
another caller's own identifier) so two callers retrying the same failed request never step on
each other's logs. Only on success does that directory become the canonical
`<out_dir>/<result_id>/`, replacing any leftover directory a crash between an earlier rename and
its `store` left behind.
"""

from __future__ import annotations

from pathlib import Path

from resto.application.ports.repositories import ResultRepository
from resto.application.ports.run_directories import RunDirectories
from resto.application.ports.sumo import RunOutput, SumoRunner
from resto.domain.entities.scenario import Scenario
from resto.domain.entities.simulation_result import RunMode, RunStatus, SimulationResult
from resto.domain.services.ids import result_id_for
from resto.domain.services.reproducibility import reproducibility_hash
from resto.domain.value_objects.artifact_ref import ArtifactRef


def attempt_dir(out_dir: Path, result_id: str, attempt: str) -> Path:
    """The staging directory one attempt at `result_id` runs in, before it either becomes
    `<out_dir>/<result_id>/` (on success) or is left in place (on failure, as its own logs)."""
    return out_dir / f"{result_id}.{attempt}"


def run_simulation(
    scenario: Scenario,
    seed: int,
    *,
    runner: SumoRunner,
    results: ResultRepository,
    run_dirs: RunDirectories,
    out_dir: Path,
    attempt: str,
) -> SimulationResult:
    """Runs `scenario` with `seed`, returns the `SimulationResult`, and stores it iff it is `ok`.

    Batch only until E2.5.
    """
    if scenario.is_online:
        raise NotImplementedError("online scenarios need the E2.5 runner")
    mode = RunMode.BATCH
    sumo_version = runner.sumo_version()
    result_id = result_id_for(scenario.scenario_id, seed, mode.value, sumo_version)
    existing = results.get(result_id)
    if existing is not None and existing.status is RunStatus.OK:
        return existing

    staging_dir = attempt_dir(out_dir, result_id, attempt)
    run_dirs.prepare(staging_dir)
    output = runner.run_batch(scenario.sumocfg, seed, staging_dir)

    if not output.ok:
        return _build_result(
            result_id,
            scenario,
            seed,
            mode,
            RunStatus.FAILED,
            output,
            output.artifacts,
            sumo_version,
        )

    artifacts = run_dirs.promote(staging_dir, out_dir / result_id, output.artifacts)
    result = _build_result(
        result_id, scenario, seed, mode, RunStatus.OK, output, artifacts, sumo_version
    )
    results.store(result)
    return result


def _build_result(
    result_id: str,
    scenario: Scenario,
    seed: int,
    mode: RunMode,
    status: RunStatus,
    output: RunOutput,
    artifacts: tuple[ArtifactRef, ...],
    sumo_version: str,
) -> SimulationResult:
    """The one place a `SimulationResult` is built from a run. KPIs are recorded only for an ok run;
    `SimulationResult` itself enforces which status needs which fields."""
    return SimulationResult(
        result_id=result_id,
        scenario_id=scenario.scenario_id,
        seed=seed,
        mode=mode,
        status=status,
        content_hash=reproducibility_hash(artifacts),
        artifacts=artifacts,
        kpis=output.kpis if status is RunStatus.OK else None,
        error=output.error,
        wall_clock_s=output.wall_clock_s,
        sumo_version=sumo_version,
    )


def run_ephemeral(
    sumocfg: ArtifactRef, seed: int, *, runner: SumoRunner, out_dir: Path
) -> RunOutput:
    """One batch run of a cfg that is not (yet) a `Scenario`: probe and calibration runs. Never
    stored - there is no repository to store into."""
    return runner.run_batch(sumocfg, seed, out_dir)
