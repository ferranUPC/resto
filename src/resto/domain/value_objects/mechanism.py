from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True, slots=True)
class StaticFileMechanism:
    """Intervention implemented as a SUMO additional file (rerouter, VSS, TLS program, TAZ)."""

    file_kind: Literal["rerouter", "vss", "tls_program", "taz"]
    path: Path
    kind: Literal["static_file"] = "static_file"


@dataclass(frozen=True, slots=True)
class ScriptMechanism:
    """Intervention implemented inside the scenario's traci_api script."""

    kind: Literal["script"] = "script"


@dataclass(frozen=True, slots=True)
class RegenerateDemandMechanism:
    """Intervention implemented by pointing the scenario at a derived Demand (demand_scale)."""

    demand_id: str
    kind: Literal["regenerate_demand"] = "regenerate_demand"


Mechanism = StaticFileMechanism | ScriptMechanism | RegenerateDemandMechanism
