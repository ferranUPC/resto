"""Input Parser benchmark CLI (E5.1; docs/evaluating-resto.md §5). Spends API credit: run by hand.

    python -m eval.parser_benchmark.run --name smoke --model deepseek/deepseek-v4.1-flash \
        --requests R001 R021 R065 --max-cost-usd 0.05
    python -m eval.parser_benchmark.run --name v1-dev --model deepseek/deepseek-v4.1-flash \
        --max-cost-usd 0.40
    python -m eval.parser_benchmark.run --name v1-dev --report-only

`--model` is always explicit and must be one of `APPROVED_MODELS` (CLAUDE.md cost policy). The
prompt is tuned on the dev split (the default); E5.1 Done is measured once on held-out, which
needs `--split held_out --final`. Raw runs go to `runs/<name>.jsonl` (gitignored, resumable); the
report to `reports/<name>.md` and `reports/<name>.json`. Run inside the `resto` conda env with
`OPENROUTER_API_KEY` in `.env`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from eval.parser_benchmark.report import render_markdown, score_records, summarize_run
from eval.parser_benchmark.runner import load_records, run_benchmark
from eval.request_bank.bank import BankRequest, bank_requests

HERE = Path(__file__).resolve().parent

APPROVED_MODELS = (
    "deepseek/deepseek-v4.1-flash",  # the default agent model
    "mistralai/ministral-3b-2512",  # comparison runs (evaluating-resto.md §5, 2026-09-23)
    "google/gemma-3-12b-it",
)
# Conservative per-call token estimate (prompt + Question schema in, one Question out), with a
# retry on one call in five; replace with measured means once a run exists.
_TOKENS_PER_REQUEST = (6000, 900)


def select(
    split: str, ids: list[str] | None = None, concepts: list[str] | None = None
) -> list[BankRequest]:
    """Exact request ids, or every request of the given concepts, or a whole split."""
    requests = bank_requests()
    if ids or concepts:
        return [r for r in requests if r.id in (ids or ()) or r.concept_id in (concepts or ())]
    return [r for r in requests if split == "all" or r.split == split]


def estimate_usd(model: str, n_runs: int) -> float | None:
    from resto.adapters.llm.pricing import estimate_cost_usd

    per_run = estimate_cost_usd(model, *_TOKENS_PER_REQUEST)
    return None if per_run is None else per_run * n_runs


def write_report(name: str) -> Path:
    records = load_records(HERE / "runs" / f"{name}.jsonl")
    scored = score_records(records, bank_requests())
    summary = summarize_run(scored)
    reports = HERE / "reports"
    reports.mkdir(exist_ok=True)
    (reports / f"{name}.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    path = reports / f"{name}.md"
    path.write_text(render_markdown(name, summary, scored), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", required=True)
    parser.add_argument("--model", choices=APPROVED_MODELS)
    parser.add_argument("--split", choices=["dev", "held_out", "all"], default="dev")
    parser.add_argument("--final", action="store_true", help="allow running on held-out")
    parser.add_argument("--requests", nargs="*", help="exact request ids (any split)")
    parser.add_argument("--concepts", nargs="*", help="concept ids, with all their variants")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-cost-usd", type=float)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args(argv)

    if not args.report_only:
        if args.model is None:
            parser.error("--model is required unless --report-only")
        requests = select(args.split, args.requests, args.concepts)
        # Checked on what was selected, so --requests/--concepts cannot reach held-out either.
        if not args.final and any(r.split == "held_out" for r in requests):
            parser.error("held-out is for measuring Done once: pass --final to run it")
        runs = len(requests) * args.repetitions
        estimate = estimate_usd(args.model, runs)
        print(
            f"{len(requests)} requests × {args.repetitions} repetitions = {runs} runs on "
            f"{args.model}, ~${estimate:.2f} estimated"
            if estimate is not None else f"{runs} runs on {args.model}, no price known"
        )
        if args.dry_run:
            return 0
        if estimate is None or estimate > 1.0:
            print("no estimate, or above $1: log it in docs/evaluating-resto.md §7 instead "
                  "(CLAUDE.md)", file=sys.stderr)
            return 2
        if args.max_cost_usd is None:
            parser.error("--max-cost-usd is required for a paid run")

        from resto.adapters.llm.anthropic_client import OpenRouterToolAgent
        from resto.adapters.llm.config import load_llm_config
        from resto.adapters.llm.pricing import estimate_cost_usd
        from resto.application.ports.llm import Budget

        config = load_llm_config()
        outcome = run_benchmark(
            requests,
            repetitions=args.repetitions,
            agent=OpenRouterToolAgent(config, model=args.model),
            budget=Budget(config.max_steps, config.max_output_tokens, max_seconds=120.0),
            out_file=HERE / "runs" / f"{args.name}.jsonl",
            model=args.model,
            price=lambda i, o: estimate_cost_usd(args.model, i, o),
            workers=args.workers,
            max_cost_usd=args.max_cost_usd,
        )
        print(outcome)

    print(f"report: {write_report(args.name)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
