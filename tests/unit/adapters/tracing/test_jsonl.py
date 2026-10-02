"""JsonlTracer (E0.7): typed trace events -> JSONL -> the same typed events."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from resto.adapters.tracing.jsonl import SCHEMA_VERSION, JsonlTracer, read_run
from resto.application.ports.tracing import (
    ClarificationAsked,
    ExpertRoundHeld,
    NetworksAdded,
    NoteStatusChanged,
    NotesWritten,
    NoteWriterFailed,
    PhaseStarted,
    PlanMade,
    ReportComposed,
    StepTraced,
    StudyCreated,
    TraceEvent,
)
from resto.domain.entities.expert_note import NoteStatus
from resto.domain.value_objects.question import Intent, Mode, Question
from resto.domain.value_objects.step_record import (
    StepError,
    StepErrorKind,
    StepStatus,
    Usage,
)
from resto.domain.value_objects.study_plan import FromStep, ObtainNetworkStep, StudyPlan


def _events() -> list[TraceEvent]:
    return [
        StudyCreated(
            Question(text="how congested is the peak?", intent=Intent.DESCRIBE, mode=Mode.FORCED),
            Usage(input_tokens=5, output_tokens=7, cost_usd=0.001),
        ),
        ClarificationAsked("which corridor?"),
        NetworksAdded(("n1", "n2")),
        StepTraced(
            phase=0,
            tool="run_simulation",
            status=StepStatus.FAILED,
            produced_ids=(),
            usage=Usage(simulations=1),
            error=StepError(StepErrorKind.INFRASTRUCTURE, "sumo crashed", ("log.txt",)),
        ),
        NotesWritten(("note-1",)),
        NoteStatusChanged("note-1", "res-1", NoteStatus.CONFIRMED),
        NoteWriterFailed("ValueError: bad"),
        PhaseStarted(1),
        PlanMade(1, StudyPlan(
                network_id=FromStep(0),
                rationale="baseline only",
                steps=(ObtainNetworkStep("RIVERSIDE"),),
            )),
        ExpertRoundHeld(1, 2),
        ReportComposed(),
    ]


def test_write_then_read_gives_equal_typed_events(tmp_path: Path) -> None:
    tracer = JsonlTracer(tmp_path)
    events = _events()

    for event in events:
        tracer.emit("study-1", event)

    assert read_run(tmp_path, "study-1") == events


def test_only_the_first_line_of_a_study_file_carries_the_schema_version(tmp_path: Path) -> None:
    tracer = JsonlTracer(tmp_path)

    tracer.emit("study-1", NetworksAdded(("n1",)))
    tracer.emit("study-1", NetworksAdded(("n2",)))

    lines = (tmp_path / "study-1.jsonl").read_text().splitlines()
    first, second = [json.loads(line) for line in lines]
    assert first["schema_version"] == SCHEMA_VERSION
    assert "schema_version" not in second


def test_a_file_with_another_schema_version_is_refused(tmp_path: Path) -> None:
    tracer = JsonlTracer(tmp_path)
    tracer.emit("study-1", NetworksAdded(("n1",)))
    path = tmp_path / "study-1.jsonl"
    record = json.loads(path.read_text())
    record["schema_version"] = SCHEMA_VERSION + 1
    path.write_text(json.dumps(record) + "\n")

    with pytest.raises(ValueError, match="schema version"):
        read_run(tmp_path, "study-1")


def test_different_studies_are_isolated_in_separate_files(tmp_path: Path) -> None:
    tracer = JsonlTracer(tmp_path)

    tracer.emit("study-1", NetworksAdded(("a",)))
    tracer.emit("study-2", NetworksAdded(("b",)))

    assert read_run(tmp_path, "study-1") == [NetworksAdded(("a",))]
    assert read_run(tmp_path, "study-2") == [NetworksAdded(("b",))]


def test_read_run_returns_empty_list_for_unknown_study(tmp_path: Path) -> None:
    assert read_run(tmp_path, "does-not-exist") == []
