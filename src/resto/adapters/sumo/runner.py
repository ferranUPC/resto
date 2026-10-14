"""`SumoRunner` adapter, batch mode (E2.1, ADR-0017): derive a run cfg from the scenario cfg,
start `sumo -c run.sumocfg`, collect the outputs.

Almost nothing is passed on the command line but `-c`: the seed, the outputs and the edgedata
period all live in files in the run directory, so `sumo -c run.sumocfg` reproduces the run by
itself. The one exception, found empirically while building E2.4's effect-verification harness:
a `<rerouter>` additional file (`lane_closure`/`edge_closure`, E2.2/E2.3) makes SUMO's own router
recompute a path for any vehicle that would need the closed lane/edge - but on DEV-NET's sparse
grid (no U-turn connections, largely single-lane) at least one vehicle in `peak`/`low` typically
has no alternate path at all, or starts its trip on the closed edge outright. By default SUMO
treats either case as fatal and aborts the *entire* run ("no valid route"/"not allowed on source
edge"), rather than the "some vehicles just don't reroute" DoD §4.5 already expects (the
`lane_closure` effect bar is "≥ 90 % rerouted", not 100). `--ignore-route-errors` downgrades that
one vehicle to a dropped-and-warned one (it never departs, so `Kpis.departed` already reflects
the drop) instead of failing the run - confirmed empirically on 12 different DEV-NET locations
that all hard-failed without it and all completed with it. A first attempt at this fix reached
for `--device.rerouting.probability` instead (SUMO's periodic re-routing device); a clean,
isolated re-test showed it made no difference in any of those 12 cases, so it was dropped in
favour of this simpler, verified fix. Added only when the scenario's additional files actually
contain a `<rerouter>`, so a scenario with none (most of E2.1's own reproducibility test, and
every baseline/non-closure run) stays byte-identical to before this fix.

Online mode (`run_online`, ADR-0044) derives the same run cfg, writes the `script.py` the translator
generates from the `TraciScript` into the run directory and starts the script harness as a
subprocess under a timeout. Same scenario and seed give the same edgedata as a batch run.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from time import perf_counter

from resto.adapters.persistence.filesystem import artifact_ref
from resto.adapters.sumo.outputs import output_artifact, parse_kpis
from resto.adapters.sumo.script_harness import APPLIED_ACTIONS_FILE, read_applied_actions
from resto.adapters.sumo.script_translator import translate_script
from resto.adapters.sumo.sumo_process import checked_version, launch, launch_harness
from resto.adapters.sumo.writers.sumocfg import (
    parse_settings,
    render_sumocfg,
    with_additional,
    write_edgedata_additional,
)
from resto.application.ports.sumo import RunOutput
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.traci_script import TraciScript

EDGEDATA_PERIOD_S = 300.0
SCRIPT_NAME = "script.py"
DEFAULT_TIMEOUT_S = 600.0  # twice the DoD's 5-minute threshold
RUN_CFG_NAME = "run.sumocfg"
IGNORE_ROUTE_ERRORS_ARGS = ("--ignore-route-errors",)


def _has_rerouter(additional_files: Sequence[Path]) -> bool:
    """Whether any of `additional_files` declares a `<rerouter>` - see the module docstring."""
    for path in additional_files:
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError):
            continue
        if any(child.tag == "rerouter" for child in root):
            return True
    return False


# output option -> (file name in the run directory, artifact kind)
_OUTPUTS: dict[str, tuple[str, str]] = {
    "tripinfo-output": ("tripinfo.xml", "tripinfo"),
    "statistic-output": ("statistics.xml", "statistics"),
    "summary-output": ("summary.xml", "summary"),
}
_EDGEDATA_FILE = "edgedata.xml"
_REPORT = {"duration-log.statistics": "true", "no-step-log": "true"}


@dataclass(frozen=True)
class PreparedRun:
    """What `prepare_run` derived: the `sumo` arguments and the input artifacts of the run."""

    args: tuple[str, ...]
    inputs: tuple[ArtifactRef, ...]


class InvalidScenarioCfg(ValueError):
    """The scenario's sumocfg could not be read."""


def prepare_run(sumocfg: ArtifactRef, seed: int, out_dir: Path) -> PreparedRun:
    """Derives the run configuration from the scenario cfg and writes it into `out_dir`.

    Shared by the batch and online runners, so both derive the same configuration.

    Raises:
        InvalidScenarioCfg: `sumocfg` cannot be parsed.
    """
    try:
        settings = parse_settings(sumocfg.path)
    except (ValueError, OSError, SyntaxError) as exc:
        raise InvalidScenarioCfg(f"invalid scenario cfg: {exc}") from exc
    edgedata_add = write_edgedata_additional(out_dir, EDGEDATA_PERIOD_S, _EDGEDATA_FILE)
    run_cfg = out_dir / RUN_CFG_NAME
    run_cfg.write_text(
        render_sumocfg(
            with_additional(settings, edgedata_add),
            out_dir,
            seed=seed,
            outputs={option: name for option, (name, _) in _OUTPUTS.items()},
            report=_REPORT,
        ),
        encoding="utf-8",
    )
    args = ["-c", str(run_cfg)]
    if _has_rerouter(settings.additional_files):
        args.extend(IGNORE_ROUTE_ERRORS_ARGS)
    return PreparedRun(
        args=tuple(args),
        inputs=(artifact_ref(run_cfg, "sumocfg"), artifact_ref(edgedata_add, "additional")),
    )


def collect_outputs(prepared: PreparedRun, out_dir: Path, wall_clock_s: float) -> RunOutput:
    """Checks the expected output files exist, refs them and parses the KPIs."""
    expected = [(out_dir / _EDGEDATA_FILE, "edgedata")] + [
        (out_dir / name, kind) for name, kind in _OUTPUTS.values()
    ]
    missing = [p.name for p, _ in expected if not p.exists()]
    if missing:
        return RunOutput(
            ok=False,
            error=f"sumo exited normally but did not write {', '.join(missing)}",
            artifacts=prepared.inputs,
            wall_clock_s=wall_clock_s,
        )
    outputs = tuple(output_artifact(p, kind) for p, kind in expected)
    return RunOutput(
        ok=True,
        error=None,
        artifacts=prepared.inputs + outputs,
        wall_clock_s=wall_clock_s,
        kpis=parse_kpis(out_dir / _OUTPUTS["statistic-output"][0]),
    )


class SubprocessSumoRunner:
    def __init__(self, sumo_binary: str = "sumo", timeout_s: float = DEFAULT_TIMEOUT_S) -> None:
        self._sumo = sumo_binary
        self._timeout_s = timeout_s

    def sumo_version(self) -> str:
        """The `sumo` binary's version; raises if it is not the pinned one."""
        return checked_version(self._sumo)

    def run_batch(self, sumocfg: ArtifactRef, seed: int, out_dir: Path) -> RunOutput:
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            prepared = prepare_run(sumocfg, seed, out_dir)
        except InvalidScenarioCfg as exc:
            return RunOutput(ok=False, error=str(exc), artifacts=(), wall_clock_s=0.0)

        started = perf_counter()
        launched = launch(self._sumo, prepared.args, out_dir, seed)
        wall_clock_s = perf_counter() - started
        if not launched.ok:
            return RunOutput(
                ok=False,
                error=launched.message,
                artifacts=prepared.inputs,
                wall_clock_s=wall_clock_s,
            )
        return collect_outputs(prepared, out_dir, wall_clock_s)

    def run_online(
        self, sumocfg: ArtifactRef, script: TraciScript, seed: int, out_dir: Path
    ) -> RunOutput:
        """Runs the scenario with `script` applied through TraCI. A failure (SUMO's or the script's
        traceback, a timeout, a harness that left no applied actions) is `ok=False`, never an
        empty success."""
        self.sumo_version()
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            prepared = prepare_run(sumocfg, seed, out_dir)
        except InvalidScenarioCfg as exc:
            return RunOutput(ok=False, error=str(exc), artifacts=(), wall_clock_s=0.0)
        script_path = out_dir / SCRIPT_NAME
        script_path.write_text(translate_script(script), encoding="utf-8")
        prepared = PreparedRun(
            args=prepared.args,
            inputs=prepared.inputs + (artifact_ref(script_path, "script"),),
        )

        started = perf_counter()
        launched = launch_harness(
            script_path, out_dir, [self._sumo, *prepared.args], self._timeout_s
        )
        wall_clock_s = perf_counter() - started
        if not launched.ok:
            return RunOutput(
                ok=False,
                error=launched.message,
                artifacts=prepared.inputs,
                wall_clock_s=wall_clock_s,
            )
        try:
            applied = read_applied_actions(out_dir)
        except FileNotFoundError:
            return RunOutput(
                ok=False,
                error=f"the harness exited normally but did not write {APPLIED_ACTIONS_FILE}",
                artifacts=prepared.inputs,
                wall_clock_s=wall_clock_s,
            )
        collected = collect_outputs(prepared, out_dir, wall_clock_s)
        return replace(collected, applied_actions=applied)
