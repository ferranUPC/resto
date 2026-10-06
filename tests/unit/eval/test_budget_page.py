"""The interactive budget page (E3.9/04): same model, in-page sums only, Node parity."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from eval.budget import compute, load_plan
from eval.budget.page import render_page

from tests.unit.eval.budget_fixtures import HEADER, suite, write

ROOT = Path(__file__).resolve().parents[3] / "eval" / "budget"
RUNNER = """
const fs = require("fs");
const [, , htmlPath, fragment] = process.argv;
const html = fs.readFileSync(htmlPath, "utf8");
const core = html.match(/<script id="core">([\\s\\S]*?)<\\/script>/)[1];
const data = JSON.parse(
  html.match(/<script id="data" type="application\\/json">([\\s\\S]*?)<\\/script>/)[1]
);
const api = new Function(core + "; return { parseFragment, totals };")();
const state = api.parseFragment(data, fragment);
process.stdout.write(JSON.stringify({ state, totals: api.totals(data, state) }));
"""


def _node_totals(tmp_path: Path, html: str, fragment: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed: the in-page calculation parity check is skipped")
    page = tmp_path / "page.html"
    page.write_text(html, encoding="utf-8")
    runner = tmp_path / "run.js"
    runner.write_text(RUNNER, encoding="utf-8")
    out = subprocess.run(
        [node, str(runner), str(page), fragment], capture_output=True, text=True, check=True
    )
    return json.loads(out.stdout)


def _pair(r) -> list[float]:
    return [r.low, r.high]


def test_the_page_is_one_file_without_network_references_or_model_names():
    html = render_page(load_plan(ROOT / "cost-data.toml"))
    assert html.startswith("<!doctype html>")
    assert not re.search(r"(src|href)=[\"']https?:", html)
    assert "deepseek" not in html.lower() and "claude" not in html.lower()
    assert "viewport" in html and "measured" in html and "proxy" in html


def test_page_matches_the_python_model_on_the_default_and_a_restored_link(tmp_path):
    plan = load_plan(write(tmp_path, suite(suite_id="a"), suite(suite_id="b")))
    html = render_page(plan)
    default = _node_totals(tmp_path, html, "")
    assert default["totals"]["withContingency"] == pytest.approx(
        _pair(compute(plan).with_contingency)
    )

    link = "#tier.a=minimum&tier.b=planned&c.a=0.5&g=0.2"
    got = _node_totals(tmp_path, html, link)
    assert got["state"]["tiers"] == {"a": "minimum", "b": "planned"}
    plan2 = replace(
        plan,
        global_contingency=0.2,
        suites=tuple(replace(s, contingency=0.5) if s.id == "a" else s for s in plan.suites),
    )
    want = compute(plan2, {"a": "minimum", "b": "planned"})
    t = got["totals"]
    assert t["withContingency"] == pytest.approx(_pair(want.with_contingency))
    assert t["withoutContingency"] == pytest.approx(_pair(want.without_contingency))
    for p in ("V1", "V2"):
        assert t["byPass"][p] == pytest.approx(_pair(want.by_pass[p]))
    assert t["excess"] == pytest.approx(_pair(want.excess_over_cap))
    assert t["byBasis"]["measured"] == pytest.approx(_pair(want.by_basis["measured"]))


def test_parity_on_the_shipped_plan_for_every_uniform_tier(tmp_path):
    plan = load_plan(ROOT / "cost-data.toml")
    html = render_page(plan)
    live = [s for s in plan.suites if not s.removed]
    for tier in ("minimum", "planned", "extended"):
        fragment = "#" + "&".join(f"tier.{s.id}={tier}" for s in live)
        got = _node_totals(tmp_path, html, fragment)["totals"]
        want = compute(plan, {s.id: tier for s in live})
        assert got["withContingency"] == pytest.approx(_pair(want.with_contingency))
        assert got["byPass"]["V1"] == pytest.approx(_pair(want.by_pass["V1"]))


def test_a_bad_fragment_falls_back_to_the_defaults(tmp_path):
    plan = load_plan(write(tmp_path))
    got = _node_totals(tmp_path, render_page(plan), "#tier.s1=bogus&c.s1=abc&g=-3")
    assert got["state"]["tiers"] == {"s1": "planned"}
    assert got["totals"]["withContingency"] == pytest.approx(_pair(compute(plan).with_contingency))


def test_the_excess_over_the_cap_is_reported(tmp_path):
    big = HEADER.replace("cap_usd = 30.0", "cap_usd = 1.0")
    plan = load_plan(write(tmp_path, header=big))
    got = _node_totals(tmp_path, render_page(plan), "")["totals"]
    assert got["excess"][1] > 0


def test_the_committed_page_is_up_to_date():
    assert (ROOT / "budget.html").read_text(encoding="utf-8") == render_page(
        load_plan(ROOT / "cost-data.toml")
    )


def test_the_page_script_says_may_exceed_when_only_the_high_total_is_over():
    html = (ROOT / "page_template.html").read_text(encoding="utf-8")
    assert "May exceed the $" in html
