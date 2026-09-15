"""Scenario matrix DEV-NET/peak (work-plan E3.1; architecture §3): 15-25 `Scenario` rows x 3
seeds, simulated with the real Runner and stored through DatabaseMCP - "ground truth for
counterfactuals" and the experiment store E3.2's question bank and the learning-effect
experiment (E4.9) will read from.

Lives at the repo root next to `verify/` and `eval/benchmarks/`, not under `tests/`, for the same
reason: it is an evaluation asset to build once and keep, not a test of one code path - `build.py`
is run manually (`python -m eval.scenario_matrix.build`), not picked up by `pytest`
(`pyproject.toml`'s `testpaths` deliberately does not list `eval/`).

Only the mechanisms already implemented when this was built (E2.2/E2.3: `lane_closure`,
`edge_closure`, `speed_limit`, `signal_program`, `demand_scale`, plus `baseline`) are in scope -
the architecture doc's own example matrix rows S05 (`condition` script) and S06 (derived network)
need E2.6 and E6.1 respectively, neither of which exists yet.
"""
