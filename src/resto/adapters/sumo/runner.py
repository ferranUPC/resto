"""`SumoRunner` adapter, batch mode (E2.1, ADR-0017): derive a run cfg from the scenario cfg,
start `sumo -c run.sumocfg`, collect the outputs.

Nothing is passed on the command line but `-c`: the seed, the outputs and the edgedata period
all live in files in the run directory, so `sumo -c run.sumocfg` reproduces the run by itself.
Online mode (SUMO under TraCI with a sandboxed script) is E2.5.
"""

from __future__ import annotations

import subprocess
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

        started = perf_counter()
        try:
            proc = subprocess.run(
                [self._sumo, "-c", str(run_cfg)], capture_output=True, text=True, cwd=out_dir
            )
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
