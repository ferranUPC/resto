"""`python -m eval.budget`: rewrite `full-plan.md` from `cost-data.toml`; no model or network."""

from __future__ import annotations

from pathlib import Path

from eval.budget import load_plan, render_full_plan

HERE = Path(__file__).resolve().parent


def main() -> None:
    plan = load_plan(HERE / "cost-data.toml")
    (HERE / "full-plan.md").write_text(render_full_plan(plan), encoding="utf-8")


if __name__ == "__main__":
    main()
