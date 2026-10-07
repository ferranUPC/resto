"""Manual end-to-end run on DEV-NET with the default model (E5.4 ticket 05, second run).

Not a pytest test (docs/llm-cost-policy.md). The Network Author (E6.1) and the Demand Generator
(E7.1) do not exist yet, so both are stubs that answer `Found` with DEV-NET and its `peak` demand,
stored in a fresh SQLite file. Parser, Builder, SUMO, Expert, note writer and Composer are real.

    python scripts/manual_study_run.py "question"            # dry run
    python scripts/manual_study_run.py "question" --run
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from eval.scenario_matrix.build import _dev_net_network, dev_net_demand

from resto.adapters.llm.anthropic_client import OpenRouterToolAgent
from resto.adapters.llm.config import load_llm_config, load_rounds_config
from resto.adapters.llm.pricing import estimate_cost_usd
from resto.adapters.persistence.sqlite.repositories import SqliteDatabase
from resto.adapters.tracing.jsonl import JsonlTracer
from resto.application.executor import StudyBudget, StudySettings
from resto.application.ports.llm import AgentRun, Budget, StopReason
from resto.application.use_cases.run_study import ParserFailed, run_study
from resto.domain.value_objects.demand_spec import DemandProfile
from resto.domain.value_objects.outcomes import Found
from resto.domain.value_objects.step_record import Usage
from resto.interface.cli.main import AGENT_SECONDS, build_deps
from resto.interface.render import render_study, render_study_text


class FoundStub:
    def __init__(self, found_id: str) -> None:
        self._id = found_id

    def obtain(self, task: object) -> AgentRun[Found]:
        return AgentRun(Found(self._id), (), Usage(), StopReason.OUTPUT)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("text")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--work", type=Path, required=True, help="empty directory for db, runs, traces")
    args = ap.parse_args()

    config = load_llm_config()
    budget = Budget(config.max_steps, config.max_output_tokens, AGENT_SECONDS)
    study_budget = StudyBudget(max_tokens=200_000)
    worst = estimate_cost_usd(config.default_model, 150_000, 50_000)
    print(f"model {config.default_model}  study budget {study_budget}")
    print(f"worst-case cost: ${worst:.3f} (study token cap 200k, at most 20 agent calls)")
    if not args.run:
        print("dry run: no API call made")
        return 0

    args.work.mkdir(parents=True, exist_ok=True)
    db = SqliteDatabase(args.work / "resto.sqlite")
    network = _dev_net_network()
    demand = dev_net_demand(DemandProfile.PEAK, network.network_id)
    db.networks.store(network)
    db.demands.store(demand)
    agent = OpenRouterToolAgent(config)
    tracer = JsonlTracer(args.work / "traces")
    deps = build_deps(db=db, agent=agent, budget=budget, tracer=tracer, out_dir=args.work)
    deps = replace(
        deps,
        agents=replace(
            deps.agents,
            network_author=FoundStub(network.network_id),
            demand_generator=FoundStub(demand.demand_id),
        ),
    )
    rounds = load_rounds_config()
    settings = StudySettings(
        out_dir=args.work,
        network_max_rounds=rounds.network_max_rounds,
        calibration_max_rounds=rounds.calibration_max_rounds,
        budget=study_budget,
    )
    try:
        study = run_study(args.text, deps, settings)
    except ParserFailed as e:
        print(f"parser failed: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()
    print(render_study_text(study))
    print("=" * 60)
    print(render_study(study))
    print(f"status: {study.status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
