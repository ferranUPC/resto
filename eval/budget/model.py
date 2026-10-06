"""The evaluation cost model: validated data in, low/high totals out.

Cost of a stage = inputs x repetitions x calls_per_input x sum(models x price of its level) with the
tokens of one call, evaluated once with the low tokens and once with the high tokens. A tier is a
list of stages (each in one validation pass); a suite offers several tiers. Contingency is a
per-suite share of each suite's cost, then a global share of the sum of cost and per-suite reserve.
Nothing here calls a model or the network; prices come from `config/prices.toml`.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from resto.adapters.llm.pricing import UnknownModelError, price_of

PASSES = ("V1", "V2")
BASES = ("measured", "proxy")
VARIES = ("repetitions", "seeds")
PENDING = "pending policy approval"
MIN_TIER = "minimum"
DEFAULT_TIER = "planned"
REPETITION_FLOOR = 2


class BudgetDataError(ValueError):
    """The cost data is wrong; the message names the suite, tier or level at fault."""


class LowAboveHighError(BudgetDataError):
    """A low figure exceeds its high figure."""


class BasisMissingError(BudgetDataError):
    """A stage has no valid basis (measured or proxy) or does not name the run it derives from."""


class LevelUnknownError(BudgetDataError):
    """A stage names a capability level absent from the scale."""


class PriceNotInManifestError(BudgetDataError):
    """A level backed by the manifest names a model that `config/prices.toml` does not price."""


class MinimumTierBelowFloorError(BudgetDataError):
    """A minimum tier runs fewer than the 2 repetitions the plan sets as its floor."""


@dataclass(frozen=True)
class Range:
    low: float
    high: float

    def __add__(self, other: Range) -> Range:
        return Range(self.low + other.low, self.high + other.high)

    def scaled(self, factor: float) -> Range:
        return Range(self.low * factor, self.high * factor)


ZERO = Range(0.0, 0.0)


@dataclass(frozen=True)
class Level:
    name: str
    input_per_mtok: float
    output_per_mtok: float
    backing: str  # "manifest: <slug>" or "assumption: <text>"
    policy: str
    approved_for: tuple[str, ...]


@dataclass(frozen=True)
class Stage:
    pass_: str
    inputs: int
    repetitions: int
    calls_per_input: int
    models: tuple[tuple[str, int], ...]  # (level, how many models at that level)
    tokens_in: Range
    tokens_out: Range
    basis: str
    derived_from: str


@dataclass(frozen=True)
class Tier:
    name: str
    stages: tuple[Stage, ...]


@dataclass(frozen=True)
class Suite:
    id: str
    name: str
    measures: str
    threshold: str
    varies: str
    contingency: float
    tiers: tuple[Tier, ...]
    fixed: bool  # shape settled when its benchmark is designed? False = still open
    removed: str


@dataclass(frozen=True)
class Plan:
    cap_usd: float
    global_contingency: float
    levels: dict[str, Level]
    suites: tuple[Suite, ...]


@dataclass(frozen=True)
class SuiteTotals:
    suite_id: str
    tier: str
    by_pass: dict[str, Range]
    contingency: dict[str, Range]
    pending_policy_approval: bool


@dataclass(frozen=True)
class PlanTotals:
    suites: tuple[SuiteTotals, ...]
    without_contingency: Range
    suite_contingency: Range
    global_contingency: Range
    with_contingency: Range
    by_pass: dict[str, Range]  # with contingency
    excess_over_cap: Range


def _need(table: dict[str, Any], key: str, where: str) -> Any:
    if key not in table:
        raise BudgetDataError(f"{where}: missing {key!r}")
    return table[key]


def _level(name: str, raw: dict[str, Any]) -> Level:
    where = f"level {name!r}"
    policy = _need(raw, "policy", where)
    approved_for = tuple(raw.get("approved_for", ()))
    if "manifest" in raw:
        try:
            price = price_of(raw["manifest"])
        except UnknownModelError as exc:
            raise PriceNotInManifestError(f"{where}: {exc}") from exc
        return Level(
            name,
            price.input_per_mtok,
            price.output_per_mtok,
            f"manifest: {raw['manifest']}",
            policy,
            approved_for,
        )
    assumption = _need(raw, "assumption", where)
    return Level(
        name,
        float(_need(raw, "input_per_mtok", where)),
        float(_need(raw, "output_per_mtok", where)),
        f"assumption: {assumption}",
        policy,
        approved_for,
    )


def _range(raw: dict[str, Any], key: str, where: str) -> Range:
    low, high = float(_need(raw, f"{key}_low", where)), float(_need(raw, f"{key}_high", where))
    if low > high:
        raise LowAboveHighError(f"{where}: {key} low {low} is above high {high}")
    return Range(low, high)


def _stage(raw: dict[str, Any], levels: dict[str, Level], where: str) -> Stage:
    pass_ = _need(raw, "pass", where)
    if pass_ not in PASSES:
        raise BudgetDataError(f"{where}: pass must be one of {PASSES}, got {pass_!r}")
    basis = raw.get("basis")
    if basis not in BASES or not raw.get("derived_from"):
        raise BasisMissingError(
            f"{where}: needs basis in {BASES} and derived_from naming the run "
            "(or what the proxy stands on)"
        )
    models = tuple((m["level"], int(m["count"])) for m in _need(raw, "models", where))
    for level, _ in models:
        if level not in levels:
            raise LevelUnknownError(f"{where}: unknown capability level {level!r}")
    return Stage(
        pass_,
        int(_need(raw, "inputs", where)),
        int(_need(raw, "repetitions", where)),
        int(_need(raw, "calls_per_input", where)),
        models,
        _range(raw, "tokens_in", where),
        _range(raw, "tokens_out", where),
        basis,
        raw["derived_from"],
    )


def _suite(raw: dict[str, Any], levels: dict[str, Level]) -> Suite:
    sid = _need(raw, "id", "suite")
    varies = _need(raw, "varies", f"suite {sid!r}")
    if varies not in VARIES:
        raise BudgetDataError(f"suite {sid!r}: varies must be one of {VARIES}")
    tiers = []
    for raw_tier in _need(raw, "tiers", f"suite {sid!r}"):
        tname = _need(raw_tier, "name", f"suite {sid!r}")
        where = f"suite {sid!r} tier {tname!r}"
        stages = tuple(_stage(s, levels, where) for s in _need(raw_tier, "stages", where))
        if tname == MIN_TIER and any(s.repetitions < REPETITION_FLOOR for s in stages):
            raise MinimumTierBelowFloorError(
                f"{where}: runs fewer than {REPETITION_FLOOR} repetitions"
            )
        tiers.append(Tier(tname, stages))
    return Suite(
        sid,
        _need(raw, "name", f"suite {sid!r}"),
        _need(raw, "measures", f"suite {sid!r}"),
        _need(raw, "threshold", f"suite {sid!r}"),
        varies,
        float(_need(raw, "contingency", f"suite {sid!r}")),
        tuple(tiers),
        bool(raw.get("fixed", False)),
        raw.get("removed", ""),
    )


def load_plan(path: Path) -> Plan:
    """Read and validate a cost data file. Raises a `BudgetDataError` subclass on bad data."""
    with path.open("rb") as fh:
        raw = tomllib.load(fh)
    meta = _need(raw, "plan", "file")
    levels = {name: _level(name, r) for name, r in _need(raw, "levels", "file").items()}
    return Plan(
        float(_need(meta, "cap_usd", "plan")),
        float(_need(meta, "global_contingency", "plan")),
        levels,
        tuple(_suite(s, levels) for s in _need(raw, "suites", "file")),
    )


def stage_cost(stage: Stage, levels: dict[str, Level]) -> Range:
    """The one cost formula, used by every output."""
    per_run = ZERO
    for level, count in stage.models:
        price = levels[level]
        low = (
            stage.tokens_in.low * price.input_per_mtok
            + stage.tokens_out.low * price.output_per_mtok
        )
        high = (
            stage.tokens_in.high * price.input_per_mtok
            + stage.tokens_out.high * price.output_per_mtok
        )
        per_run = per_run + Range(low, high).scaled(count / 1_000_000)
    return per_run.scaled(stage.inputs * stage.repetitions * stage.calls_per_input)


def pending_levels(suite: Suite, tier: Tier, levels: dict[str, Level]) -> list[str]:
    used = {lv for stage in tier.stages for lv, _ in stage.models}
    return sorted(
        lv
        for lv in used
        if levels[lv].policy == PENDING and suite.id not in levels[lv].approved_for
    )


def compute(plan: Plan, selection: dict[str, str] | None = None) -> PlanTotals:
    """Totals for one tier per suite (default: `planned`). Removed suites are left out."""
    selection = selection or {}
    rows: list[SuiteTotals] = []
    by_pass_net = {p: ZERO for p in PASSES}
    by_pass_reserve = {p: ZERO for p in PASSES}
    for suite in plan.suites:
        if suite.removed:
            continue
        wanted = selection.get(suite.id, DEFAULT_TIER)
        tier = next((t for t in suite.tiers if t.name == wanted), None)
        if tier is None:
            raise BudgetDataError(f"suite {suite.id!r} has no tier {wanted!r}")
        cost = {p: ZERO for p in PASSES}
        for stage in tier.stages:
            cost[stage.pass_] = cost[stage.pass_] + stage_cost(stage, plan.levels)
        reserve = {p: cost[p].scaled(suite.contingency) for p in PASSES}
        for p in PASSES:
            by_pass_net[p] = by_pass_net[p] + cost[p]
            by_pass_reserve[p] = by_pass_reserve[p] + reserve[p]
        rows.append(
            SuiteTotals(
                suite.id, tier.name, cost, reserve, bool(pending_levels(suite, tier, plan.levels))
            )
        )
    net = _sum(by_pass_net.values())
    reserve_total = _sum(by_pass_reserve.values())
    by_pass = {
        p: (by_pass_net[p] + by_pass_reserve[p]).scaled(1 + plan.global_contingency) for p in PASSES
    }
    total = _sum(by_pass.values())
    return PlanTotals(
        tuple(rows),
        net,
        reserve_total,
        (net + reserve_total).scaled(plan.global_contingency),
        total,
        by_pass,
        Range(max(0.0, total.low - plan.cap_usd), max(0.0, total.high - plan.cap_usd)),
    )


def _sum(ranges: Any) -> Range:
    total = ZERO
    for r in ranges:
        total = total + r
    return total
