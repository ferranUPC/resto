"""DatabaseMCP conformance suite (work-plan E1.5, contract §8).

Lives at the repo root, not under `tests/`, on purpose: `docs/DATABASE_MCP_CONTRACT.md` frames
DatabaseMCP as a standard with a pluggable backend ("any third party may supply their own"), and
this suite is the acceptance test such a backend must pass (contract §9) - it should be runnable
on its own against a backend nobody has wired into this project's own test fixtures. `pytest`
(bare, from the repo root) still picks it up: see `testpaths` in `pyproject.toml`.
"""
