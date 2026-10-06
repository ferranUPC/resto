"""Knowledge-hygiene probes CLI (E4.6; eval/README.md §4.8). Spends API credit: run
by hand only.

    python -m eval.hygiene_probes.run --name smoke --probes S00-desc-occ S00-desc-tt \
        --repetitions 1 --max-cost-usd 0.05
    python -m eval.hygiene_probes.run --name hygiene-v1 --repetitions 1 --max-cost-usd 1
    python -m eval.hygiene_probes.run --name hygiene-v1 --report-only

Raw runs go to `runs/<name>.jsonl` (gitignored, resumable); the report to `reports/<name>.md` and
`reports/<name>.json`. Run inside the `resto` conda env, with `SUMO_HOME` unset and
`OPENROUTER_API_KEY` in `.env`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from eval.hygiene_probes.probes import load_probes
from eval.hygiene_probes.report import render_markdown, summarize
from eval.hygiene_probes.runner import run_probes
from eval.paid_runs import CostPolicy, add_paid_run_arguments, load_records, require_cap

HERE = Path(__file__).resolve().parent
EVAL = HERE.parent
DEV_NET = EVAL / "dev-net" / "dev-net.net.xml"
# Measured mean tokens per probe run, `eval/hygiene_probes/runs/hygiene-v1.jsonl` (20 probes ×
# 1 repetition, 2026-09): 28,237 input / 2,256 output. Replaces the earlier dollar-based
# `AVG_COST_PER_RUN_USD` guess (decision 5, "tokens per job... from its smoke run").
INPUT_TOKENS_PER_JOB = 28_200
OUTPUT_TOKENS_PER_JOB = 2_300


def write_report(name: str) -> Path:
    records = load_records(HERE / "runs" / f"{name}.jsonl")
    summary = summarize(records)
    reports = HERE / "reports"
    reports.mkdir(exist_ok=True)
    (reports / f"{name}.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    path = reports / f"{name}.md"
    path.write_text(render_markdown(name, summary, records), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", required=True)
    parser.add_argument("--probes", nargs="*", help="probe (question) ids; default: all 20")
    parser.add_argument("--repetitions", type=int, default=1)
    add_paid_run_arguments(parser)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args(argv)

    if not args.report_only:
        from resto.adapters.llm.anthropic_client import OpenRouterToolAgent
        from resto.adapters.llm.config import load_llm_config
        from resto.adapters.sumo.netxml import SumolibNetworkQuery
        from resto.application.ports.llm import Budget

        max_cost_usd = require_cap(parser, args.max_cost_usd)
        probes = load_probes(ids=args.probes)
        config = load_llm_config()
        cost_policy = CostPolicy.for_model(
            config.default_model,
            input_tokens_per_job=INPUT_TOKENS_PER_JOB,
            output_tokens_per_job=OUTPUT_TOKENS_PER_JOB,
            max_cost_usd=max_cost_usd,
            approved_over_1usd=args.approved_over_1usd,
        )
        runs = len(probes) * args.repetitions
        print(
            f"{len(probes)} probes × {args.repetitions} repetitions = {runs} runs, "
            f"~${cost_policy.per_job_estimate_usd * runs:.2f} estimated; cap: ${max_cost_usd:.2f}"
        )
        outcome = run_probes(
            probes,
            repetitions=args.repetitions,
            agent=OpenRouterToolAgent(config),
            budget=Budget(
                max_steps=config.max_steps, max_tokens=config.max_output_tokens, max_seconds=300.0
            ),
            query=lambda: SumolibNetworkQuery(DEV_NET),
            out_file=HERE / "runs" / f"{args.name}.jsonl",
            cost_policy=cost_policy,
            workers=args.workers,
        )
        print(outcome)

    print(f"report: {write_report(args.name)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
