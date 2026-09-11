from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from resto.domain.value_objects.intervention import Intervention
from resto.domain.value_objects.time_window import TimeWindow
from resto.domain.value_objects.topology_modification import TopologyModification


class Intent(StrEnum):
    DESCRIBE = "describe"
    DIAGNOSE = "diagnose"
    COUNTERFACTUAL = "counterfactual"
    COMPARE = "compare"
    RUN = "run"


class Mode(StrEnum):
    FREE = "free"
    FORCED = "forced"


@dataclass(frozen=True, slots=True)
class Question:
    """What the user asked, as understood by the Coordinator. A plain doubt is
    `describe`/`diagnose`; a hypothesis is `counterfactual`/`compare`."""

    text: str
    intent: Intent
    mode: Mode = Mode.FREE
    network_ref: str | None = None
    demand_ref: str | None = None
    interventions: tuple[Intervention, ...] = ()
    topology_changes: tuple[TopologyModification, ...] = ()
    metrics_of_interest: tuple[str, ...] = ()
    time_window: TimeWindow | None = None
    context_tags: frozenset[str] = frozenset()
    ambiguities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("a Question requires text")

    @property
    def is_ambiguous(self) -> bool:
        return bool(self.ambiguities)
