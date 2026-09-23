"""The CLI composition root (E5.10): the real wiring builds, and a request with no Input Parser
yet ends in an error without creating a Study or calling a model."""

from __future__ import annotations

from pathlib import Path

import pytest

from resto.adapters.persistence.sqlite.repositories import SqliteDatabase
from resto.application.ports.llm import Budget
from resto.interface.cli.main import build_deps, main
from tests.unit.adapters.llm._fakes import FakeToolAgent


class NullTracer:
    def emit(self, study_id: str, event: str, payload: object) -> None:
        raise AssertionError("no study, no trace")


def test_without_an_input_parser_no_study_is_created(
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

    code = main(["how congested is the peak?", "--mode", "forced"], deps=deps)

    db.close()
    err = capsys.readouterr().err
    assert code == 1
    assert "no study was created" in err and "E5.1" in err


def test_a_failed_study_is_rendered(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from tests.unit.application.use_cases.test_run_study import BASELINE_PLAN, World

    world = World(tmp_path, plans=(BASELINE_PLAN,), expert=(ConnectionError("503"),))

    code = main(["how congested is the peak?"], deps=world.deps)

    out = capsys.readouterr().out
    assert code == 1
    assert "Step `ask_expert` of phase 0 (the question as asked) failed (infrastructure)" in out
