"""Question bank (work-plan E3.2): generates the descriptive/diagnostic/counterfactual question
bank over the DEV-NET/peak scenario matrix (E3.1) and writes `question-bank.json` +
`question-bank-report.md`.

Run from the repo root inside the `resto` conda env (`SUMO_HOME` unset):

    python -m eval.question_bank.build

Reuses `eval.scenario_matrix.rows.ROWS`/`build_draft` and `eval.scenario_matrix.build`'s own
network/demand/context helpers to re-derive every row's `Scenario`/`SimulationResult`s against the
already-built `eval/scenario_matrix/matrix.db`: `build_scenario`/`run_simulation` dedupe on
content/request hashes (see that module's own docstring), so this touches no SUMO process, it just
reads back what E3.1 already stored. Gold answers come from `db.results.query_edgedata` (edge-level
measures) and `SimulationResult.kpis.mean_delay` (network-wide), averaged over each row's 3 seeds.

The 3.5% occupancy threshold and the 08:00-08:05 default window (both in `templates.py`) were picked
by inspecting the matrix's own edgedata while building this: DEV-NET/peak's baseline occupancy
tops out at ~3% in that window, a lane closure's upstream queue at ~6% (`eval/scenario_matrix/
runs/S00` vs `S03`) - a threshold in between gives descriptive questions a genuine, non-degenerate
answer instead of an empty edge list on every row.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path
from typing import Any

from mcp.client._memory import InMemoryTransport

from eval.question_bank import templates
from eval.question_bank.gold import mean_edgedata
from eval.question_bank.templates import QuestionBankItem, descriptive_window
from eval.scenario_matrix.build import CONTEXT_TAGS, SEEDS, _dev_net_network, _peak_demand
from eval.scenario_matrix.build import DB_PATH as MATRIX_DB_PATH
from eval.scenario_matrix.rows import ROWS, MatrixRow, build_draft
from resto.adapters.persistence.mcp_client import McpClientDatabase
from resto.adapters.persistence.sqlite.repositories import SqliteDatabase
from resto.adapters.sumo.netxml import SumolibNetworkQuery
from resto.adapters.sumo.runner import SubprocessSumoRunner
from resto.application.ports.llm import AgentRun, StopReason
from resto.application.schemas import adapter_for
from resto.application.use_cases.build_scenario import build_scenario
from resto.application.use_cases.run_simulation import run_simulation
from resto.domain.entities.demand import Demand
from resto.domain.entities.network import Network
from resto.domain.entities.scenario import Scenario
from resto.domain.entities.simulation_result import RunStatus, SimulationResult
from resto.domain.value_objects.question import Question
from resto.domain.value_objects.step_record import Usage
from resto.domain.value_objects.tasks import ScenarioTask
from resto.domain.value_objects.time_window import TimeWindow
from resto.interface.mcp.database_server import build_server

BANK_DIR = Path(__file__).resolve().parent
BANK_JSON_PATH = BANK_DIR / "question-bank.json"
REPORT_PATH = BANK_DIR / "question-bank-report.md"
REBUILD_DIR = BANK_DIR / "_rebuild"
MIN_QUESTIONS = 60


class QuestionBankBuildError(RuntimeError):
    """A row's data could not be re-derived from the matrix, or the bank ended up below the
    work-plan's 60-question floor - the bank must not be marked built while incomplete."""


def _rebuild_row(
    row: MatrixRow,
    *,
    network: Network,
    demand: Demand,
    net_ref: Any,
    peak_routes_ref: Any,
    db: McpClientDatabase,
    runner: SubprocessSumoRunner,
) -> tuple[Scenario, dict[int, SimulationResult]]:
    """Re-derives one row's `Scenario`/`SimulationResult`s against the already-built matrix -
    every call below is idempotent (content/request-hash dedup), so this runs no SUMO process
    when `matrix.db` already has the row."""
    draft = build_draft(
        row, net_ref=net_ref, peak_routes_ref=peak_routes_ref, network=network, demand=demand,
        demands=db.demands, out_dir=REBUILD_DIR / row.id / "build",
    )
    run = AgentRun(output=draft, tool_calls=(), usage=Usage(), stop_reason=StopReason.OUTPUT)
    task = ScenarioTask(
        network_id=network.network_id, demand_id=demand.demand_id, context_tags=CONTEXT_TAGS
    )
    scenario = build_scenario(
        task, run, networks=db.networks, demands=db.demands, scenarios=db.scenarios,
        network_query_factory=lambda p: SumolibNetworkQuery(p), runner=runner,
        out_dir=REBUILD_DIR / row.id / "load_check",
    )
    results: dict[int, SimulationResult] = {}
    for seed in SEEDS:
        result = run_simulation(
            scenario, seed, runner=runner, results=db.results, out_dir=REBUILD_DIR / row.id / "runs"
        )
        if result.status is not RunStatus.OK:
            raise QuestionBankBuildError(f"{row.id} seed {seed} is not OK in matrix.db")
        results[seed] = result
    return scenario, results


def _mean_delay(results: dict[int, SimulationResult]) -> float:
    means = []
    for result in results.values():
        assert result.kpis is not None  # guaranteed by SimulationResult's own invariant when OK
        means.append(result.kpis.mean_delay)
    return statistics.mean(means)


def _mean_edgedata_at(
    db: McpClientDatabase, result_ids: tuple[str, ...], window: TimeWindow
) -> dict[str, dict[str, float]]:
    per_seed = [
        db.results.query_edgedata(result_id, (), (window.start, window.end))
        for result_id in result_ids
    ]
    return mean_edgedata(per_seed)


def generate_question_bank() -> list[QuestionBankItem]:
    network = _dev_net_network()
    demand = _peak_demand(network.network_id)
    net_ref = network.net_xml
    peak_routes_ref = demand.routes

    backend = SqliteDatabase(str(MATRIX_DB_PATH))
    server = build_server(backend)
    db = McpClientDatabase(lambda: InMemoryTransport(server))
    runner = SubprocessSumoRunner()

    items: list[QuestionBankItem] = []
    try:
        db.networks.store(network)
        db.demands.store(demand)

        scenarios: dict[str, Scenario] = {}
        results_by_row: dict[str, dict[int, SimulationResult]] = {}
        for row in ROWS:
            scenario, results = _rebuild_row(
                row, network=network, demand=demand, net_ref=net_ref,
                peak_routes_ref=peak_routes_ref, db=db, runner=runner,
            )
            scenarios[row.id] = scenario
            results_by_row[row.id] = results

        baseline_row = ROWS[0]
        assert baseline_row.mechanism == "baseline"
        baseline_scenario = scenarios[baseline_row.id]
        baseline_results = results_by_row[baseline_row.id]
        baseline_result_ids = tuple(baseline_results[seed].result_id for seed in SEEDS)
        baseline_mean_delay = _mean_delay(baseline_results)

        for row in ROWS:
            scenario = scenarios[row.id]
            results = results_by_row[row.id]
            result_ids = tuple(results[seed].result_id for seed in SEEDS)
            window = descriptive_window(row)
            mean_edges = _mean_edgedata_at(db, result_ids, window)
            seed_edges = tuple(
                db.results.query_edgedata(results[seed].result_id, (), (window.start, window.end))
                for seed in SEEDS
            )
            network_id = network.network_id
            demand_id = demand.demand_id

            items.append(
                templates.descriptive_occupancy_item(
                    row, scenario, network_id=network_id, demand_id=demand_id,
                    context_tags=CONTEXT_TAGS, mean_edgedata=mean_edges, seed_edgedata=seed_edges,
                    result_ids=result_ids,
                )
            )
            items.append(
                templates.descriptive_travel_time_item(
                    row, scenario, network_id=network_id, demand_id=demand_id,
                    context_tags=CONTEXT_TAGS, mean_edgedata=mean_edges, seed_edgedata=seed_edges,
                    result_ids=result_ids,
                )
            )
            items.append(
                templates.diagnostic_bottleneck_item(
                    row, scenario, network_id=network_id, demand_id=demand_id,
                    context_tags=CONTEXT_TAGS, mean_edgedata=mean_edges, result_ids=result_ids,
                )
            )

            if row.mechanism == "baseline":
                continue

            baseline_mean_edges_at_window = _mean_edgedata_at(db, baseline_result_ids, window)
            mean_delay = _mean_delay(results)

            items.append(
                templates.counterfactual_direction_item(
                    row, scenario, baseline_scenario.scenario_id,
                    network_id=network_id, demand_id=demand_id, context_tags=CONTEXT_TAGS,
                    mean_edgedata=mean_edges, baseline_mean_edgedata=baseline_mean_edges_at_window,
                    result_ids=result_ids, baseline_result_ids=baseline_result_ids,
                )
            )
            items.append(
                templates.counterfactual_top_k_item(
                    row, scenario, baseline_scenario.scenario_id,
                    network_id=network_id, demand_id=demand_id, context_tags=CONTEXT_TAGS,
                    mean_edgedata=mean_edges, baseline_mean_edgedata=baseline_mean_edges_at_window,
                    result_ids=result_ids, baseline_result_ids=baseline_result_ids,
                )
            )
            items.append(
                templates.counterfactual_magnitude_item(
                    row, scenario, baseline_scenario.scenario_id,
                    network_id=network_id, demand_id=demand_id, context_tags=CONTEXT_TAGS,
                    mean_delay=mean_delay, baseline_mean_delay=baseline_mean_delay,
                    result_ids=result_ids, baseline_result_ids=baseline_result_ids,
                )
            )
    finally:
        db.close()
        backend.close()

    if len(items) < MIN_QUESTIONS:
        raise QuestionBankBuildError(
            f"only {len(items)} questions generated, work-plan E3.2 requires >= {MIN_QUESTIONS}"
        )
    return items


def _item_to_json(item: QuestionBankItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "question": adapter_for(Question).dump_python(item.question, mode="json"),
        "scenario_id": item.scenario_id,
        "result_ids": list(item.result_ids),
        "gold_answer": item.gold_answer,
        "evidence": item.evidence,
    }


def _write_bank_json(items: list[QuestionBankItem]) -> None:
    payload = [_item_to_json(item) for item in items]
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    BANK_JSON_PATH.write_text(text, encoding="utf-8")


def _write_report(items: list[QuestionBankItem]) -> None:
    by_family = {"desc": 0, "diag": 0, "cf": 0}
    for item in items:
        family = "desc" if "-desc-" in item.id else "diag" if item.id.endswith("-diag") else "cf"
        by_family[family] += 1

    lines = [
        "# Question bank (work-plan E3.2)",
        "",
        f"Built by `python -m eval.question_bank.build` from `eval/scenario_matrix/rows.py`'s "
        f"{len(ROWS)} rows, against `eval/scenario_matrix/matrix.db`. {len(items)} questions "
        f"total (work-plan floor: {MIN_QUESTIONS}): {by_family['desc']} descriptive, "
        f"{by_family['diag']} diagnostic, {by_family['cf']} counterfactual.",
        "",
        "| id | intent | text |",
        "|---|---|---|",
    ]
    for item in items[:10]:
        lines.append(f"| {item.id} | {item.question.intent.value} | {item.question.text} |")
    lines.append("")
    lines.append(f"Full bank: `{BANK_JSON_PATH.name}` ({len(items)} entries).")
    lines.append("")
    lines.append(
        '**Scope note on diagnostic items:** each `-diag` entry\'s `gold_answer["top_3"]` is '
        "machine-gradeable today (Jaccard against the Expert's own answer, DoD §4.7). "
        '`gold_answer["reason"]` (merge/signal/demand) is *not* wired to any grading metric yet '
        '- how to score the Expert\'s free-text "why" against it is an open question '
        "(architecture doc §8), left for E3.3 to decide. The field is present and free to "
        "compute, just unused by any metric today."
    )
    lines.append("")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    items = generate_question_bank()
    _write_bank_json(items)
    _write_report(items)
    print(f"{len(items)} questions built, {BANK_JSON_PATH} and {REPORT_PATH} written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
