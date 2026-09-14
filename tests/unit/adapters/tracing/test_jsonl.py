"""JsonlTracer (E0.7): run id, step, tool call, artifacts, tokens -> JSONL."""

from __future__ import annotations

from pathlib import Path

from resto.adapters.tracing.jsonl import JsonlTracer, read_run
from resto.domain.value_objects.step_record import StepStatus, Usage


def test_emit_appends_one_json_line_with_study_id_event_and_payload(tmp_path: Path) -> None:
    tracer = JsonlTracer(tmp_path)

    tracer.emit("study-1", "step", {"tool": "generate_network", "status": "ok"})

    [record] = read_run(tmp_path, "study-1")
    assert record["study_id"] == "study-1"
    assert record["event"] == "step"
    assert record["tool"] == "generate_network"
    assert record["status"] == "ok"
    assert "ts" in record


def test_multiple_emits_append_in_order(tmp_path: Path) -> None:
    tracer = JsonlTracer(tmp_path)

    tracer.emit("study-1", "tool_call", {"tool": "shortest_path"})
    tracer.emit("study-1", "artifact", {"path": "net.xml"})
    tracer.emit("study-1", "usage", {"input_tokens": 10})

    events = [r["event"] for r in read_run(tmp_path, "study-1")]
    assert events == ["tool_call", "artifact", "usage"]


def test_payload_with_dataclass_enum_and_path_is_json_serialisable(tmp_path: Path) -> None:
    tracer = JsonlTracer(tmp_path)

    tracer.emit(
        "study-1",
        "step",
        {
            "status": StepStatus.FAILED,
            "usage": Usage(input_tokens=5, output_tokens=7, simulations=1),
            "artifact_path": Path("results") / "kpis.json",
        },
    )

    [record] = read_run(tmp_path, "study-1")
    assert record["status"] == "failed"
    assert record["usage"] == {"input_tokens": 5, "output_tokens": 7, "simulations": 1}
    assert record["artifact_path"] == str(Path("results") / "kpis.json")


def test_different_studies_are_isolated_in_separate_files(tmp_path: Path) -> None:
    tracer = JsonlTracer(tmp_path)

    tracer.emit("study-1", "step", {"tool": "a"})
    tracer.emit("study-2", "step", {"tool": "b"})

    assert [r["tool"] for r in read_run(tmp_path, "study-1")] == ["a"]
    assert [r["tool"] for r in read_run(tmp_path, "study-2")] == ["b"]


def test_read_run_returns_empty_list_for_unknown_study(tmp_path: Path) -> None:
    assert read_run(tmp_path, "does-not-exist") == []
