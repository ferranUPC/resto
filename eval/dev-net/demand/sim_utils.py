"""Shared helpers for generating and verifying DEV-NET demand profiles.

Used by generate_demand.sh (via calibrate.py, not committed) while tuning `peak`'s
insertion-rate, and by verification.ipynb to reproduce the same checks against the
final, committed trips/routes. Not part of `resto.application` — this is eval-only
scaffolding around SUMO's own CLI tools, not framework code.
"""

from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import sumolib

DEMAND_DIR = Path(__file__).resolve().parent
DEV_NET_DIR = DEMAND_DIR.parent
NET_FILE = DEV_NET_DIR / "dev-net.net.xml"

# An edge counts as "congested" for a run if, over the whole aggregation window, it
# both (a) carried vehicles at or below this fraction of its free-flow (speed-limit)
# speed and (b) had at least CONGESTION_MIN_OCCUPANCY average occupancy. Speed alone
# is not enough: a signalised approach shows the same >=50% average speed drop from a
# single car waiting one red phase as it does under a real, demand-driven queue - the
# occupancy floor is what tells those two apart (empirically, an idle-signal artifact
# stays under ~0.15% occupancy on DEV-NET, a genuinely queued approach clears 1%).
CONGESTION_SPEED_RATIO = 0.5
CONGESTION_MIN_OCCUPANCY = 0.5

CONTROL_EDGES = {
    "B0C0": "bottleneck approach (2 lanes, row 0)",
    "C0D0": "bottleneck exit (1 lane, row 0)",
    "C2D2": "signalised corridor (row 2)",
    "A0A1": "baseline, far from both features (column A, south)",
    "E2E3": "leaving the corridor northbound (column E)",
}


def route_file(profile: str) -> Path:
    return DEMAND_DIR / f"{profile}.rou.xml"


def run_dir() -> Path:
    d = DEMAND_DIR / "_runs"
    d.mkdir(exist_ok=True)
    return d


def run_sim(profile: str, sim_seed: int, route_path: Path | None = None) -> dict[str, Path]:
    """Runs one headless SUMO simulation of `profile`'s stored routes with simulation
    seed `sim_seed` (SUMO's own stochasticity - NOT the demand-generation seed baked
    into the routes). Returns paths to the edgedata and statistics outputs."""
    route_path = route_path or route_file(profile)
    out = run_dir()
    edgedata = out / f"{profile}_seed{sim_seed}.edgedata.xml"
    stats = out / f"{profile}_seed{sim_seed}.stats.xml"
    subprocess.run(
        [
            "sumo",
            "--net-file",
            str(NET_FILE),
            "--route-files",
            str(route_path),
            "--seed",
            str(sim_seed),
            "--edgedata-output",
            str(edgedata),
            "--statistic-output",
            str(stats),
            "--no-step-log",
            "--duration-log.disable",
            "--time-to-teleport",
            "300",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return {"edgedata": edgedata, "stats": stats}


def parse_edgedata(path: Path) -> dict[str, dict]:
    """Returns {edge_id: {attr: float}} for every non-internal edge in the (single,
    whole-window) <interval> of an --edgedata-output file."""
    root = ET.parse(path).getroot()
    interval = root.find("interval")
    result: dict[str, dict] = {}
    for edge in interval.findall("edge"):
        eid = edge.get("id")
        if eid.startswith(":"):
            continue
        result[eid] = {k: float(v) for k, v in edge.attrib.items() if k != "id"}
    return result


def count_teleports(stats_path: Path) -> int:
    root = ET.parse(stats_path).getroot()
    return int(root.find("teleports").get("total"))


def num_vehicles(stats_path: Path) -> int:
    root = ET.parse(stats_path).getroot()
    return int(root.find("vehicles").get("loaded"))


def num_network_edges() -> int:
    net = sumolib.net.readNet(str(NET_FILE))
    return len([e for e in net.getEdges() if not e.getID().startswith(":")])


def _is_congested(attrs: dict) -> bool:
    return (
        attrs.get("sampledSeconds", 0.0) > 0
        and attrs.get("speedRelative", 1.0) <= CONGESTION_SPEED_RATIO
        and attrs.get("occupancy", 0.0) >= CONGESTION_MIN_OCCUPANCY
    )


def congested_edges(edgedata: dict[str, dict]) -> list[str]:
    return sorted(eid for eid, attrs in edgedata.items() if _is_congested(attrs))


def congestion_fraction(edgedata: dict[str, dict]) -> float:
    return len(congested_edges(edgedata)) / num_network_edges()
