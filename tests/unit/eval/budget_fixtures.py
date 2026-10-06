"""Minimal cost data for the budget tests: written to a temporary directory, loaded through
`eval.budget.load_plan`. Prices come from the real manifest (deepseek 0.15 in / 0.60 out)."""

from __future__ import annotations

from pathlib import Path

HEADER = """
[plan]
cap_usd = 30.0
global_contingency = 0.10

[levels.reasoning-low]
manifest = "deepseek/deepseek-v4.1-flash"
policy = "approved"

[levels.reasoning-high]
input_per_mtok = 3.0
output_per_mtok = 15.0
assumption = "test assumption"
policy = "pending policy approval"
"""

# 10 inputs x 2 reps x 1 model x 1 call x (1,000,000 in, 100,000 out) at 0.15 / 0.60
# = 20 x (0.15 + 0.06) = 4.20 low; the high tokens are double: 8.40.
STAGE = """
[[suites.tiers.stages]]
pass = "{pass_}"
inputs = 10
repetitions = {reps}
calls_per_input = 1
models = [{{ level = "{level}", count = 1 }}]
tokens_in_low = 1000000
tokens_in_high = 2000000
tokens_out_low = 100000
tokens_out_high = 200000
basis = "{basis}"
derived_from = "run-x"
"""


def suite(
    *,
    suite_id: str = "s1",
    contingency: float = 0.20,
    min_reps: int = 2,
    basis: str = "measured",
    level: str = "reasoning-low",
    removed: str = "",
) -> str:
    out = f"""
[[suites]]
id = "{suite_id}"
name = "Suite {suite_id}"
measures = "something"
threshold = "DoD x"
varies = "repetitions"
contingency = {contingency}
"""
    if removed:
        out += f'removed = "{removed}"\n'
    for tier in ("minimum", "planned"):
        out += f'\n[[suites.tiers]]\nname = "{tier}"\n'
        reps = min_reps if tier == "minimum" else 3
        out += STAGE.format(pass_="V2", reps=reps, level=level, basis=basis)
    return out


def write(tmp_path: Path, *suites: str, header: str = HEADER) -> Path:
    path = tmp_path / "cost.toml"
    path.write_text(header + "".join(suites or (suite(),)), encoding="utf-8")
    return path
