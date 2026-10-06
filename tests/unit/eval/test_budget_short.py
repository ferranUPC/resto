"""The short English version for the supervisors (E3.9/03), rendered from the same model."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from eval.budget import compute, load_plan, render_short_version
from eval.budget.model import MIN_TIER, Range, TierMissingError

from tests.unit.eval.budget_fixtures import EXPLORE, HEADER, suite, write

ROOT = Path(__file__).resolve().parents[3] / "eval" / "budget"
SIZE_BOUND_WORDS = 1500


def _usd(r: Range) -> str:
    return f"${r.low:.2f} to ${r.high:.2f}"


def test_every_total_is_the_models_total(tmp_path):
    plan = load_plan(write(tmp_path))
    totals = compute(plan)
    text = render_short_version(plan)
    assert _usd(totals.with_contingency) in text
    for p in ("V1", "V2"):
        assert _usd(totals.by_pass[p]) in text


def test_the_minimum_tier_total_is_the_models_total(tmp_path):
    plan = load_plan(write(tmp_path))
    minimum = compute(plan, {s.id: MIN_TIER for s in plan.suites})
    assert _usd(minimum.with_contingency) in render_short_version(plan)


def test_one_row_per_live_suite_with_basis_and_pass(tmp_path):
    plan = load_plan(
        write(
            tmp_path,
            suite(),
            suite(suite_id="s2", basis="proxy"),
            suite(suite_id="gone", removed="removed by r13"),
        )
    )
    text = render_short_version(plan)
    rows = [ln for ln in text.splitlines() if ln.startswith("| Suite s") and "| V" in ln]
    assert len(rows) == 2
    assert any("proxy" in r for r in rows) and any("measured" in r for r in rows)
    assert all("V2" in r for r in rows)
    assert "removed by r13" not in text


def test_the_excess_over_the_cap_is_stated(tmp_path):
    big = HEADER.replace("cap_usd = 30.0", "cap_usd = 1.0")
    assert "exceeds" in render_short_version(load_plan(write(tmp_path, header=big)))


def test_the_shipped_short_version_has_no_model_names_is_short_and_current():
    plan = load_plan(ROOT / "cost-data.toml")
    text = render_short_version(plan).lower()
    for level in plan.levels.values():
        if level.backing.startswith("manifest: "):
            slug = level.backing.split(": ", 1)[1].lower()
            assert slug not in text
            assert slug.split("/")[-1] not in text
    for name in ("deepseek", "gemma", "llama", "qwen", "gpt", "claude", "mistral"):
        assert name not in text
    assert len(text.split()) <= SIZE_BOUND_WORDS
    assert "output composer" in text.split("unfixed")[-1]
    committed = (ROOT / "short-version.md").read_text(encoding="utf-8")
    assert committed == render_short_version(plan)
    assert _usd(compute(plan).with_contingency).lower() in text


def test_the_text_is_english():
    text = render_short_version(load_plan(ROOT / "cost-data.toml"))
    assert not re.search(r"[áéíóúñç¿¡]", text.lower())
    assert "evaluation budget" in text.lower()


def _with_hours(**kw) -> str:
    """Review time 6 to 18 minutes per answer: 10 inputs x 1 model = 1 to 3 hours."""
    explore = EXPLORE.replace("review_minutes_low = 2", "review_minutes_low = 6").replace(
        "review_minutes_high = 4", "review_minutes_high = 18"
    )
    return suite(explore=explore, **kw)


def test_a_level_awaiting_policy_approval_is_marked(tmp_path):
    plan = load_plan(write(tmp_path, suite(level="reasoning-high")))
    assert "reasoning-high x1 (pending policy approval)" in render_short_version(plan)
    approved = load_plan(write(tmp_path))
    assert "pending policy approval" not in render_short_version(approved).split("## Design")[1]


def test_each_suite_states_levels_models_variation_and_reviewer_hours(tmp_path):
    plan = load_plan(write(tmp_path, _with_hours()))
    rows = render_short_version(plan).splitlines()
    row = next(ln for ln in rows if ln.startswith("| Suite s1 | V"))
    assert "reasoning-low x1" in row
    assert "repetitions" in row
    assert "1 to 3 h / 1 to 3 h" in row


def test_totals_show_without_with_contingency_and_the_reserve(tmp_path):
    plan = load_plan(write(tmp_path))
    totals = compute(plan)
    text = render_short_version(plan)
    assert _usd(totals.without_contingency) in text
    assert _usd(totals.suite_contingency + totals.global_contingency) in text


def test_the_measured_and_proxy_share_is_shown(tmp_path):
    plan = load_plan(write(tmp_path, suite(basis="proxy")))
    text = render_short_version(plan)
    assert "proxy 100%" in text
    assert "measured $0.00 to $0.00 (0% of the low, 0% of the high)" in text


def test_a_possible_excess_says_may_exceed(tmp_path):
    # planned total with contingency is $8.32 to $16.63: a $10 cap is crossed only by the high
    mid = HEADER.replace("cap_usd = 30.0", "cap_usd = 10.0")
    text = render_short_version(load_plan(write(tmp_path, header=mid)))
    assert "may exceed" in text
    assert "exceeds the" not in text


def test_a_certain_excess_says_exceeds(tmp_path):
    big = HEADER.replace("cap_usd = 30.0", "cap_usd = 1.0")
    assert "exceeds the" in render_short_version(load_plan(write(tmp_path, header=big)))


def test_a_live_suite_without_a_minimum_or_planned_tier_is_rejected(tmp_path):
    with pytest.raises(TierMissingError, match="minimum"):
        load_plan(write(tmp_path, suite(tiers=("planned",))))
    with pytest.raises(TierMissingError, match="planned"):
        load_plan(write(tmp_path, suite(tiers=("minimum",))))
