"""Renders the interactive budget page: one HTML file with the computed figures embedded.

Python computes every per-suite, per-tier figure before contingency with the same functions as
the Markdown plan (`tier_cost`, `tier_cost_by_basis`). The page script adds those up for the
selected tiers, applies the per-suite and global contingency shares (editable) and works out the
excess over the cap; a parity test checks its totals against `compute`. The selection (tier per
suite, contingencies) lives in the address fragment.
"""

from __future__ import annotations

import json
from pathlib import Path

from eval.budget.model import (
    BASES,
    DEFAULT_TIER,
    PASSES,
    TIERS,
    Plan,
    Range,
    Suite,
    Tier,
    pending_levels,
    tier_cost,
    tier_cost_by_basis,
)

TEMPLATE = Path(__file__).with_name("page_template.html")


def _pair(r: Range) -> list[float]:
    return [r.low, r.high]


def _tier(suite: Suite, tier: Tier, plan: Plan) -> dict[str, object]:
    cost = tier_cost(tier, plan.levels)
    basis = tier_cost_by_basis(tier, plan.levels)
    levels = sorted({lv for stage in tier.stages for lv, _ in stage.models})
    return {
        "net": {p: _pair(cost[p]) for p in PASSES},
        "basis": {b: _pair(basis[b]) for b in BASES},
        "hours": _pair(tier.reviewer_hours),
        "levels": levels,
        "pending": bool(pending_levels(suite, tier, plan.levels)),
    }


def page_data(plan: Plan) -> dict[str, object]:
    """The embedded data: per-suite, per-tier figures before contingency; no model names."""
    suites = []
    for s in plan.suites:
        if s.removed:
            continue
        suites.append(
            {
                "id": s.id,
                "name": s.name,
                "measures": s.measures,
                "threshold": s.threshold,
                "contingency": s.contingency,
                "fixed": s.fixed,
                "tiers": {
                    t.name: _tier(s, t, plan)
                    for t in sorted(s.tiers, key=lambda t: TIERS.index(t.name))
                },
            }
        )
    return {
        "cap": plan.cap_usd,
        "globalContingency": plan.global_contingency,
        "defaultTier": DEFAULT_TIER,
        "passes": list(PASSES),
        "bases": list(BASES),
        "levels": [{"name": lv.name, "policy": lv.policy} for lv in plan.levels.values()],
        "suites": suites,
    }


def render_page(plan: Plan) -> str:
    """The single-file page; the data block is JSON, with `<` escaped so it cannot end the tag."""
    data = json.dumps(page_data(plan), indent=1, sort_keys=True).replace("<", "\\u003c")
    return TEMPLATE.read_text(encoding="utf-8").replace("/*DATA*/", data)
