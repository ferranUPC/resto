"""The evaluation cost model: validated data in, low/high totals out.

Cost of a stage = inputs x repetitions x calls_per_input x sum(models x price of its level) with the
tokens of one call, evaluated once with the low tokens and once with the high tokens. A tier is a
list of stages (each in one validation pass); a suite offers several tiers. Contingency is a
per-suite share of each suite's cost, then a global share of the sum of cost and per-suite reserve.
Besides the three tier presets, a suite can be explored freely: a `Config` fixes the inputs per
pass, and the models and repetitions per capability level, inside the bounds the data sets. Presets
are configurations too (`tier_config`), and a configuration costs the same as the tier it equals.
Nothing here calls a model or the network; prices come from `config/prices.toml`.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from resto.adapters.llm.pricing import UnknownModelError, price_of

PASSES = ("V1", "V2")
BASES = ("measured", "proxy")
VARIES = ("repetitions", "seeds")
PENDING = "pending policy approval"
TIERS = ("minimum", "planned", "extended")
MIN_TIER, DEFAULT_TIER = TIERS[0], TIERS[1]
DEFAULT_LEVEL = (
    "reasoning-low"  # the level the default model sits on; the minimum tier uses only it
)
REPETITION_FLOOR = 2
REPETITIONS_MAX = 10  # default upper bound of the repetitions a reader may pick
MODELS_MAX = 3  # default upper bound of the models per capability level a reader may pick


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
    """A minimum tier runs fewer repetitions than the plan's floor."""


class MinimumTierLevelError(BudgetDataError):
    """A minimum tier uses a capability level other than the default one."""


class TierUnknownError(BudgetDataError):
    """A tier name is not one of the known tiers (minimum, planned, extended)."""


class TierMissingError(BudgetDataError):
    """A live suite lacks the minimum or the planned tier."""


class ConfigError(BudgetDataError):
    """A free configuration is outside the bounds the data sets for its suite."""


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
    output_factor: float = (
        1.0  # output tokens relative to the default level, for levels a suite has no run for
    )


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
    reviewer_hours: Range = Range(0.0, 0.0)  # manual review time, never converted to USD


@dataclass(frozen=True)
class Explore:
    """What a reader may change on one suite: inputs per pass, repetitions, models per level."""

    inputs: dict[str, tuple[int, int]]  # pass -> (min, max)
    repetitions_max: int
    models_max: int
    review_minutes: Range  # manual review minutes per answer; ZERO when the suite has no review


@dataclass(frozen=True)
class Profile:
    """Tokens of one agent run of a suite at one level in one pass (a measured or proxy block)."""

    pass_: str
    level: str
    calls_per_input: int
    tokens_in: Range
    tokens_out: Range
    basis: str
    derived_from: str


@dataclass(frozen=True)
class Config:
    """A free choice for one suite: inputs per pass, models and repetitions per level."""

    inputs: dict[str, int]
    models: dict[str, int]
    repetitions: dict[str, int]


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
    explore: Explore | None = None

    def offers(self, name: str) -> bool:
        return any(t.name == name for t in self.tiers)

    def tier(self, name: str) -> Tier:
        """The tier called `name`; raises `TierMissingError` when the suite lacks it."""
        for t in self.tiers:
            if t.name == name:
                return t
        raise TierMissingError(f"suite {self.id!r} has no tier {name!r}")


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
    without_contingency_by_pass: dict[str, Range]
    by_basis: dict[str, Range]  # without contingency, split measured / proxy
    excess_over_cap: Range


def _need(table: dict[str, Any], key: str, where: str) -> Any:
    if key not in table:
        raise BudgetDataError(f"{where}: missing {key!r}")
    return table[key]


def _level(name: str, raw: dict[str, Any]) -> Level:
    where = f"level {name!r}"
    policy = _need(raw, "policy", where)
    approved_for = tuple(raw.get("approved_for", ()))
    factor = float(raw.get("output_factor", 1.0))
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
            factor,
        )
    assumption = _need(raw, "assumption", where)
    return Level(
        name,
        float(_need(raw, "input_per_mtok", where)),
        float(_need(raw, "output_per_mtok", where)),
        f"assumption: {assumption}",
        policy,
        approved_for,
        factor,
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


def _explore(raw: dict[str, Any], tiers: list[Tier], meta: dict[str, Any], sid: str) -> Explore:
    where = f"suite {sid!r} explore"
    table = raw.get("explore", {})
    planned = next((t for t in tiers if t.name == DEFAULT_TIER), None)
    default_inputs = {} if planned is None else tier_config(planned).inputs
    bounds: dict[str, tuple[int, int]] = {}
    raw_inputs = table.get("inputs", {})
    for pass_, default in default_inputs.items():
        low, high = (
            (int(raw_inputs[pass_]["min"]), int(raw_inputs[pass_]["max"]))
            if pass_ in raw_inputs
            else (default, default)
        )
        if not 1 <= low <= default <= high:
            raise BudgetDataError(
                f"{where}: inputs for {pass_} need 1 <= min <= planned ({default}) <= max, "
                f"got {low} and {high}"
            )
        bounds[pass_] = (low, high)
    reps_max = int(table.get("repetitions_max", meta.get("repetitions_max", REPETITIONS_MAX)))
    models_max = int(table.get("models_max", meta.get("models_max", MODELS_MAX)))
    if reps_max < REPETITION_FLOOR or models_max < 1:
        raise BudgetDataError(f"{where}: repetitions_max must be >= {REPETITION_FLOOR}")
    minutes = _range(table, "review_minutes", where) if "review_minutes_low" in table else ZERO
    return Explore(bounds, reps_max, models_max, minutes)


def _suite(raw: dict[str, Any], levels: dict[str, Level], meta: dict[str, Any]) -> Suite:
    sid = _need(raw, "id", "suite")
    varies = _need(raw, "varies", f"suite {sid!r}")
    if varies not in VARIES:
        raise BudgetDataError(f"suite {sid!r}: varies must be one of {VARIES}")
    removed = raw.get("removed", "")
    tiers: list[Tier] = []
    raw_tiers = raw.get("tiers", []) if removed else _need(raw, "tiers", f"suite {sid!r}")
    for raw_tier in raw_tiers:
        tname = _need(raw_tier, "name", f"suite {sid!r}")
        where = f"suite {sid!r} tier {tname!r}"
        if tname not in TIERS:
            raise TierUnknownError(f"{where}: tier must be one of {TIERS}")
        stages = tuple(_stage(s, levels, where) for s in _need(raw_tier, "stages", where))
        if tname == MIN_TIER and any(s.repetitions < REPETITION_FLOOR for s in stages):
            raise MinimumTierBelowFloorError(
                f"{where}: runs fewer than {REPETITION_FLOOR} repetitions"
            )
        if tname == MIN_TIER and any(lv != DEFAULT_LEVEL for st in stages for lv, _ in st.models):
            raise MinimumTierLevelError(f"{where}: must use only the {DEFAULT_LEVEL!r} level")
        tiers.append(Tier(tname, stages))
    explore = None if removed else _explore(raw, tiers, meta, sid)
    if explore is not None:
        tiers = [replace(t, reviewer_hours=review_hours(explore, tier_config(t))) for t in tiers]
    return Suite(
        sid,
        _need(raw, "name", f"suite {sid!r}"),
        _need(raw, "measures", f"suite {sid!r}"),
        _need(raw, "threshold", f"suite {sid!r}"),
        varies,
        float(_need(raw, "contingency", f"suite {sid!r}")),
        tuple(tiers),
        bool(raw.get("fixed", False)),
        removed,
        explore,
    )


def load_plan(path: Path) -> Plan:
    """Read and validate a cost data file. Raises a `BudgetDataError` subclass on bad data."""
    with path.open("rb") as fh:
        raw = tomllib.load(fh)
    meta = _need(raw, "plan", "file")
    levels = {name: _level(name, r) for name, r in _need(raw, "levels", "file").items()}
    suites = tuple(_suite(s, levels, meta) for s in _need(raw, "suites", "file"))
    for suite in suites:
        for required in (MIN_TIER, DEFAULT_TIER):
            if not suite.removed and not suite.offers(required):
                raise TierMissingError(
                    f"suite {suite.id!r}: a live suite needs a {required!r} tier"
                )
    return Plan(
        float(_need(meta, "cap_usd", "plan")),
        float(_need(meta, "global_contingency", "plan")),
        levels,
        suites,
    )


def stage_cost(stage: Stage, levels: dict[str, Level]) -> Range:
    """The one cost formula, used by every output."""
    per_run = sum(
        (
            (
                stage.tokens_in.scaled(levels[level].input_per_mtok)
                + stage.tokens_out.scaled(levels[level].output_per_mtok)
            ).scaled(count / 1_000_000)
            for level, count in stage.models
        ),
        ZERO,
    )
    return per_run.scaled(stage.inputs * stage.repetitions * stage.calls_per_input)


def tier_cost(tier: Tier, levels: dict[str, Level]) -> dict[str, Range]:
    """Cost of a tier per validation pass, before contingency: the one tier-cost function."""
    cost = {p: ZERO for p in PASSES}
    for stage in tier.stages:
        cost[stage.pass_] = cost[stage.pass_] + stage_cost(stage, levels)
    return cost


def tier_net(tier: Tier, levels: dict[str, Level]) -> Range:
    """Cost of a tier over both passes, before contingency."""
    return sum(tier_cost(tier, levels).values(), ZERO)


def tier_cost_by_basis(tier: Tier, levels: dict[str, Level]) -> dict[str, Range]:
    """Cost of a tier split by basis (measured, proxy), before contingency."""
    cost = {b: ZERO for b in BASES}
    for stage in tier.stages:
        cost[stage.basis] = cost[stage.basis] + stage_cost(stage, levels)
    return cost


def pending_levels(suite: Suite, tier: Tier, levels: dict[str, Level]) -> list[str]:
    used = {lv for stage in tier.stages for lv, _ in stage.models}
    return sorted(
        lv
        for lv in used
        if levels[lv].policy == PENDING and suite.id not in levels[lv].approved_for
    )


def tier_config(tier: Tier) -> Config:
    """The free configuration a tier preset stands for."""
    inputs: dict[str, int] = {}
    models: dict[str, int] = {}
    reps: dict[str, int] = {}
    for st in tier.stages:
        inputs[st.pass_] = max(inputs.get(st.pass_, 0), st.inputs)
        for level, count in st.models:
            models[level] = max(models.get(level, 0), count)
            reps[level] = max(reps.get(level, 0), st.repetitions)
    return Config(inputs, models, reps)


def v1_repetitions_cap(suite: Suite) -> int:
    """V1 is the reduced checkpoint: it never runs more repetitions than the planned tier does."""
    planned = suite.tier(DEFAULT_TIER)
    return max((st.repetitions for st in planned.stages if st.pass_ == "V1"), default=0)


def suite_profiles(suite: Suite, levels: dict[str, Level]) -> list[Profile]:
    """Token blocks per (pass, level). A level the suite has no recorded run for takes the
    default level's blocks of the same pass with its output tokens scaled by the level's factor."""
    found: dict[tuple[str, str], list[Profile]] = {}
    for tier in suite.tiers:
        for st in tier.stages:
            for level, _ in st.models:
                block = Profile(
                    st.pass_, level, st.calls_per_input, st.tokens_in, st.tokens_out,
                    st.basis, st.derived_from,
                )  # fmt: skip
                blocks = found.setdefault((st.pass_, level), [])
                same = (block.tokens_in, block.tokens_out, block.basis)
                if all((b.tokens_in, b.tokens_out, b.basis) != same for b in blocks):
                    blocks.append(block)  # one block per distinct token figures, whatever the tier
    out = [b for blocks in found.values() for b in blocks]
    for level in levels:
        if (  # V2 is the pass that runs every level; V1 runs the default level only
            ("V2", level) not in found and ("V2", DEFAULT_LEVEL) in found and level != DEFAULT_LEVEL
        ):
            for base in found[("V2", DEFAULT_LEVEL)]:
                out.append(
                    Profile(
                        "V2", level, base.calls_per_input, base.tokens_in,
                        base.tokens_out.scaled(levels[level].output_factor), "proxy",
                        f"default-level run {base.derived_from!r} with output tokens scaled "
                        f"by {levels[level].output_factor:g}",
                    )
                )  # fmt: skip
    return out


def check_config(suite: Suite, config: Config, plan: Plan) -> None:
    """Raise `ConfigError` when a configuration leaves the bounds the data sets for the suite."""
    ex = suite.explore
    if ex is None:
        raise ConfigError(f"suite {suite.id!r} cannot be configured")
    where = f"suite {suite.id!r} configuration"
    for pass_, (low, high) in ex.inputs.items():
        if not low <= config.inputs.get(pass_, 0) <= high:
            raise ConfigError(f"{where}: inputs for {pass_} must be between {low} and {high}")
    for level, count in config.models.items():
        if level not in plan.levels:
            raise LevelUnknownError(f"{where}: unknown capability level {level!r}")
        if not 0 <= count <= ex.models_max:
            raise ConfigError(f"{where}: models of {level} must be between 0 and {ex.models_max}")
    if config.models.get(DEFAULT_LEVEL, 0) < 1:
        raise ConfigError(f"{where}: needs at least one model at the {DEFAULT_LEVEL!r} level")
    for level, reps in config.repetitions.items():
        if config.models.get(level, 0) and not REPETITION_FLOOR <= reps <= ex.repetitions_max:
            raise ConfigError(
                f"{where}: repetitions of {level} must be between "
                f"{REPETITION_FLOOR} and {ex.repetitions_max}"
            )


def review_hours(explore: Explore, config: Config) -> Range:
    """Manual review time: one answer per model per V2 input, never converted to money."""
    slots = sum(config.models.values())
    return explore.review_minutes.scaled(config.inputs.get("V2", 0) * slots / 60)


def config_cost(
    suite: Suite, config: Config, plan: Plan
) -> tuple[dict[str, Range], dict[str, Range]]:
    """Cost of a free configuration per pass and per basis, before contingency."""
    by_pass = {p: ZERO for p in PASSES}
    by_basis = {b: ZERO for b in BASES}
    cap = v1_repetitions_cap(suite)
    for prof in suite_profiles(suite, plan.levels):
        count = config.models.get(prof.level, 0)
        if prof.pass_ == "V1" and prof.level != DEFAULT_LEVEL:
            continue
        reps = config.repetitions.get(prof.level, 0)
        if prof.pass_ == "V1":
            reps = min(reps, cap)
        price = plan.levels[prof.level]
        per_run = (
            prof.tokens_in.scaled(price.input_per_mtok)
            + prof.tokens_out.scaled(price.output_per_mtok)
        ).scaled(1 / 1_000_000)
        cost = per_run.scaled(
            config.inputs.get(prof.pass_, 0) * reps * prof.calls_per_input * count
        )
        by_pass[prof.pass_] = by_pass[prof.pass_] + cost
        by_basis[prof.basis] = by_basis[prof.basis] + cost
    return by_pass, by_basis


def config_pending(suite: Suite, config: Config, plan: Plan) -> list[str]:
    return sorted(
        lv
        for lv, n in config.models.items()
        if n and plan.levels[lv].policy == PENDING and suite.id not in plan.levels[lv].approved_for
    )


CUSTOM = "custom"


def compute(plan: Plan, selection: Mapping[str, str | Config] | None = None) -> PlanTotals:
    """Totals for one tier or one free configuration per suite (default: `planned`).
    Removed suites are left out."""
    selection = selection or {}
    rows: list[SuiteTotals] = []
    by_pass_net = {p: ZERO for p in PASSES}
    by_pass_reserve = {p: ZERO for p in PASSES}
    by_basis = {b: ZERO for b in BASES}
    for suite in plan.suites:
        if suite.removed:
            continue
        wanted = selection.get(suite.id, DEFAULT_TIER)
        if isinstance(wanted, Config):
            check_config(suite, wanted, plan)
            cost, basis_cost = config_cost(suite, wanted, plan)
            name, pending = CUSTOM, bool(config_pending(suite, wanted, plan))
        else:
            tier = suite.tier(wanted)
            cost, basis_cost = tier_cost(tier, plan.levels), tier_cost_by_basis(tier, plan.levels)
            name, pending = tier.name, bool(pending_levels(suite, tier, plan.levels))
        reserve = {p: cost[p].scaled(suite.contingency) for p in PASSES}
        for p in PASSES:
            by_pass_net[p] = by_pass_net[p] + cost[p]
            by_pass_reserve[p] = by_pass_reserve[p] + reserve[p]
        for basis, part in basis_cost.items():
            by_basis[basis] = by_basis[basis] + part
        rows.append(SuiteTotals(suite.id, name, cost, reserve, pending))
    net = sum(by_pass_net.values(), ZERO)
    reserve_total = sum(by_pass_reserve.values(), ZERO)
    by_pass = {
        p: (by_pass_net[p] + by_pass_reserve[p]).scaled(1 + plan.global_contingency) for p in PASSES
    }
    total = sum(by_pass.values(), ZERO)
    return PlanTotals(
        tuple(rows),
        net,
        reserve_total,
        (net + reserve_total).scaled(plan.global_contingency),
        total,
        by_pass,
        by_pass_net,
        by_basis,
        Range(max(0.0, total.low - plan.cap_usd), max(0.0, total.high - plan.cap_usd)),
    )


def offered_tiers(plan: Plan) -> list[str]:
    """The tiers every live suite offers, in `TIERS` order."""
    live = [s for s in plan.suites if not s.removed]
    return [t for t in TIERS if all(s.offers(t) for s in live)]


def totals_per_tier(plan: Plan) -> list[tuple[str, PlanTotals]]:
    """Totals with every live suite at the same tier, for each tier all of them offer."""
    live = [s for s in plan.suites if not s.removed]
    return [(t, compute(plan, {s.id: t for s in live})) for t in offered_tiers(plan)]
