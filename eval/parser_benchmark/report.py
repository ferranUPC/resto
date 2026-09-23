"""Scores raw Input Parser runs against the request bank's gold and renders the report (E5.1).

Every (request, repetition) record is scored on its own; the E5.1 thresholds are checked on all of
them together, and `intent_agreement` (§4.1, ≥ 95 %) needs at least two repetitions. Consistency
across a concept's variants uses repetition 1. Breakdowns cover every axis of the bank, so a
prompt change can be read per language, register, vagueness, noise and category.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from eval.request_bank.bank import BankRequest
from eval.request_bank.concepts import AmbiguousGold
from eval.request_bank.generate import describe_question
from eval.request_bank.scoring import (
    AXES,
    INTENT_AGREEMENT_THRESHOLD,
    THRESHOLDS,
    Rate,
    RequestScore,
    consistency,
    done,
    intent_agreement,
    score_request,
    summarize,
)
from resto.application.schemas import adapter_for
from resto.domain.value_objects.question import Question

GRADED = tuple(THRESHOLDS)
"""The metrics with an E5.1 threshold, shown in every breakdown."""
_FIELDS = {  # metric -> RequestScore attribute
    "schema_validity": "valid",
    "intent": "intent",
    "interventions": "interventions",
    "topology_changes": "topology_changes",
    "metrics_of_interest": "metrics_of_interest",
    "ambiguity_detection": "ambiguity_detected",
    "arm_structure": "arm_structure",
}


@dataclass(frozen=True, slots=True)
class Scored:
    request: BankRequest
    repetition: int
    score: RequestScore
    predicted: Question | None
    record: Mapping[str, Any]


def prediction(record: Mapping[str, Any]) -> Question | None:
    data = record.get("question")
    return None if data is None else adapter_for(Question).validate_python(data)


def score_records(
    records: Sequence[Mapping[str, Any]], requests: Sequence[BankRequest]
) -> list[Scored]:
    """Records of requests no longer in the bank are ignored."""
    by_id = {r.id: r for r in requests}
    scored = []
    for record in records:
        request = by_id.get(record["request_id"])
        if request is None:
            continue
        predicted = prediction(record)
        scored.append(
            Scored(request, record["repetition"], score_request(request.gold, predicted),
                   predicted, record)
        )
    return sorted(scored, key=lambda s: (s.request.id, s.repetition))


def failed_fields(scored: Scored) -> list[str]:
    score = scored.score
    failed = []
    for metric, attr in _FIELDS.items():
        if metric == "arm_structure" and not score.multi_arm:
            continue
        if getattr(score, attr) is False:
            failed.append(metric)
    return failed


def _rate(rate: Rate) -> dict[str, Any]:
    return {"hits": rate.hits, "total": rate.total, "value": rate.value}


def summarize_run(scored: Sequence[Scored]) -> dict[str, Any]:
    records = [s.record for s in scored]
    summary = summarize([s.score for s in scored])
    by_rep: dict[int, dict[str, Question | None]] = defaultdict(dict)
    for s in scored:
        by_rep[s.repetition][s.request.id] = s.predicted
    requests = {s.request.id: s.request for s in scored}
    agreement = intent_agreement(list(by_rep.values())) if len(by_rep) > 1 else None
    verdict = done(summary)
    if agreement is not None:
        verdict["intent_agreement"] = (
            agreement.value is not None and agreement.value >= INTENT_AGREEMENT_THRESHOLD
        )
    first = min(by_rep) if by_rep else 1
    breakdowns = {}
    for axis in AXES:
        groups: dict[str, list[RequestScore]] = defaultdict(list)
        for s in scored:
            groups[AXES[axis](s.request)].append(s.score)
        breakdowns[axis] = {
            value: {m: _rate(r) for m, r in summarize(group).items() if m in GRADED}
            for value, group in sorted(groups.items())
        }
    return {
        "requests": len(requests),
        "records": len(records),
        "repetitions": sorted(by_rep),
        "models": sorted({r["model"] for r in records}),
        "parser_versions": sorted({r["parser_version"] for r in records}),
        "cost_usd": round(sum(r["cost_usd"] or 0.0 for r in records), 4),
        "mean_input_tokens": round(sum(r["input_tokens"] for r in records) / len(records))
        if records else 0,
        "mean_output_tokens": round(sum(r["output_tokens"] for r in records) / len(records))
        if records else 0,
        "stop_reasons": dict(Counter(r["stop_reason"] for r in records)),
        "metrics": {name: _rate(rate) for name, rate in summary.items()},
        "done": verdict,
        "intent_agreement": None if agreement is None else _rate(agreement),
        "consistency": _rate(consistency(list(requests.values()), by_rep.get(first, {}))),
        "breakdowns": breakdowns,
    }


def _pct(rate: Mapping[str, Any]) -> str:
    value = rate["value"]
    return "—" if value is None else f"{100 * value:.1f} % ({rate['hits']}/{rate['total']})"


def _gold_lines(request: BankRequest) -> list[str]:
    gold = request.gold
    if isinstance(gold, AmbiguousGold):
        intent = f", intent `{gold.intent}`" if gold.intent else ""
        return [f"expect `ambiguities[]` ({gold.reason}{intent})"]
    return describe_question(gold)


def render_markdown(name: str, summary: Mapping[str, Any], scored: Sequence[Scored]) -> str:
    lines = [
        f"# Input Parser benchmark — {name}",
        "",
        f"{summary['requests']} requests, {summary['records']} runs (repetitions "
        f"{summary['repetitions']}), models {summary['models']}, parser "
        f"{summary['parser_versions']}; ${summary['cost_usd']:.4f}, mean "
        f"{summary['mean_input_tokens']} input / {summary['mean_output_tokens']} output tokens; "
        f"stop reasons {summary['stop_reasons']}.",
        "",
        "| Metric | Result | E5.1 threshold | Met |",
        "|---|---|---|---|",
    ]
    for metric, threshold in THRESHOLDS.items():
        met = "yes" if summary["done"][metric] else "**no**"
        result = _pct(summary["metrics"][metric])
        lines.append(f"| {metric} | {result} | ≥ {threshold:.0%} | {met} |")
    if summary["intent_agreement"] is not None:
        met = "yes" if summary["done"]["intent_agreement"] else "**no**"
        lines.append(
            f"| intent_agreement | {_pct(summary['intent_agreement'])} | "
            f"≥ {INTENT_AGREEMENT_THRESHOLD:.0%} | {met} |"
        )
    lines += ["", "Reported, not graded:", ""]
    for metric, rate in summary["metrics"].items():
        if metric not in THRESHOLDS:
            lines.append(f"- {metric}: {_pct(rate)}")
    lines.append(f"- consistency across variants: {_pct(summary['consistency'])}")

    for axis, groups in summary["breakdowns"].items():
        lines += ["", f"## By {axis}", "", "| " + axis + " | " + " | ".join(GRADED) + " |",
                  "|---" * (len(GRADED) + 1) + "|"]
        for value, metrics in groups.items():
            cells = [_pct(metrics[m]) if metrics[m]["total"] else "—" for m in GRADED]
            lines.append(f"| {value} | " + " | ".join(cells) + " |")

    failures = [s for s in scored if failed_fields(s)]
    lines += ["", f"## Failures ({len(failures)})", ""]
    for s in failures:
        lines += [
            f"### `{s.request.id}` rep {s.repetition} — {', '.join(failed_fields(s))}",
            "",
            f"> {s.request.text}",
            "",
            "Gold: " + "\n".join(_gold_lines(s.request)),
            "",
        ]
        if s.predicted is None:
            lines.append(f"Parsed: none ({s.record['stop_reason']}: {s.record['failure']})")
        else:
            lines.append("Parsed: " + "\n".join(describe_question(s.predicted)))
        lines.append("")
    return "\n".join(lines) + "\n"

