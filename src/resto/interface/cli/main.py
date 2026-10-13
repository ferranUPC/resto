"""CLI entrypoint. `main` loads the LLM config, opens the database, builds a `RunStudy` with
`resto.interface.dependencies.build_run_study`, calls `RunStudy.execute`, closes the database,
prints the study and saves its Markdown report. A request the Input Parser cannot turn into a
`Question` raises `ParserFailed`, and the CLI reports it without creating a Study. Tests pass their
own `RunStudy` through the `run_study` keyword, which skips the config, the database and the wiring.

    python -m resto.interface.cli.main "how congested is the peak?" [--mode forced]
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from resto.adapters.persistence.sqlite.repositories import SqliteDatabase
from resto.adapters.tracing.jsonl import JsonlTracer
from resto.application.executor import StudySettings
from resto.application.ports.llm import Budget
from resto.application.use_cases.run_study import ParserFailed, RunStudy
from resto.domain.entities.study import Study, StudyStatus
from resto.domain.value_objects.question import Mode
from resto.interface.dependencies import AGENT_SECONDS, build_run_study
from resto.interface.render import render_study, render_study_text


def _save_report(study: Study, out_dir: Path) -> None:
    """The study as Markdown in `<out_dir>/reports/<study_id>.md`, whatever was printed. The path
    goes to stderr so that stdout holds only the report."""
    path = out_dir / "reports" / f"{study.study_id}.md"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_study(study), encoding="utf-8")
    except OSError as e:
        print(f"warning: the report was not saved: {e}", file=sys.stderr)
        return
    print(f"report saved: {path}", file=sys.stderr)


def main(
    argv: Sequence[str] | None = None,
    *,
    run_study: RunStudy | None = None,
) -> int:
    """`run_study` replaces the real wiring (tests)."""
    parser = argparse.ArgumentParser(prog="resto", description="Run one RESTO study.")
    parser.add_argument("text", help="the question, in natural language")
    parser.add_argument("--mode", choices=[m.value for m in Mode], default=None)
    parser.add_argument("--db", type=Path, default=Path("resto.sqlite"))
    parser.add_argument("--out", type=Path, default=Path("runs"))
    parser.add_argument(
        "--format",
        choices=("auto", "text", "markdown"),
        default="auto",
        help="auto: plain text on a terminal, Markdown when redirected or piped",
    )
    args = parser.parse_args(argv)
    mode = Mode(args.mode) if args.mode else None

    db: SqliteDatabase | None = None
    if run_study is None:
        from resto.adapters.llm.anthropic_client import OpenRouterToolAgent
        from resto.adapters.llm.config import (
            MissingApiKeyError,
            load_llm_config,
            load_rounds_config,
        )

        try:
            config = load_llm_config()
        except MissingApiKeyError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        db = SqliteDatabase(args.db)
        budget = Budget(config.max_steps, config.max_output_tokens, AGENT_SECONDS)
        tracer = JsonlTracer(args.out / "traces")
        agent = OpenRouterToolAgent(config)
        rounds = load_rounds_config()
        settings = StudySettings(
            out_dir=args.out,
            network_max_rounds=rounds.network_max_rounds,
            calibration_max_rounds=rounds.calibration_max_rounds,
        )
        run_study = build_run_study(
            db=db, agent=agent, budget=budget, tracer=tracer, settings=settings
        )
    try:
        study = run_study.execute(args.text, mode=mode)
    except ParserFailed as e:
        print(f"error: no study was created: {e}", file=sys.stderr)
        return 1
    finally:
        if db is not None:
            db.close()
    as_text = args.format == "text" or (args.format == "auto" and sys.stdout.isatty())
    print(render_study_text(study) if as_text else render_study(study), end="")
    _save_report(study, args.out)
    return 0 if study.status is StudyStatus.COMPLETED else 1


if __name__ == "__main__":
    sys.exit(main())
