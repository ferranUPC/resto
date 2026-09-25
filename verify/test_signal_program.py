"""`signal_program` effect verification (work-plan E2.4, DoD §4.5) on DEV-NET with real SUMO:
the WAUT switch actually moves the junction's active `tlLogic` program during the window and
reverts it afterwards - read from a `SaveTLSSwitchTimes` log (`run_with_tls_switch_log`), the one
SUMO output that observes it (see `verify/effects.py` and this package's `__init__.py`).

The alternate program ("1") is supplied through its own additional file, not through
`dev-net.net.xml` (frozen, E0.5) - DEV-NET's junctions only ship one program each. Its phase
`state` strings are C2's own (`dev-net.net.xml`'s `programID="0"`), just with different
durations, so the network stays internally consistent (same movements, different timing).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from resto.adapters.sumo.runner import SubprocessSumoRunner
from resto.adapters.sumo.writers.sumocfg import SumocfgFileWriter
from resto.adapters.sumo.writers.tls_program import TlsProgramWriter
from resto.application.ports.writers import SimulationSettings
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import TlsTarget
from resto.domain.value_objects.time_window import TimeWindow
from verify.effects import run_with_tls_switch_log, verify_signal_program

DEV_NET_DIR = Path(__file__).resolve().parent.parent / "eval" / "dev-net"
NET = DEV_NET_DIR / "dev-net.net.xml"
PEAK_ROUTES = DEV_NET_DIR / "demand" / "peak.rou.xml"
TLS = "C2"
BEGIN_S = 28800.0  # 08:00, the peak demand's first departure (ADR-0028)
WINDOW = TimeWindow(28900.0, 29100.0)
END_S = 29400.0
ORIGINAL_PROGRAM = "0"
ALT_PROGRAM = "1"
# C2's own phase `state` strings (dev-net.net.xml, programID="0"), retimed for programID="1".
ALT_PHASES = (
    ("80", "GGgrrrGGgrrr"),
    ("3", "yyyrrryyyrrr"),
    ("4", "rrrGGgrrrGGg"),
    ("3", "rrryyyrrryyy"),
)


def _write_alt_program(out_dir: Path) -> Path:
    root = ET.Element("additional")
    tl = ET.SubElement(root, "tlLogic", id=TLS, type="static", programID=ALT_PROGRAM, offset="0")
    for duration, state in ALT_PHASES:
        ET.SubElement(tl, "phase", duration=duration, state=state)
    path = out_dir / "alt_program.add.xml"
    ET.indent(root, space="    ")
    path.write_text(ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def signal_program_cfg(tmp_path_factory: pytest.TempPathFactory) -> ArtifactRef:
    out_dir = tmp_path_factory.mktemp("signal_program")
    alt_program = _write_alt_program(out_dir)
    intervention = Intervention(
        type=InterventionType.SIGNAL_PROGRAM,
        target=TlsTarget(tls_id=TLS),
        window=WINDOW,
        params={"program_id": ALT_PROGRAM},
    )
    _, waut_ref = TlsProgramWriter().write(intervention, out_dir)
    settings = SimulationSettings(
        net_file=NET,
        route_files=(PEAK_ROUTES,),
        additional_files=(alt_program, waut_ref.path),
        begin=BEGIN_S,
        end=END_S,
    )
    return SumocfgFileWriter().write(settings, out_dir, "scenario.sumocfg")


def test_signal_program_switches_and_reverts(
    signal_program_cfg: ArtifactRef, tmp_path: Path
) -> None:
    output, tls_switches = run_with_tls_switch_log(
        SubprocessSumoRunner(), signal_program_cfg, TLS, seed=1, out_dir=tmp_path
    )
    assert output.ok, output.error

    result = verify_signal_program(tls_switches, TLS, WINDOW, ALT_PROGRAM, ORIGINAL_PROGRAM)
    assert result.ok, result.reason
