"""The short English version for the supervisors, rendered from the same computed model.

No figure is written here: every number comes from `compute`, `tier_net`, `tier_cost_by_basis`
and `totals_per_tier`. Capability levels appear by name only, never a model name.
"""

from __future__ import annotations

from eval.budget.common import (
    GENERATED,
    cap,
    excess_cell,
    excess_sentence,
    share,
    usd,
)
from eval.budget.model import (
    BASES,
    DEFAULT_TIER,
    MIN_TIER,
    PASSES,
    PENDING,
    Plan,
    PlanTotals,
    Suite,
    Tier,
    compute,
    pending_levels,
    tier_cost_by_basis,
    tier_net,
    totals_per_tier,
)


def _runs(tier: Tier) -> int:
    return sum(s.inputs * s.repetitions for s in tier.stages)


def _passes(tier: Tier) -> str:
    return "+".join(p for p in PASSES if any(s.pass_ == p for s in tier.stages))


def _basis(tier: Tier, plan: Plan) -> str:
    """Each basis with its share of the tier's cost (by the high figure), e.g. `measured 62%`."""
    parts = tier_cost_by_basis(tier, plan.levels)
    total = tier_net(tier, plan.levels).high
    used = [f"{b} {parts[b].high / total:.0%}" for b in BASES if parts[b].high > 0]
    return " + ".join(used) if used else "none"


def _levels(suite: Suite, tier: Tier, plan: Plan) -> str:
    """Levels tested with the most models any stage runs at each; pending ones are marked."""
    most: dict[str, int] = {}
    for stage in tier.stages:
        for level, count in stage.models:
            most[level] = max(most.get(level, 0), count)
    pending = pending_levels(suite, tier, plan.levels)
    return ", ".join(
        f"{lv} x{n}" + (f" ({PENDING})" if lv in pending else "") for lv, n in sorted(most.items())
    )


def _hours(tier: Tier) -> str:
    hours = tier.reviewer_hours
    return f"{hours.low:g} to {hours.high:g} h" if hours.high else "none"


def _shape_row(suite: Suite) -> str:
    shape = "fixed" if suite.fixed else "unfixed"
    return f"| {suite.name} | {suite.measures} | {suite.threshold} | {shape} |"


def _design_row(suite: Suite, plan: Plan) -> str:
    planned = suite.tier(DEFAULT_TIER)
    minimum = suite.tier(MIN_TIER)
    return (
        f"| {suite.name} | {_passes(planned)} | {_levels(suite, planned, plan)} | "
        f"{suite.varies} | {_runs(minimum)} / {_runs(planned)} | {_basis(planned, plan)} | "
        f"{_hours(minimum)} / {_hours(planned)} | "
        f"{usd(tier_net(minimum, plan.levels))} / {usd(tier_net(planned, plan.levels))} |"
    )


def _totals_row(tier: str, t: PlanTotals) -> str:
    flag = f" ({PENDING})" if any(r.pending_policy_approval for r in t.suites) else ""
    reserve = t.suite_contingency + t.global_contingency
    return (
        f"| {tier}{flag} | {usd(t.without_contingency)} | {usd(reserve)} | "
        f"{usd(t.with_contingency)} | {usd(t.by_pass['V1'])} | {usd(t.by_pass['V2'])} | "
        f"{excess_cell(t)} |"
    )


def _evidence(totals: PlanTotals) -> str:
    parts = [
        f"{b} {usd(totals.by_basis[b])} ({share(totals.by_basis[b], totals.without_contingency)})"
        for b in BASES
    ]
    return "Planned tier before contingency, by evidence: " + "; ".join(parts) + "."


def render_short_version(plan: Plan) -> str:
    """A one-page evaluation budget: suites, their design and cost, totals per tier."""
    live = [s for s in plan.suites if not s.removed]
    totals = compute(plan)
    lines = [
        "# Evaluation budget (short version)",
        "",
        GENERATED,
        "All figures are low-to-high ranges in USD. Runs are agent runs. `measured` rests on a",
        "recorded run, `proxy` on an estimate. Model capability is given as a level, not a model;",
        f"a level marked `{PENDING}` may not be used until the cost policy approves it.",
        "",
        "## Suites",
        "",
        "| Suite | Measures | Threshold read | Shape |",
        "|---|---|---|---|",
        *(_shape_row(s) for s in live),
        "",
        "## Design and cost per suite",
        "",
        "Levels are those of the planned tier, with the models run at each (`x2` = two models).",
        "Basis shows the share of cost resting on a run or an estimate. Reviewer hours are manual",
        "time, never converted to USD. Runs, hours and cost (before contingency) are shown as",
        "minimum / planned. The suite varies repetitions or seeds as stated. The interactive page",
        "lets a reader set the inputs, the levels, the models per level and the repetitions of each",
        "suite within bounds fixed in the cost data, starting from any of these three sizes.",
        "",
        "| Suite | Pass | Levels tested | Varies | Runs | Basis | Reviewer hours | Cost |",
        "|---|---|---|---|---|---|---|---|",
        *(_design_row(s, plan) for s in live),
        "",
        "## Totals",
        "",
        f"Against the {cap(plan)} reference (V1 and V2 combined). Reserve is the per-suite plus",
        "the global contingency; V1 and V2 are with contingency.",
        "",
        "| Tier | Without contingency | Reserve | With contingency | V1 | V2 | Excess |",
        "|---|---|---|---|---|---|---|",
        *(_totals_row(tier, t) for tier, t in totals_per_tier(plan)),
        "",
        _evidence(totals),
        "",
        excess_sentence(plan, totals, "The planned tier"),
        "",
    ]
    unfixed = [s.name for s in live if not s.fixed]
    if unfixed:
        lines += [
            "## Suites unfixed until their benchmark is designed",
            "",
            "Early ranges, not a commitment: " + ", ".join(unfixed) + ".",
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"
