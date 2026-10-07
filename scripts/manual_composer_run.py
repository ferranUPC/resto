"""Manual run of the Output Composer with the default model (E5.4 ticket 05).

Not a pytest test (docs/llm-cost-policy.md: the suite never calls the real API). The completed study
is built in this process from invented numbers, because `StudyRepository` is in memory:

    python scripts/manual_composer_run.py            # dry run: config, budget, cost estimate
    python scripts/manual_composer_run.py --run      # one real call with RESTO_LLM_DEFAULT_MODEL
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace

from tests.unit.domain._fixtures import artifact
from tests.unit.domain._samples import study as sample_study

from resto.adapters.llm.agents.composer import COMPOSER_VERSION, ComposerPort
from resto.adapters.llm.anthropic_client import OpenRouterToolAgent
from resto.adapters.llm.config import load_llm_config
from resto.adapters.llm.pricing import estimate_cost_usd
from resto.adapters.persistence.memory import InMemoryResultRepository
from resto.application.ports.llm import Budget
from resto.application.use_cases.compose_report import compose_report
from resto.domain.entities.simulation_result import RunMode, RunStatus, SimulationResult
from resto.domain.value_objects.answer_value import Change, ChangeDirection, Measure
from resto.domain.value_objects.expert_answer import Basis, Evidence, EvidenceKind, ExpertAnswer
from resto.domain.value_objects.kpis import Kpis
from resto.interface.render import render_study

BASE = SimulationResult(
    result_id="res0",
    scenario_id="s0",
    seed=1,
    mode=RunMode.ONLINE,
    status=RunStatus.OK,
    content_hash="rc0",
    artifacts=(artifact("edgedata.xml", "ed0", "edgedata"),),
    kpis=Kpis(mean_delay=37.5, mean_travel_time=281.0, teleports=0, departed=500, arrived=497),
    wall_clock_s=58.0,
)
TREATMENT = SimulationResult(
    result_id="res1",
    scenario_id="s1",
    seed=1,
    mode=RunMode.ONLINE,
    status=RunStatus.OK,
    content_hash="rc1",
    artifacts=(artifact("edgedata.xml", "ed1", "edgedata"),),
    kpis=Kpis(mean_delay=42.0, mean_travel_time=300.0, teleports=0, departed=500, arrived=498),
    wall_clock_s=61.5,
)
ANSWER = ExpertAnswer(
    answer=(
        "Closing lane 1 of E12 during the 07:00-10:00 peak raises mean delay from 37.5 s to 42.0 s "
        "(about +12 %) and mean travel time from 281 s to 300 s. No vehicle teleported in either "
        "run and 497 versus 498 of 500 vehicles arrived, so the closure shifts delay without "
        "gridlock. The largest time loss moves to E12 itself."
    ),
    basis=Basis.OBSERVED,
    confidence=0.8,
    evidence=(
        Evidence(EvidenceKind.ARTIFACT, "res0", "baseline: mean_delay 37.5 s, travel time 281 s"),
        Evidence(EvidenceKind.ARTIFACT, "res1", "closure: mean_delay 42.0 s, travel time 300 s"),
    ),
    values=(
        Change(
            measure=Measure.TIME_LOSS,
            direction=ChangeDirection.INCREASE,
            relative_change_pct=12.0,
            edge_id="E12",
            network_id="abc123",
        ),
    ),
)


def build_study():  # type: ignore[no-untyped-def]
    study = sample_study()
    phase = replace(study.phases[0], round=replace(study.phases[0].round, answer=ANSWER))
    return replace(study, phases=(phase,))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", action="store_true", help="make the real call")
    args = parser.parse_args()

    config = load_llm_config()
    budget = Budget(config.max_steps, config.max_output_tokens, 120.0)
    print(f"model {config.default_model}  composer {COMPOSER_VERSION}  budget {budget}")
    worst = estimate_cost_usd(
        config.default_model, budget.max_steps * 4000, budget.max_steps * budget.max_tokens
    )
    print(f"worst-case cost estimate: ${worst:.4f}")
    if not args.run:
        print("dry run: no API call made")
        return 0

    study = build_study()
    results = InMemoryResultRepository()
    results.store(BASE)
    results.store(TREATMENT)
    run = ComposerPort(OpenRouterToolAgent(config), budget, results).compose(study)
    cost = estimate_cost_usd(config.default_model, run.usage.input_tokens, run.usage.output_tokens)
    print(f"stop {run.stop_reason}  usage {run.usage}  cost ${cost:.6f}")
    for call in run.tool_calls:
        print(f"  tool {call.name}({dict(call.arguments)})")
    if run.output is None:
        print("no draft produced")
        return 1
    report = compose_report(study, run)
    print("\n" + render_study(replace(study, report=report)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
