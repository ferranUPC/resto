"""The short English version for the supervisors (E3.9/03), rendered from the same model."""

from __future__ import annotations

import re
from pathlib import Path

from eval.budget import compute, load_plan, render_short_version
from eval.budget.model import MIN_TIER, Range

from tests.unit.eval.budget_fixtures import HEADER, suite, write

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
    rows = [ln for ln in text.splitlines() if ln.startswith("| Suite s")]
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
        if ": " in level.backing:
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
