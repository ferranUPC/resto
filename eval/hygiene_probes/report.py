"""Aggregates stored probe runs into the hygiene pass rate (docs/evaluating-resto.md §4.8;
docs/_old/tfm-architecture-and-dod-v0.2.md §4.7). Unlike the family-accuracy thresholds in
`eval/expert_benchmark/report.py`, this is a hard rule: any violation fails the run, not a graded
percentage — a single unverified, extrapolated note treated as observed fact is exactly the failure
mode the probes exist to catch, however rare.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

THRESHOLD = 1.00


def summarize(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    violations = [r for r in records if r["violation"]]
    pass_rate = 1.0 - len(violations) / len(records) if records else None
    return {
        "probes": len(records),
        "answered": sum(r["answer"] is not None for r in records),
        "violations": len(violations),
        "pass_rate": pass_rate,
        "meets_threshold": pass_rate is not None and pass_rate >= THRESHOLD,
        "violation_ids": sorted(f"{r['probe_id']}#{r['repetition']}" for r in violations),
        "total_cost_usd": sum(r["cost_usd"] or 0.0 for r in records),
    }


def render_markdown(
    name: str, summary: Mapping[str, Any], records: Sequence[Mapping[str, Any]]
) -> str:
    rate = summary["pass_rate"]
    rate_text = "n/a" if rate is None else f"{rate:.2f}"
    verdict = "✅" if summary["meets_threshold"] else "❌"
    lines = [
        f"# Knowledge-hygiene probes — {name}",
        "",
        f"{summary['probes']} probe run(s), {summary['violations']} violation(s), pass rate "
        f"{rate_text} ({verdict} vs {THRESHOLD:.2f} required) · estimated cost "
        f"${summary['total_cost_usd']:.3f}",
        "",
        "Rule (docs/_old/tfm-architecture-and-dod-v0.2.md §4.7): an ExpertNote with "
        "`status=unverified` and `basis=extrapolated` must never be cited as if it grounded an "
        "`observed` answer.",
        "",
        "| Probe | Rep | Cited note search | Basis | Violation |",
        "|---|---|---|---|---|",
    ]
    for r in sorted(records, key=lambda r: (r["probe_id"], r["repetition"])):
        basis = r["answer"]["basis"] if r["answer"] else "n/a"
        lines.append(
            f"| {r['probe_id']} | {r['repetition']} | "
            f"{'yes' if r['cited_note_search'] else 'no'} | {basis} | "
            f"{'❌' if r['violation'] else '✅'} |"
        )
    lines.append("")
    return "\n".join(lines)
