"""Boundary schemas: pydantic TypeAdapters over the domain dataclasses.

The domain stays framework-free; validation (which runs the dataclasses' __post_init__
invariants), JSON round-trip and JSON-schema export all happen here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from resto.domain.entities.demand import Demand
from resto.domain.entities.expert_note import ExpertNote
from resto.domain.entities.network import Network
from resto.domain.entities.scenario import Scenario
from resto.domain.entities.simulation_result import SimulationResult
from resto.domain.entities.study import Study
from resto.domain.value_objects.drafts import (
    DemandDraft,
    ExpertNoteDraft,
    NetworkDraft,
    ScenarioDraft,
)
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
    # agent drafts
    "NetworkDraft": NetworkDraft,
    "DemandDraft": DemandDraft,
    "ScenarioDraft": ScenarioDraft,
    "ExpertNoteDraft": ExpertNoteDraft,
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


def render_json_schemas() -> dict[str, str]:
    """The exact bytes of each published schema file.

    Sorted keys and a fixed indent so regenerating produces no diff when nothing changed —
    that is what lets a test detect drift between the code and the committed schemas.
    """
    return {
        name: json.dumps(schema, indent=2, sort_keys=True) + "\n"
        for name, schema in json_schemas().items()
    }


def write_json_schemas(target: Path) -> list[Path]:
    """Publish the schemas as files so a DatabaseMCP implementer can read them without
    running Python (DoD §4.9). Stale files are removed so the directory always mirrors the code."""
    target.mkdir(parents=True, exist_ok=True)
    rendered = render_json_schemas()
    for stale in set(target.glob("*.json")) - {target / f"{n}.json" for n in rendered}:
        stale.unlink()
    written = []
    for name, text in rendered.items():
        path = target / f"{name}.json"
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":  # python -m resto.application.schemas [dir]
    import sys

    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("schemas")
    for written_path in write_json_schemas(destination):
        print(written_path)
