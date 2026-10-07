"""The CLI composition root (E5.10): the real wiring builds, and a request the Input Parser cannot
turn into a `Question` ends in an error without creating a Study."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

from resto.adapters.llm.agents.composer import ComposerPort
from resto.adapters.persistence.sqlite.repositories import SqliteDatabase
from resto.adapters.tracing.jsonl import JsonlTracer, read_run
from resto.application.executor.deps import StudyDeps, StudySettings
from resto.application.ports.llm import Budget
from resto.application.ports.tracing import ModelCall, TraceEvent
from resto.domain.value_objects.drafts import ClaimDraft, ReportDraft
from resto.domain.value_objects.step_record import Usage
from resto.interface.cli.main import build_deps, main
from tests.unit.adapters.llm._fakes import FakeToolAgent
from tests.unit.application._world import DESCRIBE


class NullTracer:
    def emit(self, study_id: str, event: TraceEvent) -> None:
        raise AssertionError("no study, no trace")


def test_without_a_question_no_study_is_created(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = SqliteDatabase(tmp_path / "resto.sqlite")
    agent = FakeToolAgent(output=None)
    deps = build_deps(
        db=db,
        agent=agent,
        budget=Budget(max_steps=1, max_tokens=1, max_seconds=1.0),
        tracer=NullTracer(),
        out_dir=tmp_path,
    )

    code = main(
        ["how congested is the peak?", "--mode", "forced", "--out", str(tmp_path)], deps=deps
    )

    db.close()
    err = capsys.readouterr().err
    assert code == 1
    assert "no study was created" in err and "without a Question" in err


def test_a_failed_study_is_rendered(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from tests.unit.application._world import BASELINE_PLAN, World

    world = World(tmp_path, plans=(BASELINE_PLAN,), expert=(ConnectionError("503"),))

    code = main(
        ["how congested is the peak?", "--out", str(tmp_path)],
        deps=world.deps,
        settings=world.settings,
    )

    out = capsys.readouterr().out
    assert code == 1
    assert "Step `ask_expert` of phase 0 (the question as asked) failed (infrastructure)" in out


def _completed_deps(tmp_path: Path) -> tuple[StudyDeps, StudySettings]:
    from tests.unit.application._world import BASELINE_PLAN, World, answers

    world = World(tmp_path, plans=(BASELINE_PLAN,), expert=(answers(),))
    draft = ReportDraft(
        summary="The mean delay is about 24 s.",
        claims=(ClaimDraft(text="mean delay 24 s", evidence_refs=("q1",)),),
    )
    composer = ComposerPort(
        agent=FakeToolAgent(output=draft),
        budget=Budget(max_steps=1, max_tokens=1, max_seconds=1.0),
        results=world.results,
    )
    agents = replace(world.deps.agents, composer=composer)
    return replace(world.deps, agents=agents), world.settings


def _run(tmp_path: Path, *args: str, tty: bool, monkeypatch: pytest.MonkeyPatch) -> int:
    """The CLI on a completed study, with `stdout.isatty()` faked."""
    deps, settings = _completed_deps(tmp_path)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: tty)
    argv = ["how congested is the peak?", "--out", str(tmp_path), *args]
    return main(argv, deps=deps, settings=settings)


def test_a_completed_study_prints_the_report_the_composer_wrote(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    code = _run(tmp_path, tty=False, monkeypatch=monkeypatch)

    out = capsys.readouterr().out
    assert code == 0
    assert "The mean delay is about 24 s." in out
    assert "mean delay 24 s" in out


def test_auto_prints_plain_text_on_a_terminal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    code = _run(tmp_path, tty=True, monkeypatch=monkeypatch)

    out = capsys.readouterr().out
    assert code == 0
    assert out.startswith("STUDY ") and "\nSUMMARY\n" in out
    assert "# " not in out


def test_auto_prints_markdown_when_redirected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _run(tmp_path, tty=False, monkeypatch=monkeypatch)

    assert capsys.readouterr().out.startswith("# Study ")


@pytest.mark.parametrize(
    ("fmt", "tty", "starts"),
    [("text", False, "STUDY "), ("markdown", True, "# Study "), ("auto", True, "STUDY ")],
)
def test_format_forces_one_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    fmt: str,
    tty: bool,
    starts: str,
) -> None:
    _run(tmp_path, "--format", fmt, tty=tty, monkeypatch=monkeypatch)

    assert capsys.readouterr().out.startswith(starts)


@pytest.mark.parametrize(
    ("fmt", "tty"), [("auto", True), ("auto", False), ("text", True), ("markdown", False)]
)
def test_the_markdown_report_is_saved_whatever_the_format_printed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    fmt: str,
    tty: bool,
) -> None:
    _run(tmp_path, "--format", fmt, tty=tty, monkeypatch=monkeypatch)

    captured = capsys.readouterr()
    (saved,) = (tmp_path / "reports").glob("*.md")
    assert saved.read_text().startswith(f"# Study {saved.stem}: report")
    assert f"report saved: {saved}" in captured.err
    assert "report saved" not in captured.out


def test_a_failed_study_is_saved_as_markdown_too(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit.application._world import BASELINE_PLAN, World

    world = World(tmp_path, plans=(BASELINE_PLAN,), expert=(ConnectionError("503"),))
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    code = main(
        ["how congested is the peak?", "--out", str(tmp_path)],
        deps=world.deps,
        settings=world.settings,
    )

    captured = capsys.readouterr()
    (saved,) = (tmp_path / "reports").glob("*.md")
    assert code == 1
    assert captured.out.startswith("STUDY ") and "(failed)" in captured.out
    assert saved.read_text().startswith(f"# Study {saved.stem}: failed")


def test_the_parsers_model_call_reaches_the_jsonl_trace(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "resto.sqlite")
    usage = Usage(input_tokens=12, output_tokens=3, cost_usd=0.001)
    agent = FakeToolAgent(output=DESCRIBE, usage=usage)
    traces = tmp_path / "traces"
    deps = build_deps(
        db=db,
        agent=agent,
        budget=Budget(max_steps=1, max_tokens=1, max_seconds=1.0),
        tracer=JsonlTracer(traces),
        out_dir=tmp_path,
    )

    main(["how congested is the peak?"], deps=deps)

    db.close()
    (trace,) = traces.glob("*.jsonl")
    events = read_run(traces, trace.stem)
    assert ModelCall(usage) in events
