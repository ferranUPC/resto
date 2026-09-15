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

Online mode (SUMO under TraCI with a sandboxed script) is E2.5.
"""

from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from pathlib import Path
from time import perf_counter

from resto.adapters.persistence.filesystem import artifact_ref
from resto.adapters.sumo.outputs import output_artifact, parse_kpis
from resto.adapters.sumo.writers.sumocfg import (
    parse_settings,
    render_sumocfg,
    with_additional,
    write_edgedata_additional,
)
from resto.application.ports.sumo import RunOutput
from resto.domain.value_objects.artifact_ref import ArtifactRef

EDGEDATA_PERIOD_S = 300.0
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


class SubprocessSumoRunner:
    def __init__(self, sumo_binary: str = "sumo") -> None:
        self._sumo = sumo_binary

    def run_batch(self, sumocfg: ArtifactRef, seed: int, out_dir: Path) -> RunOutput:
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            settings = parse_settings(sumocfg.path)
        except (ValueError, OSError, SyntaxError) as exc:
            return RunOutput(
                ok=False, error=f"invalid scenario cfg: {exc}", artifacts=(), wall_clock_s=0.0
            )
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
        inputs = (artifact_ref(run_cfg, "sumocfg"), artifact_ref(edgedata_add, "additional"))
        command = [self._sumo, "-c", str(run_cfg)]
        if _has_rerouter(settings.additional_files):
            command.extend(IGNORE_ROUTE_ERRORS_ARGS)

        started = perf_counter()
        try:
            proc = subprocess.run(command, capture_output=True, text=True, cwd=out_dir)
        except OSError as exc:
            return RunOutput(ok=False, error=str(exc), artifacts=inputs, wall_clock_s=0.0)
        wall_clock_s = perf_counter() - started

        if proc.returncode != 0:
            message = _sumo_message(proc.stderr) or f"sumo exited with code {proc.returncode}"
            return RunOutput(ok=False, error=message, artifacts=inputs, wall_clock_s=wall_clock_s)

        expected = [(out_dir / _EDGEDATA_FILE, "edgedata")] + [
            (out_dir / name, kind) for name, kind in _OUTPUTS.values()
        ]
        missing = [p.name for p, _ in expected if not p.exists()]
        if missing:
            return RunOutput(
                ok=False,
                error=f"sumo exited normally but did not write {', '.join(missing)}",
                artifacts=inputs,
                wall_clock_s=wall_clock_s,
            )
        outputs = tuple(output_artifact(p, kind) for p, kind in expected)
        return RunOutput(
            ok=True,
            error=None,
            artifacts=inputs + outputs,
            wall_clock_s=wall_clock_s,
            kpis=parse_kpis(out_dir / _OUTPUTS["statistic-output"][0]),
        )

    def run_online(
        self, sumocfg: ArtifactRef, script: ArtifactRef, seed: int, out_dir: Path
    ) -> RunOutput:
        raise NotImplementedError("online mode is work-plan E2.5")


def _sumo_message(stderr: str) -> str:
    """SUMO's own error lines, without the warnings that precede them."""
    errors = [line for line in stderr.splitlines() if line.startswith("Error")]
    return "\n".join(errors) if errors else stderr.strip()
