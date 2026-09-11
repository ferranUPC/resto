from __future__ import annotations

from dataclasses import dataclass

from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.intervention import Intervention, InterventionType, Strategy
from resto.domain.value_objects.mechanism import (
    Mechanism,
    RegenerateDemandMechanism,
    ScriptMechanism,
)
from resto.domain.value_objects.traci_script import TraciScript


@dataclass(frozen=True, slots=True)
class Scenario:
    """A runnable SUMO configuration for (network, demand, interventions).
    `scenario_id` is the hash of the request, not of the files (see ids.scenario_id_for)."""

    scenario_id: str
    network_id: str
    demand_id: str
    interventions: tuple[Intervention, ...]
    mechanisms: tuple[Mechanism, ...]
    sumocfg: ArtifactRef
    content_hash: str
    additional_files: tuple[ArtifactRef, ...] = ()
    context_tags: frozenset[str] = frozenset()
    traci_script: TraciScript | None = None

    def __post_init__(self) -> None:
        if len(self.mechanisms) != len(self.interventions):
            raise ValueError("every intervention needs exactly one mechanism")
        for intervention, mechanism in zip(self.interventions, self.mechanisms, strict=True):
            if intervention.type is InterventionType.DEMAND_SCALE and not isinstance(
                mechanism, RegenerateDemandMechanism
            ):
                raise ValueError("demand_scale must be implemented by regenerating the demand")
            if intervention.strategy is Strategy.DYNAMIC and not isinstance(
                mechanism, ScriptMechanism
            ):
                raise ValueError("interventions with a runtime condition require a script")
        if self.needs_script and self.traci_script is None:
            raise ValueError("script mechanisms require a traci_script")
        if self.traci_script is not None and not self.traci_script.is_runnable:
            raise ValueError("a scenario's script must pass lint and dry_run")

    @property
    def needs_script(self) -> bool:
        return any(isinstance(m, ScriptMechanism) for m in self.mechanisms)

    @property
    def is_online(self) -> bool:
        return self.traci_script is not None
