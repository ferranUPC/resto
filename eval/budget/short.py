"""The short English version for the supervisors, rendered from the same computed model.

No figure is written here: every number comes from `compute`, `tier_cost` and
`tier_cost_by_basis`. Capability levels appear by name only, never a model name.
"""

from __future__ import annotations

from eval.budget.model import (
    DEFAULT_TIER,
    MIN_TIER,
    PASSES,
    TIERS,
    Plan,
    Range,
    Suite,
    Tier,
    compute,
    tier_cost,
    tier_cost_by_basis,
)


def _usd(r: Range) -> str:
    return f"${r.low:.2f} to ${r.high:.2f}"


def _tier(suite: Suite, name: str) -> Tier | None:
    return next((t for t in suite.tiers if t.name == name), None)


def _runs(tier: Tier) -> int:
    return sum(s.inputs * s.repetitions for s in tier.stages)


def _passes(tier: Tier) -> str:
    return "+".join(p for p in PASSES if any(s.pass_ == p for s in tier.stages))


def _basis(tier: Tier, plan: Plan) -> str:
    parts = tier_cost_by_basis(tier, plan.levels)
    used = [b for b, r in parts.items() if r.high > 0]
    return " + ".join(used) if used else "none"


def _net(tier: Tier, plan: Plan) -> Range:
    return sum(tier_cost(tier, plan.levels).values(), Range(0.0, 0.0))


def _row(suite: Suite, plan: Plan) -> str:
    full = _tier(suite, DEFAULT_TIER)
    low = _tier(suite, MIN_TIER)
    assert full is not None and low is not None
    shape = "fixed" if suite.fixed else "unfixed"
    return (
        f"| {suite.name} | {suite.measures} | {suite.threshold} | {_passes(full)} | "
        f"{_runs(full)} / {_runs(low)} | {_basis(full, plan)} | "
        f"{_usd(_net(low, plan))} / {_usd(_net(full, plan))} | {shape} |"
    )


def render_short_version(plan: Plan) -> str:
    """A one-page evaluation budget: one row per suite, totals per tier against the cap."""
    live = [s for s in plan.suites if not s.removed]
    totals = compute(plan)
    cap = f"${plan.cap_usd:g}"
    lines = [
        "# Evaluation budget (short version)",
        "",
        "Generated from `eval/budget/cost-data.toml` by `python -m eval.budget`; do not edit.",
        "All figures are low-to-high ranges in USD. Runs are agent runs. `measured` rests on a",
        "recorded run, `proxy` on an estimate. Model capability is given as a level, not a model.",
        "",
        "## Suites",
        "",
        "Runs and cost are shown as minimum / planned (cost before contingency).",
        "",
        "| Suite | Measures | Threshold read | Pass | Runs | Basis | Cost | Shape |",
        "|---|---|---|---|---|---|---|---|",
        *(_row(s, plan) for s in live),
        "",
        "## Totals",
        "",
        f"Against the {cap} reference (V1 and V2 combined). With contingency.",
        "",
        "| Tier | V1 | V2 | Combined | Excess over reference |",
        "|---|---|---|---|---|",
    ]
    for tier in TIERS:
        if not all(_tier(s, tier) for s in live):
            continue
        t = totals if tier == DEFAULT_TIER else compute(plan, {s.id: tier for s in live})
        excess = _usd(t.excess_over_cap) if t.excess_over_cap.high > 0 else "none"
        lines.append(
            f"| {tier} | {_usd(t.by_pass['V1'])} | {_usd(t.by_pass['V2'])} | "
            f"{_usd(t.with_contingency)} | {excess} |"
        )
    lines.append("")
    if totals.excess_over_cap.high > 0:
        lines.append(
            f"The planned tier exceeds the {cap} reference by {_usd(totals.excess_over_cap)}. "
            "That excess is what the funding request can ask for."
        )
    else:
        lines.append(f"The planned tier stays within the {cap} reference.")
    lines.append("")
    unfixed = [s.name for s in live if not s.fixed]
    if unfixed:
        lines += [
            "## Suites unfixed until their benchmark is designed",
            "",
            "Early ranges, not a commitment: " + ", ".join(unfixed) + ".",
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"
