"""Scores stored benchmark runs and aggregates them (docs/evaluating-resto.md §4.4–§4.6): metrics
per repetition, then mean ± std across repetitions, compared with the DoD §4.7 thresholds."""

from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from eval.expert_benchmark.bank import BenchmarkQuestion, Family
from eval.expert_benchmark.scoring import Score, score_answer
from resto.application.schemas import adapter_for
from resto.domain.value_objects.expert_answer import ExpertAnswer

# DoD §4.7 thresholds on DEV-NET (tfm-architecture-and-dod.md is the source of truth).
THRESHOLDS: dict[str, tuple[str, float]] = {
    "descriptive_accuracy": (">=", 0.90),
    "diag_mean_jaccard": (">=", 0.60),
    "cf_dir_accuracy": (">=", 0.75),
    "cf_band_accuracy": (">=", 0.50),
    "brier": ("<=", 0.25),
    "accepted_share": (">=", 1.00),
}
METRIC_ORDER = (
    "descriptive_accuracy",
    "desc_occ_accuracy",
    "desc_tt_accuracy",
    "diag_accuracy",
    "diag_mean_jaccard",
    "cf_dir_accuracy",
    "cf_topk_accuracy",
    "cf_topk_mean_jaccard",
    "cf_band_accuracy",
    "brier",
    "accepted_share",
)


@dataclass(frozen=True, slots=True)
class ScoredRun:
    question: BenchmarkQuestion
    repetition: int
    score: Score
    answer: ExpertAnswer | None
    record: Mapping[str, Any]


def score_records(
    records: Iterable[Mapping[str, Any]], questions: Sequence[BenchmarkQuestion]
) -> list[ScoredRun]:
    by_id = {q.id: q for q in questions}
    adapter = adapter_for(ExpertAnswer)
    scored = []
    for record in records:
        question = by_id.get(record["question_id"])
        if question is None:
            continue
        answer = None if record["answer"] is None else adapter.validate_python(record["answer"])
        score = score_answer(question, answer, rejection=record["rejection"])
        scored.append(ScoredRun(question, record["repetition"], score, answer, record))
    return scored


def _accuracy(runs: Sequence[ScoredRun]) -> float | None:
    return sum(r.score.correct for r in runs) / len(runs) if runs else None


def _mean_jaccard(runs: Sequence[ScoredRun]) -> float | None:
    values = [r.score.jaccard or 0.0 for r in runs]
    return statistics.mean(values) if values else None


def repetition_metrics(runs: Sequence[ScoredRun]) -> dict[str, float | None]:
    by_family: dict[Family, list[ScoredRun]] = defaultdict(list)
    for run in runs:
        by_family[run.question.family].append(run)
    answered = [r for r in runs if r.answer is not None]
    return {
        "descriptive_accuracy": _accuracy(by_family[Family.DESC_OCC] + by_family[Family.DESC_TT]),
        "desc_occ_accuracy": _accuracy(by_family[Family.DESC_OCC]),
        "desc_tt_accuracy": _accuracy(by_family[Family.DESC_TT]),
        "diag_accuracy": _accuracy(by_family[Family.DIAG]),
        "diag_mean_jaccard": _mean_jaccard(by_family[Family.DIAG]),
        "cf_dir_accuracy": _accuracy(by_family[Family.CF_DIR]),
        "cf_topk_accuracy": _accuracy(by_family[Family.CF_TOPK]),
        "cf_topk_mean_jaccard": _mean_jaccard(by_family[Family.CF_TOPK]),
        "cf_band_accuracy": _accuracy(by_family[Family.CF_BAND]),
        "brier": statistics.mean(
            (r.answer.confidence - float(r.score.correct)) ** 2 for r in answered if r.answer
        )
        if answered
        else None,
        "accepted_share": sum(r.record["rejection"] is None for r in runs) / len(runs)
        if runs
        else None,
    }


def summarize(scored: Sequence[ScoredRun]) -> dict[str, Any]:
    by_rep: dict[int, list[ScoredRun]] = defaultdict(list)
    for run in scored:
        by_rep[run.repetition].append(run)
    per_rep = {rep: repetition_metrics(runs) for rep, runs in sorted(by_rep.items())}

    aggregate: dict[str, dict[str, float | int | None]] = {}
    for metric in METRIC_ORDER:
        values = [v for m in per_rep.values() if (v := m[metric]) is not None]
        aggregate[metric] = {
            "mean": statistics.mean(values) if values else None,
            "std": statistics.stdev(values) if len(values) >= 2 else None,
            "repetitions": len(values),
        }

    by_basis: dict[str, list[bool]] = defaultdict(list)
    cost: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for run in scored:
        if run.answer is not None:
            by_basis[run.answer.basis.value].append(run.score.correct)
        family = cost[run.question.family.value]
        family["runs"] += 1
        family["input_tokens"] += run.record["input_tokens"]
        family["output_tokens"] += run.record["output_tokens"]
        family["cost_usd"] += run.record["cost_usd"] or 0.0

    return {
        "runs": len(scored),
        "questions": len({r.question.id for r in scored}),
        "repetitions": sorted(by_rep),
        "budget_stops": sum(r.record["stop_reason"] == "budget" for r in scored),
        "per_repetition": per_rep,
        "aggregate": aggregate,
        "accuracy_by_basis": {
            basis: {"answers": len(hits), "accuracy": sum(hits) / len(hits)}
            for basis, hits in sorted(by_basis.items())
        },
        "cost_by_family": {k: dict(v) for k, v in sorted(cost.items())},
        "total_cost_usd": sum(r.record["cost_usd"] or 0.0 for r in scored),
    }


def _fmt(value: float | int | None, digits: int = 2) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _meets(metric: str, mean: float | int | None) -> str:
    if metric not in THRESHOLDS or mean is None:
        return ""
    op, bound = THRESHOLDS[metric]
    ok = mean >= bound if op == ">=" else mean <= bound
    return f"{op} {bound:.2f} {'✅' if ok else '❌'}"


def render_markdown(name: str, summary: Mapping[str, Any], scored: Sequence[ScoredRun]) -> str:
    models = sorted({str(r.record["model"]) for r in scored})
    lines = [
        f"# Expert benchmark — {name}",
        "",
        f"Model: {', '.join(models) or 'n/a'} · {summary['questions']} questions × repetitions "
        f"{summary['repetitions']} = {summary['runs']} runs · budget stops: "
        f"{summary['budget_stops']} · estimated cost: ${summary['total_cost_usd']:.3f}",
        "",
        "Scoring rules: docs/evaluating-resto.md §4.4. Thresholds: DoD §4.7 (DEV-NET).",
        "",
        "| Metric | Mean | Std | DoD |",
        "|---|---|---|---|",
    ]
    for metric in METRIC_ORDER:
        agg = summary["aggregate"][metric]
        mean, std = agg["mean"], agg["std"]
        lines.append(f"| {metric} | {_fmt(mean)} | {_fmt(std)} | {_meets(metric, mean)} |")
    lines += ["", "## Accuracy by basis", "", "| Basis | Answers | Accuracy |", "|---|---|---|"]
    for basis, row in summary["accuracy_by_basis"].items():
        lines.append(f"| {basis} | {row['answers']} | {_fmt(row['accuracy'])} |")
    lines += [
        "",
        "## Cost by family",
        "",
        "| Family | Runs | Input tokens | Output tokens | Cost (USD) |",
        "|---|---|---|---|---|",
    ]
    for family, row in summary["cost_by_family"].items():
        lines.append(
            f"| {family} | {int(row['runs'])} | {int(row['input_tokens'])} | "
            f"{int(row['output_tokens'])} | {row['cost_usd']:.4f} |"
        )
    lines += ["", "## Per question", "", "| Question | Rep | Correct | Detail |"]
    lines.append("|---|---|---|---|")
    for run in sorted(scored, key=lambda r: (r.question.id, r.repetition)):
        detail = run.score.detail.replace("|", "\\|")
        lines.append(
            f"| {run.question.id} | {run.repetition} | {'✅' if run.score.correct else '❌'} | "
            f"{detail} |"
        )
    lines.append("")
    return "\n".join(lines)
