"""Formatting shared by the Markdown outputs: money, cap, generated-file line, excess."""

from __future__ import annotations

from eval.budget.model import Plan, PlanTotals, Range

GENERATED = "Generated from `eval/budget/cost-data.toml` by `python -m eval.budget`; do not edit."


def usd(r: Range) -> str:
    return f"${r.low:.2f} to ${r.high:.2f}"


def cap(plan: Plan) -> str:
    return f"${plan.cap_usd:g}"


def share(part: Range, total: Range) -> str:
    low = part.low / total.low if total.low else 0.0
    high = part.high / total.high if total.high else 0.0
    return f"{low:.0%} of the low, {high:.0%} of the high"


def excess_cell(totals: PlanTotals) -> str:
    """Table cell: `none`, the range, or the range marked as only possible."""
    excess = totals.excess_over_cap
    if excess.high <= 0:
        return "none"
    return usd(excess) if excess.low > 0 else f"up to ${excess.high:.2f} (may exceed)"


def excess_sentence(plan: Plan, totals: PlanTotals, subject: str) -> str:
    """One honest sentence: certain excess, possible excess (low total under the cap), or none."""
    excess = totals.excess_over_cap
    if excess.high <= 0:
        return f"{subject} stays within the {cap(plan)} reference."
    if excess.low > 0:
        return (
            f"{subject} exceeds the {cap(plan)} reference by {usd(excess)} "
            "(combined V1 and V2, with contingency). That excess is what the funding request "
            "can ask for."
        )
    return (
        f"{subject} may exceed the {cap(plan)} reference: the low estimate is within it, the "
        f"high estimate is over by up to ${excess.high:.2f} (combined V1 and V2, with "
        "contingency). That possible excess is what the funding request can ask for."
    )
