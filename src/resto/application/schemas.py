"""Boundary schemas: pydantic TypeAdapters over the domain dataclasses.

The domain stays framework-free; validation (which runs the dataclasses' __post_init__
invariants), JSON round-trip and JSON-schema export all happen here.
"""

from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter

from resto.domain.entities.demand import Demand
from resto.domain.entities.expert_note import ExpertNote
from resto.domain.entities.network import Network
from resto.domain.entities.scenario import Scenario
from resto.domain.entities.simulation_result import SimulationResult
from resto.domain.entities.study import Study
from resto.domain.value_objects.expert_answer import ExpertAnswer
from resto.domain.value_objects.question import Question
from resto.domain.value_objects.report import Report
from resto.domain.value_objects.study_plan import StudyPlan
from resto.domain.value_objects.tasks import DemandTask, ExpertTask, NetworkTask, ScenarioTask

SCHEMA_TYPES: dict[str, type] = {
    # aggregates
    "Study": Study,
    "Network": Network,
    "Demand": Demand,
    "Scenario": Scenario,
    "SimulationResult": SimulationResult,
    "ExpertNote": ExpertNote,
    # agent outputs
    "Question": Question,
    "StudyPlan": StudyPlan,
    "ExpertAnswer": ExpertAnswer,
    "Report": Report,
    # agent inputs
    "NetworkTask": NetworkTask,
    "DemandTask": DemandTask,
    "ScenarioTask": ScenarioTask,
    "ExpertTask": ExpertTask,
}

ADAPTERS: dict[str, TypeAdapter[Any]] = {name: TypeAdapter(t) for name, t in SCHEMA_TYPES.items()}


def adapter_for(t: type) -> TypeAdapter[Any]:
    return TypeAdapter(t)


def json_schemas() -> dict[str, dict[str, Any]]:
    """JSON schema per boundary type (DoD §4.9: schemas published)."""
    return {name: adapter.json_schema() for name, adapter in ADAPTERS.items()}
