"""Renders the full internal plan (Markdown) from the same computed model every output uses."""

from __future__ import annotations

from eval.budget.common import (
    GENERATED,
    excess_cell,
    excess_sentence,
)
from eval.budget.common import (
    cap as _cap,
)
from eval.budget.common import (
    share as _share,
)
from eval.budget.common import (
    usd as _usd,
)
from eval.budget.model import (
    BASES,
    DEFAULT_TIER,
    PASSES,
    PENDING,
    TIERS,
    ZERO,
    Plan,
    PlanTotals,
    Stage,
    Suite,
    compute,
    pending_levels,
    stage_cost,
    tier_cost_by_basis,
    tier_net,
    totals_per_tier,
)


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
    for tier in sorted(suite.tiers, key=lambda t: TIERS.index(t.name)):
        total = tier_net(tier, plan.levels)
        parts = tier_cost_by_basis(tier, plan.levels)
        flag = pending_levels(suite, tier, plan.levels)
        note = f" ({PENDING}: {', '.join(flag)})" if flag else ""
        hours = tier.reviewer_hours
        out += [
            f"#### {tier.name}{note}: {_usd(total)} before contingency",
            "",
            *(
                [
                    f"Reviewer effort (separate from model cost, not in USD): "
                    f"{hours.low:g} to {hours.high:g} hours.",
                    "",
                ]
                if hours.high
                else []
            ),
            "Measured "
            + _usd(parts["measured"])
            + ", proxy "
            + _usd(parts["proxy"])
            + " (before contingency).",
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
        f"Tier per suite: `{DEFAULT_TIER}` (the default selection). The {_cap(plan)} reference",
        "is a combined figure for V1 and V2 together; the plan defines no per-pass cap, so the",
        "excess is stated for the combined total only.",
        "",
        "| | Low to high |",
        "|---|---|",
        f"| Total without contingency | {_usd(totals.without_contingency)} |",
        f"| Per-suite reserve | {_usd(totals.suite_contingency)} |",
        f"| Global reserve ({plan.global_contingency:.0%} of cost plus per-suite reserve) | "
        f"{_usd(totals.global_contingency)} |",
        f"| Total with contingency | {_usd(totals.with_contingency)} |",
    ]
    for p in PASSES:
        out.append(f"| {p} without contingency | {_usd(totals.without_contingency_by_pass[p])} |")
        out.append(f"| {p} with contingency | {_usd(totals.by_pass[p])} |")
    out.append("")
    out.append("Share of the total without contingency that rests on a run or on an estimate:")
    out.append("")
    out += ["| Basis | Low to high | Share |", "|---|---|---|"]
    for b in BASES:
        share = _share(totals.by_basis[b], totals.without_contingency)
        out.append(f"| {b} | {_usd(totals.by_basis[b])} | {share} |")
    out.append("")
    out.append(excess_sentence(plan, totals, "The plan"))
    out.append("")
    out += [
        "| Suite | Tier | Without contingency | Per-suite reserve | Measured share | "
        "Pending policy approval |",
        "|---|---|---|---|---|---|",
    ]
    by_id = {s.id: s for s in plan.suites}
    for r in totals.suites:
        tier = by_id[r.suite_id].tier(r.tier)
        net = sum(r.by_pass.values(), ZERO)
        reserve = sum(r.contingency.values(), ZERO)
        measured = tier_cost_by_basis(tier, plan.levels)["measured"]
        out.append(
            f"| {r.suite_id} | {r.tier} | {_usd(net)} | {_usd(reserve)} | "
            f"{_share(measured, net)} | {'yes' if r.pending_policy_approval else 'no'} |"
        )
    return out + [""]


def _per_tier(plan: Plan) -> list[str]:
    out = [
        "## Totals per tier",
        "",
        f"Every live suite at the same tier, against the {_cap(plan)} reference (V1 and V2",
        "combined, with contingency). Per-pass figures are with contingency.",
        "",
        "| Tier | Without contingency | V1 | V2 | With contingency | Excess over cap |",
        "|---|---|---|---|---|---|",
    ]
    for tier, t in totals_per_tier(plan):
        out.append(
            f"| {tier} | {_usd(t.without_contingency)} | {_usd(t.by_pass['V1'])} | "
            f"{_usd(t.by_pass['V2'])} | {_usd(t.with_contingency)} | {excess_cell(t)} |"
        )
    return out + [""]


def _unfixed(plan: Plan) -> list[str]:
    open_ = [s for s in plan.suites if not s.removed and not s.fixed]
    out = [
        "## Suites whose shape is unfixed",
        "",
        "Early ranges for these are not a commitment; each is fixed once its benchmark exists.",
        "",
    ]
    return out + [f"- {s.name} (`{s.id}`)" for s in open_] + [""]


def render_full_plan(plan: Plan) -> str:
    """The full internal plan: levels, every suite with its tiers, totals against the cap."""
    totals = compute(plan)
    lines = [
        "# Evaluation cost plan (full, internal)",
        "",
        GENERATED,
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
    body = [*lines, *_totals(plan, totals), *_per_tier(plan), *_unfixed(plan)]
    return "\n".join(body).rstrip() + "\n"
