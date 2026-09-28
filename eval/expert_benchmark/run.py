"""Expert benchmark CLI (docs/evaluating-resto.md §4). Spends API credit: run by hand only.

    python -m eval.expert_benchmark.run --name smoke --questions S00-desc-tt S03-desc-occ \
        --repetitions 1 --max-cost-usd 0.20
    python -m eval.expert_benchmark.run --name forced-v1 --repetitions 3 --workers 4 \
        --max-cost-usd 6
    python -m eval.expert_benchmark.run --name forced-v1 --report-only
    python -m eval.expert_benchmark.run --name abstention-v2 --mode both --repetitions 1 \
        --max-cost-usd 1.2

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
from eval.expert_benchmark.runner import Environment, run_benchmark
from eval.paid_runs import CostPolicy, add_paid_run_arguments, load_records, require_cap
from resto.domain.value_objects.question import Mode

HERE = Path(__file__).resolve().parent
EVAL = HERE.parent
MATRIX_DB = EVAL / "scenario_matrix" / "matrix.db"
DEV_NET = EVAL / "dev-net" / "dev-net.net.xml"

# Measured mean tokens per forced-mode run, `eval/expert_benchmark/runs/v1-forced-1rep.jsonl`
# (117 questions × 1 repetition): 45,119 input / 2,629 output. Free mode is not separately
# measured yet; the forced figure is used for both (decision 5, "one number feeds the $1 gate,
# the estimate-vs-cap check and the per-worker reservation").
INPUT_TOKENS_PER_JOB = 45_100
OUTPUT_TOKENS_PER_JOB = 2_650


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
    records = load_records(HERE / "runs" / f"{name}.jsonl")
    forced_records = [r for r in records if r.get("mode", Mode.FORCED.value) == Mode.FORCED.value]
    free_records = [r for r in records if r.get("mode") == Mode.FREE.value]
    scored = score_records(forced_records, questions)
    free_scored = score_records(free_records, questions)
    summary = summarize(scored, free_scored)
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
    add_paid_run_arguments(parser)
    parser.set_defaults(workers=4)
    parser.add_argument(
        "--mode",
        choices=["forced", "free", "both"],
        default="forced",
        help="which mode(s) to run against the model; 'both' runs forced and free under one job "
        "list and one --max-cost-usd cap (docs/evaluating-resto.md §4.5).",
    )
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args(argv)

    if not args.report_only:
        from resto.adapters.llm.anthropic_client import OpenRouterToolAgent
        from resto.adapters.llm.config import load_llm_config
        from resto.application.ports.llm import Budget

        max_cost_usd = require_cap(parser, args.max_cost_usd)
        modes = {"forced": [Mode.FORCED], "free": [Mode.FREE], "both": [Mode.FORCED, Mode.FREE]}[
            args.mode
        ]
        questions = load_bank(ids=args.questions)
        config = load_llm_config()
        cost_policy = CostPolicy.for_model(
            config.default_model,
            input_tokens_per_job=INPUT_TOKENS_PER_JOB,
            output_tokens_per_job=OUTPUT_TOKENS_PER_JOB,
            max_cost_usd=max_cost_usd,
            approved_over_1usd=args.approved_over_1usd,
        )
        runs = len(questions) * args.repetitions * len(modes)
        print(
            f"{len(questions)} questions × {args.repetitions} repetitions × {len(modes)} mode(s) "
            f"= {runs} runs, ~${cost_policy.per_job_estimate_usd * runs:.2f} estimated; "
            f"cap: ${max_cost_usd:.2f}"
        )
        outcome = run_benchmark(
            questions,
            repetitions=args.repetitions,
            agent=OpenRouterToolAgent(config),
            budget=Budget(
                max_steps=config.max_steps, max_tokens=config.max_output_tokens, max_seconds=300.0
            ),
            environment=dev_net_environment,
            out_file=HERE / "runs" / f"{args.name}.jsonl",
            cost_policy=cost_policy,
            modes=modes,
            workers=args.workers,
        )
        print(outcome)

    print(f"report: {write_report(args.name, args.questions)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
