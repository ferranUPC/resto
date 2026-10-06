"""The evaluation cost model (E3.9/01): data in, totals out. No paid or network call."""

from __future__ import annotations

from pathlib import Path

import pytest
from eval.budget import (
    BasisMissingError,
    LevelUnknownError,
    LowAboveHighError,
    MinimumTierBelowFloorError,
    MinimumTierLevelError,
    PriceNotInManifestError,
    TierUnknownError,
    compute,
    load_plan,
)

from tests.unit.eval.budget_fixtures import HEADER, suite, write

DATA = Path(__file__).resolve().parents[3] / "eval" / "budget" / "cost-data.toml"


def test_a_stage_costs_inputs_times_repetitions_times_tokens_times_price(tmp_path):
    totals = compute(load_plan(write(tmp_path)), {"s1": "minimum"})
    row = totals.suites[0]
    assert row.by_pass["V2"].low == pytest.approx(4.20)
    assert row.by_pass["V2"].high == pytest.approx(8.40)
    assert row.by_pass["V1"].low == 0.0


def test_contingency_is_per_suite_then_global_on_top(tmp_path):
    totals = compute(load_plan(write(tmp_path)), {"s1": "minimum"})
    # 4.20 + 20% = 5.04; global 10% of that = 0.504
    assert totals.without_contingency.low == pytest.approx(4.20)
    assert totals.suites[0].contingency["V2"].low == pytest.approx(0.84)
    assert totals.global_contingency.low == pytest.approx(0.504)
    assert totals.with_contingency.low == pytest.approx(5.544)
    assert totals.by_pass["V2"].low == pytest.approx(5.544)


def test_changing_the_contingency_in_the_data_changes_the_totals(tmp_path):
    low = compute(load_plan(write(tmp_path, suite(contingency=0.0))), {"s1": "minimum"})
    high = compute(load_plan(write(tmp_path, suite(contingency=0.5))), {"s1": "minimum"})
    assert high.with_contingency.low > low.with_contingency.low


def test_changing_the_global_contingency_changes_the_totals(tmp_path):
    base = compute(load_plan(write(tmp_path)), {"s1": "minimum"})
    header = HEADER.replace("global_contingency = 0.10", "global_contingency = 0.50")
    more = compute(load_plan(write(tmp_path, header=header)), {"s1": "minimum"})
    assert more.with_contingency.low == pytest.approx(4.20 * 1.20 * 1.50)
    assert more.with_contingency.low > base.with_contingency.low


def test_totals_split_by_pass_without_contingency_and_by_basis(tmp_path):
    totals = compute(load_plan(write(tmp_path, suite(basis="proxy"))), {"s1": "minimum"})
    assert totals.without_contingency_by_pass["V2"].low == pytest.approx(4.20)
    assert totals.without_contingency_by_pass["V1"].low == 0.0
    assert totals.by_basis["proxy"].low == pytest.approx(4.20)
    assert totals.by_basis["measured"].low == 0.0


def test_the_cap_excess_is_stated_never_an_error(tmp_path):
    totals = compute(load_plan(write(tmp_path)), {"s1": "planned"})
    assert totals.excess_over_cap.high == 0.0
    big = HEADER.replace("cap_usd = 30.0", "cap_usd = 1.0")
    totals = compute(load_plan(write(tmp_path, header=big)), {"s1": "planned"})
    assert totals.excess_over_cap.low == pytest.approx(totals.with_contingency.low - 1.0)


def test_a_suite_marked_removed_is_left_out_of_the_totals(tmp_path):
    plan = load_plan(write(tmp_path, suite(), suite(suite_id="gone", removed="removed by r13")))
    totals = compute(plan, {"s1": "minimum"})
    assert [row.suite_id for row in totals.suites] == ["s1"]
    assert totals.without_contingency.low == pytest.approx(4.20)


def test_a_level_that_needs_approval_is_marked_pending_policy_approval(tmp_path):
    plan = load_plan(write(tmp_path, suite(level="reasoning-high")))
    assert compute(plan, {"s1": "planned"}).suites[0].pending_policy_approval is True
    plan = load_plan(write(tmp_path))
    assert compute(plan, {"s1": "planned"}).suites[0].pending_policy_approval is False


def test_low_above_high_is_refused(tmp_path):
    path = write(tmp_path)
    path.write_text(path.read_text().replace("tokens_in_low = 1000000", "tokens_in_low = 3000000"))
    with pytest.raises(LowAboveHighError):
        load_plan(path)


def test_a_missing_basis_is_refused(tmp_path):
    with pytest.raises(BasisMissingError):
        load_plan(write(tmp_path, suite(basis="guess")))


def test_a_missing_derived_from_is_refused(tmp_path):
    with pytest.raises(BasisMissingError):
        load_plan(write(tmp_path, suite(derived="")))


def test_an_unknown_level_is_refused(tmp_path):
    with pytest.raises(LevelUnknownError):
        load_plan(write(tmp_path, suite(level="reasoning-extreme")))


def test_a_manifest_backed_level_missing_from_the_manifest_is_refused(tmp_path):
    header = HEADER.replace("deepseek/deepseek-v4.1-flash", "nobody/not-priced")
    with pytest.raises(PriceNotInManifestError):
        load_plan(write(tmp_path, header=header))


def test_a_minimum_tier_below_two_repetitions_is_refused(tmp_path):
    with pytest.raises(MinimumTierBelowFloorError):
        load_plan(write(tmp_path, suite(min_reps=1)))


def test_a_minimum_tier_with_a_level_other_than_the_default_is_refused(tmp_path):
    with pytest.raises(MinimumTierLevelError):
        load_plan(write(tmp_path, suite(min_level="reasoning-high")))


def test_an_unknown_tier_name_is_refused(tmp_path):
    with pytest.raises(TierUnknownError):
        load_plan(write(tmp_path, suite(tiers=("minimum", "bogus"))))


def test_the_shipped_data_names_no_model_in_derived_from():
    plan = load_plan(DATA)
    names = ("deepseek", "mistral", "ministral", "gemma", "llama", "qwen", "gpt", "claude")
    for suite_ in plan.suites:
        for tier in suite_.tiers:
            for stage in tier.stages:
                assert not any(n in stage.derived_from.lower() for n in names)


def test_the_shipped_data_loads_with_both_suites():
    plan = load_plan(DATA)
    assert [s.id for s in plan.suites] == ["input-parser", "exp-01"]
    totals = compute(plan)
    assert 0 < totals.with_contingency.low <= totals.with_contingency.high
