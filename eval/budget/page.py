"""Renders the interactive budget page: one HTML file with the computed figures embedded.

Python embeds the price of each capability level and, per suite, the token blocks, the bounds and
the three tier presets. The page script applies the cost formula to the reader's choice (inputs per
pass, models and repetitions per level), then the per-suite and global contingency (editable), and
works out the excess over the cap; a parity test checks its totals against `compute` for tiers and
for free configurations. The selection lives in the address fragment.
"""

from __future__ import annotations

import json
from pathlib import Path

from eval.budget.model import (
    BASES,
    DEFAULT_LEVEL,
    DEFAULT_TIER,
    PASSES,
    PENDING,
    REPETITION_FLOOR,
    TIERS,
    BudgetDataError,
    Plan,
    Range,
    Suite,
    Tier,
    pending_levels,
    suite_profiles,
    tier_config,
    tier_cost,
    tier_cost_by_basis,
    v1_repetitions_cap,
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


def _explore(suite: Suite, plan: Plan) -> dict[str, object]:
    ex = suite.explore
    if ex is None:
        raise BudgetDataError(f"suite {suite.id!r} has no explore bounds")
    profiles = suite_profiles(suite, plan.levels)
    levels = {}
    for name, level in plan.levels.items():
        blocks: dict[str, list[dict[str, object]]] = {}
        for prof in profiles:
            if prof.level == name:
                blocks.setdefault(prof.pass_, []).append(
                    {
                        "in": _pair(prof.tokens_in),
                        "out": _pair(prof.tokens_out),
                        "calls": prof.calls_per_input,
                        "basis": prof.basis,
                    }
                )
        levels[name] = {
            "blocks": blocks,
            "pending": level.policy == PENDING and suite.id not in level.approved_for,
        }
    defaults = tier_config(suite.tier(DEFAULT_TIER))
    return {
        "inputs": {
            p: {"min": lo, "max": hi, "default": defaults.inputs[p]}
            for p, (lo, hi) in ex.inputs.items()
        },
        "repsMax": ex.repetitions_max,
        "modelsMax": ex.models_max,
        "v1RepsCap": v1_repetitions_cap(suite),
        "minutes": _pair(ex.review_minutes),
        "levels": levels,
        "presets": {
            t.name: {
                "inputs": tier_config(t).inputs,
                "models": tier_config(t).models,
                "reps": tier_config(t).repetitions,
            }
            for t in suite.tiers
        },
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
                "varies": s.varies,
                "explore": _explore(s, plan),
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
        "defaultLevel": DEFAULT_LEVEL,
        "repetitionFloor": REPETITION_FLOOR,
        "levels": [
            {
                "name": lv.name,
                "policy": lv.policy,
                "in": lv.input_per_mtok,
                "out": lv.output_per_mtok,
            }
            for lv in plan.levels.values()
        ],
        "suites": suites,
    }


def render_page(plan: Plan) -> str:
    """The single-file page; the data block is JSON, with `<` escaped so it cannot end the tag."""
    data = json.dumps(page_data(plan), indent=1, sort_keys=True).replace("<", "\\u003c")
    return TEMPLATE.read_text(encoding="utf-8").replace("/*DATA*/", data)
