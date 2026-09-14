from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from resto.domain.value_objects.intervention import Intervention, InterventionType, Strategy


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


def check_mechanisms_match(
    interventions: Sequence[Intervention], mechanisms: Sequence[Mechanism]
) -> None:
    """The Builder's decision rules of §2.5, shared by ScenarioDraft and Scenario.

    Kept in one place: DoD §4.5 grades mechanism selection at 100 %, so the draft must fail with
    the same message the entity would, and the two must not be able to drift apart.
    """
    if len(mechanisms) != len(interventions):
        raise ValueError("every intervention needs exactly one mechanism")
    for intervention, mechanism in zip(interventions, mechanisms, strict=True):
        if (
            intervention.type is InterventionType.DEMAND_SCALE
            and intervention.strategy is Strategy.DYNAMIC
        ):
            # No mechanism can satisfy this: regenerating the demand cannot react at run time.
            # Said plainly here because the message is what the agent gets for its one retry.
            raise ValueError(
                "dynamic demand_scale is not supported in v1; report it in rejected[] instead"
            )
        if intervention.type is InterventionType.DEMAND_SCALE and not isinstance(
            mechanism, RegenerateDemandMechanism
        ):
            raise ValueError("demand_scale must be implemented by regenerating the demand")
        if intervention.strategy is Strategy.DYNAMIC and not isinstance(mechanism, ScriptMechanism):
            raise ValueError("interventions with a runtime condition require a script")


def needs_script(mechanisms: Sequence[Mechanism]) -> bool:
    return any(isinstance(m, ScriptMechanism) for m in mechanisms)
