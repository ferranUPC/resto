"""The full internal plan in Markdown (E3.9/01), rendered from the data."""

from __future__ import annotations

from pathlib import Path

from eval.budget import compute, load_plan, render_full_plan

from tests.unit.eval.budget_fixtures import HEADER, suite, write


def test_the_plan_shows_tiers_basis_and_totals_per_pass_against_the_cap(tmp_path):
    text = render_full_plan(load_plan(write(tmp_path)))
    assert "Suite s1" in text
    assert "minimum" in text and "planned" in text and "extended" not in text
    assert "measured" in text and "run-x" in text
    assert "V1" in text and "V2" in text
    assert "$30" in text
    assert "with contingency" in text.lower() and "without contingency" in text.lower()


def test_the_total_in_the_plan_is_the_models_total(tmp_path):
    plan = load_plan(write(tmp_path))
    totals = compute(plan)
    assert f"{totals.with_contingency.low:.2f}" in render_full_plan(plan)


def test_an_excess_over_the_cap_is_stated(tmp_path):
    big = HEADER.replace("cap_usd = 30.0", "cap_usd = 1.0")
    text = render_full_plan(load_plan(write(tmp_path, header=big)))
    assert "exceeds" in text.lower()


def test_totals_show_per_pass_with_and_without_contingency_and_the_reserve(tmp_path):
    plan = load_plan(write(tmp_path))
    totals = compute(plan)
    text = render_full_plan(plan)
    assert "V2 without contingency" in text and "V2 with contingency" in text
    assert "V1 without contingency" in text and "V1 with contingency" in text
    assert f"{totals.suites[0].contingency['V2'].low:.2f}" in text  # per-suite reserve in dollars
    assert "no per-pass cap" in text


def test_the_plan_shows_the_measured_and_proxy_share(tmp_path):
    text = render_full_plan(load_plan(write(tmp_path, suite(basis="proxy"))))
    assert "| proxy |" in text and "100% of the low" in text
    assert "| measured |" in text


def test_a_removed_suite_is_listed_as_excluded(tmp_path):
    plan = load_plan(write(tmp_path, suite(), suite(suite_id="gone", removed="removed by r13")))
    assert "removed by r13" in render_full_plan(plan)


def test_pending_policy_approval_is_shown(tmp_path):
    text = render_full_plan(load_plan(write(tmp_path, suite(level="reasoning-high"))))
    assert "pending policy approval" in text


def test_the_committed_plan_file_is_up_to_date():
    root = Path(__file__).resolve().parents[3] / "eval" / "budget"
    assert (root / "full-plan.md").read_text(encoding="utf-8") == render_full_plan(
        load_plan(root / "cost-data.toml")
    )


def test_totals_are_shown_per_tier_with_the_excess_over_the_cap(tmp_path):
    big = HEADER.replace("cap_usd = 30.0", "cap_usd = 1.0")
    text = render_full_plan(load_plan(write(tmp_path, header=big)))
    assert "## Totals per tier" in text
    assert "| minimum |" in text and "| planned |" in text
    assert "| extended |" not in text  # the fixture suite has no extended tier


def test_the_shipped_plan_lists_unfixed_suites_and_reviewer_effort_apart():
    root = Path(__file__).resolve().parents[3] / "eval" / "budget"
    text = render_full_plan(load_plan(root / "cost-data.toml"))
    assert "## Suites whose shape is unfixed" in text
    unfixed = text.split("## Suites whose shape is unfixed")[1].split("\n## ")[0]
    assert "Output Composer" in unfixed and "Input Parser" not in unfixed
    assert "Reviewer effort" in text and "hours" in text
    assert "| extended |" in text
    assert "removed by r13" in text
