"""Expert benchmark CLI (docs/evaluating-resto.md §4). Spends API credit: run by hand only.

    python -m eval.expert_benchmark.run --name smoke --questions S00-desc-tt S03-desc-occ \
        --repetitions 1 --max-cost-usd 0.20
    python -m eval.expert_benchmark.run --name forced-v1 --repetitions 3 --workers 4 \
        --max-cost-usd 6
    python -m eval.expert_benchmark.run --name forced-v1 --report-only

Raw runs go to `runs/<name>.jsonl` (gitignored, resumable); the report to `reports/<name>.md` and
`reports/<name>.json`. Run inside the `resto` conda env, with `SUMO_HOME` unset and
`OPENROUTER_API_KEY` in `.env`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from eval.expert_benchmark.bank import load_bank
from eval.expert_benchmark.report import render_markdown, score_records, summarize
from eval.expert_benchmark.runner import Environment, load_records, run_benchmark

HERE = Path(__file__).resolve().parent
EVAL = HERE.parent
MATRIX_DB = EVAL / "scenario_matrix" / "matrix.db"
DEV_NET = EVAL / "dev-net" / "dev-net.net.xml"
AVG_COST_PER_RUN_USD = 0.012  # smoke run 2026-09-17, docs/evaluating-resto.md §4.7


def dev_net_environment() -> Environment:
    from resto.adapters.persistence.sqlite.repositories import SqliteDatabase
    from resto.adapters.sumo.netxml import SumolibNetworkQuery

    db = SqliteDatabase(MATRIX_DB)
    return Environment(
        results=db.results,
        scenarios=db.scenarios,
        query=SumolibNetworkQuery(DEV_NET),
        close=db.close,
    )


def write_report(name: str, questions_ids: list[str] | None) -> Path:
    questions = load_bank(ids=questions_ids)
    scored = score_records(load_records(HERE / "runs" / f"{name}.jsonl"), questions)
    summary = summarize(scored)
    reports = HERE / "reports"
    reports.mkdir(exist_ok=True)
    (reports / f"{name}.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    path = reports / f"{name}.md"
    path.write_text(render_markdown(name, summary, scored), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", required=True)
    parser.add_argument("--questions", nargs="*", help="question ids; default: the whole bank")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-cost-usd", type=float, required=False)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args(argv)

    if not args.report_only:
        from resto.adapters.llm.anthropic_client import OpenRouterToolAgent
        from resto.adapters.llm.config import load_llm_config
        from resto.adapters.llm.pricing import estimate_cost_usd
        from resto.application.ports.llm import Budget

        questions = load_bank(ids=args.questions)
        runs = len(questions) * args.repetitions
        print(
            f"{len(questions)} questions × {args.repetitions} repetitions = {runs} runs, "
            f"~${runs * AVG_COST_PER_RUN_USD:.2f} estimated; cap: "
            f"{'none' if args.max_cost_usd is None else f'${args.max_cost_usd:.2f}'}"
        )
        config = load_llm_config()
        outcome = run_benchmark(
            questions,
            repetitions=args.repetitions,
            agent=OpenRouterToolAgent(config),
            budget=Budget(
                max_steps=config.max_steps, max_tokens=config.max_output_tokens, max_seconds=300.0
            ),
            environment=dev_net_environment,
            out_file=HERE / "runs" / f"{args.name}.jsonl",
            model=config.default_model,
            price=lambda i, o: estimate_cost_usd(config.default_model, i, o),
            workers=args.workers,
            max_cost_usd=args.max_cost_usd,
        )
        print(outcome)

    print(f"report: {write_report(args.name, args.questions)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
