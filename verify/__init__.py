"""Effect-verification harness (work-plan E2.4, DoD §4.5): per intervention type, reads a real
Runner execution's `edgedata`/TLS-switch output and asserts the observable effect the Builder
bank (work-plan E2.7) will later be graded against ("Target >= 27/30").

Lives at the repo root, not under `tests/`, for the same reason `conformance/` does (see its own
`__init__.py`): it is the acceptance check a Builder-produced `Scenario` must pass, not a test of
one specific code path - `pytest` (bare, from the repo root) still picks it up via `testpaths` in
`pyproject.toml`. `effects.py` holds the reusable `verify_*` functions; each `test_*.py` here
proves the harness itself is correct on one real, hand-built scenario per intervention type
(E2.2/E2.3's four static mechanisms), run through the real `SubprocessSumoRunner` against
DEV-NET, not a fake.

Two things had to be found empirically, not read off a spec, before this harness could be
written correctly (see `adapters/sumo/runner.py`'s module docstring for the first):
  - `lane_closure`/`edge_closure` need `--ignore-route-errors` to avoid hard-failing the whole
    run, now handled once in the Runner itself.
  - `edgedata`'s fixed aggregation period (`EDGEDATA_PERIOD_S`, currently 300s) is unrelated to
    an intervention's own `window`; a flow check is only meaningful when the window lines up
    exactly with an interval boundary. `verify_edge_flow` raises rather than silently
    misinterpreting a misaligned window - see its docstring.
"""
