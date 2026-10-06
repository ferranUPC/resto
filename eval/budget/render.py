"""Renders the full internal plan (Markdown) from the same computed model every output uses."""

from __future__ import annotations

from eval.budget.model import (
    DEFAULT_TIER,
    PASSES,
    PENDING,
    Plan,
    PlanTotals,
    Range,
    Stage,
    Suite,
    compute,
    pending_levels,
    stage_cost,
)

TIER_ORDER = ("minimum", "planned", "extended")


def _usd(r: Range) -> str:
    return f"${r.low:.2f} to ${r.high:.2f}"


def _cap(plan: Plan) -> str:
    return f"${plan.cap_usd:g}"


def _stage_row(stage: Stage, plan: Plan) -> str:
    models = ", ".join(f"{count} x {level}" for level, count in stage.models)
    tokens = (
        f"{stage.tokens_in.low:,.0f}-{stage.tokens_in.high:,.0f} in, "
        f"{stage.tokens_out.low:,.0f}-{stage.tokens_out.high:,.0f} out"
    )
    return (
        f"| {stage.pass_} | {stage.inputs} x {stage.repetitions} | {models} | {tokens} | "
        f"{stage.basis}: {stage.derived_from} | {_usd(stage_cost(stage, plan.levels))} |"
    )


def _levels(plan: Plan) -> list[str]:
    out = [
        "## Capability levels",
        "",
        "Levels carry no model names in the short version or the page; this plan names the",
        "backing.",
        "Prices are USD per million tokens.",
        "",
        "| Level | In | Out | Backing | Policy |",
        "|---|---|---|---|---|",
    ]
    for level in plan.levels.values():
        policy = level.policy
        if level.approved_for:
            policy += f" (approved for: {', '.join(level.approved_for)})"
        out.append(
            f"| {level.name} | {level.input_per_mtok:g} | {level.output_per_mtok:g} | "
            f"{level.backing} | {policy} |"
        )
    return out + [""]


def _suite(suite: Suite, plan: Plan) -> list[str]:
    out = [f"### {suite.name} (`{suite.id}`)", ""]
    if suite.removed:
        return out + [f"Excluded from every total: {suite.removed}.", ""]
    out += [
        f"- Measures: {suite.measures}",
        f"- Threshold read: {suite.threshold}",
        f"- Varies: {suite.varies}",
        f"- Per-suite contingency reserve: {suite.contingency:.0%}",
        "- Shape: " + ("fixed" if suite.fixed else "unfixed until its benchmark is designed"),
        "",
    ]
    for tier in sorted(suite.tiers, key=lambda t: TIER_ORDER.index(t.name)):
        total = Range(0.0, 0.0)
        for stage in tier.stages:
            total = total + stage_cost(stage, plan.levels)
        flag = pending_levels(suite, tier, plan.levels)
        note = f" ({PENDING}: {', '.join(flag)})" if flag else ""
        out += [
            f"#### {tier.name}{note}: {_usd(total)} before contingency",
            "",
            "| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |",
            "|---|---|---|---|---|---|",
            *(_stage_row(s, plan) for s in tier.stages),
            "",
        ]
    return out


def _totals(plan: Plan, totals: PlanTotals) -> list[str]:
    out = [
        "## Totals",
        "",
        f"Tier per suite: `{DEFAULT_TIER}` (the default selection). Reference cap for V1 and V2 "
        f"together: {_cap(plan)}.",
        "",
        "| | Low to high |",
        "|---|---|",
        f"| Total without contingency | {_usd(totals.without_contingency)} |",
        f"| Per-suite reserve | {_usd(totals.suite_contingency)} "
        f"(global {plan.global_contingency:.0%} on top: {_usd(totals.global_contingency)}) |",
        f"| Total with contingency | {_usd(totals.with_contingency)} |",
    ]
    out += [f"| {p} with contingency | {_usd(totals.by_pass[p])} |" for p in PASSES]
    out.append("")
    if totals.excess_over_cap.high > 0:
        out.append(
            f"The plan exceeds the {_cap(plan)} reference by {_usd(totals.excess_over_cap)}. "
            "That excess is what the funding request can ask for."
        )
    else:
        out.append(f"The plan stays within the {_cap(plan)} reference.")
    out.append("")
    out += ["| Suite | Tier | Pending policy approval |", "|---|---|---|"]
    out += [
        f"| {r.suite_id} | {r.tier} | {'yes' if r.pending_policy_approval else 'no'} |"
        for r in totals.suites
    ]
    return out + [""]


def render_full_plan(plan: Plan) -> str:
    """The full internal plan: levels, every suite with its tiers, totals against the cap."""
    totals = compute(plan)
    lines = [
        "# Evaluation cost plan (full, internal)",
        "",
        "Generated from `eval/budget/cost-data.toml` by `python -m eval.budget`; do not edit.",
        "Every figure is a low-to-high range in USD. `measured` rests on a recorded run;",
        "`proxy` is an estimate and names what it derives from. A run is one agent run;",
        "tokens are per run.",
        "",
        *_levels(plan),
        "## Suites",
        "",
    ]
    for suite in plan.suites:
        lines += _suite(suite, plan)
    return "\n".join([*lines, *_totals(plan, totals)]).rstrip() + "\n"
