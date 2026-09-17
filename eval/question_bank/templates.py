"""The three DoD §3 template families (descriptive / diagnostic / counterfactual) over one
`MatrixRow` at a time (work-plan E3.2). Pure question + gold-answer construction: every function
here takes data `build.py` has already fetched through `McpClientDatabase` (`query_edgedata`
results, `SimulationResult.kpis`) and returns one or more `QuestionBankItem`s. No DatabaseMCP
calls happen in this module, matching `gold.py`'s own "no I/O" split.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from eval.question_bank.gold import (
    EdgeMeasure,
    bottleneck_reason,
    classify_direction,
    edges_above_threshold,
    magnitude_band,
    pct_change,
    top_bottleneck_edges,
    top_k_by_delta,
)
from eval.scenario_matrix.rows import MatrixRow
from resto.domain.entities.scenario import Scenario
from resto.domain.value_objects.question import Intent, Mode, Question
from resto.domain.value_objects.time_window import TimeWindow

EdgeMeasures = Mapping[str, Mapping[str, float]]

# Fixed by inspection of the matrix's own edgedata (see eval/question_bank/build.py's module
# docstring): baseline peak occupancy tops out at ~3%, a lane closure's upstream queue at ~6% -
# this threshold cleanly separates "nothing unusual" scenarios from ones with a real hot edge.
DESCRIPTIVE_OCCUPANCY_THRESHOLD_PCT = 3.5

# Window used for every descriptive/diagnostic/counterfactual edge-level question on a row with
# no window of its own (baseline, demand_scale) - the same [0, 300) every other row already uses
# (rows.py's own docstring), so descriptive questions stay comparable across scenarios.
DEFAULT_WINDOW = TimeWindow(0.0, 300.0)

# demand_scale rows change every edge's load a little rather than one edge a lot, so they have no
# natural "target edge" of their own - B2C2 is an interior row-2 corridor edge already used by
# several other rows, a reasonable representative choice.
DEFAULT_TARGET_EDGE = "B2C2"

# signal_program rows name a TLS junction, not an edge - the edge immediately downstream of it
# (same row-2 corridor sequence A2 -> B2 -> C2 -> D2 -> E2 documented in rows.py) stands in for it.
_TLS_DOWNSTREAM_EDGE = {"A2": "A2B2", "B2": "B2C2", "C2": "C2D2", "D2": "D2E2"}

# DEV-NET topology groups for the diagnostic "why" rubric (eval/dev-net/README.md;
# eval/scenario_matrix/rows.py's own docstring): the designed 2->1 lane merge, and the row-2
# signalised corridor. Kept here rather than in gold.py so that module's classification math stays
# network-agnostic - see bottleneck_reason's own docstring.
MERGE_BOTTLENECK_EDGES = frozenset({"B0C0", "C0D0"})
SIGNALISED_CORRIDOR_EDGES = frozenset({"A2B2", "B2C2", "C2D2", "D2E2"})


@dataclass(frozen=True, slots=True)
class QuestionBankItem:
    """One question bank entry: a real domain `Question` plus its programmatic gold answer and
    the raw evidence it was computed from (so a grader can audit it, not just trust it)."""

    id: str
    question: Question
    scenario_id: str
    result_ids: tuple[str, ...]
    gold_answer: Mapping[str, Any]
    evidence: Mapping[str, Any]


def descriptive_window(row: MatrixRow) -> TimeWindow:
    return row.window if row.window is not None else DEFAULT_WINDOW


def target_edge(row: MatrixRow) -> str:
    if row.edge_id is not None:
        return row.edge_id
    if row.tls_id is not None:
        return _TLS_DOWNSTREAM_EDGE[row.tls_id]
    return DEFAULT_TARGET_EDGE


def _base_kwargs(
    scenario: Scenario,
    *,
    intent: Intent,
    network_id: str,
    demand_id: str,
    context_tags: frozenset[str],
    metrics_of_interest: tuple[str, ...],
    time_window: TimeWindow | None,
) -> dict[str, Any]:
    return {
        "intent": intent,
        "mode": Mode.FORCED,
        "network_ref": network_id,
        "demand_ref": demand_id,
        "interventions": scenario.interventions,
        "metrics_of_interest": metrics_of_interest,
        "time_window": time_window,
        "context_tags": context_tags,
    }


def descriptive_occupancy_item(
    row: MatrixRow,
    scenario: Scenario,
    *,
    network_id: str,
    demand_id: str,
    context_tags: frozenset[str],
    mean_edgedata: EdgeMeasures,
    seed_edgedata: tuple[EdgeMeasures, ...],
    result_ids: tuple[str, ...],
) -> QuestionBankItem:
    window = descriptive_window(row)
    edges = edges_above_threshold(
        mean_edgedata, EdgeMeasure.OCCUPANCY, DESCRIPTIVE_OCCUPANCY_THRESHOLD_PCT
    )
    text = (
        f"Which edges exceed {DESCRIPTIVE_OCCUPANCY_THRESHOLD_PCT:.1f}% occupancy between "
        f"{window.start:.0f}s and {window.end:.0f}s in the scenario with {row.description}?"
    )
    kwargs = _base_kwargs(
        scenario, intent=Intent.DESCRIBE, network_id=network_id, demand_id=demand_id,
        context_tags=context_tags, metrics_of_interest=("occupancy",), time_window=window,
    )
    question = Question(text=text, **kwargs)
    return QuestionBankItem(
        id=f"{row.id}-desc-occ",
        question=question,
        scenario_id=scenario.scenario_id,
        result_ids=result_ids,
        gold_answer={
            "threshold_pct": DESCRIPTIVE_OCCUPANCY_THRESHOLD_PCT,
            "window": [window.start, window.end],
            "edges_above_threshold": edges,
        },
        evidence={
            "measure": EdgeMeasure.OCCUPANCY,
            "per_seed_values": {
                edge_id: [seed[edge_id][EdgeMeasure.OCCUPANCY] for seed in seed_edgedata]
                for edge_id in edges
            },
        },
    )


def descriptive_travel_time_item(
    row: MatrixRow,
    scenario: Scenario,
    *,
    network_id: str,
    demand_id: str,
    context_tags: frozenset[str],
    mean_edgedata: EdgeMeasures,
    seed_edgedata: tuple[EdgeMeasures, ...],
    result_ids: tuple[str, ...],
) -> QuestionBankItem:
    window = descriptive_window(row)
    edge_id = target_edge(row)
    mean_travel_time = mean_edgedata[edge_id][EdgeMeasure.TRAVEL_TIME]
    text = (
        f"What is the mean travel time on {edge_id} between {window.start:.0f}s and "
        f"{window.end:.0f}s in the scenario with {row.description}?"
    )
    kwargs = _base_kwargs(
        scenario, intent=Intent.DESCRIBE, network_id=network_id, demand_id=demand_id,
        context_tags=context_tags, metrics_of_interest=("travel_time",), time_window=window,
    )
    question = Question(text=text, **kwargs)
    return QuestionBankItem(
        id=f"{row.id}-desc-tt",
        question=question,
        scenario_id=scenario.scenario_id,
        result_ids=result_ids,
        gold_answer={"edge_id": edge_id, "mean_travel_time_s": mean_travel_time},
        evidence={
            "measure": EdgeMeasure.TRAVEL_TIME,
            "per_seed_values": [seed[edge_id][EdgeMeasure.TRAVEL_TIME] for seed in seed_edgedata],
        },
    )


def diagnostic_bottleneck_item(
    row: MatrixRow,
    scenario: Scenario,
    *,
    network_id: str,
    demand_id: str,
    context_tags: frozenset[str],
    mean_edgedata: EdgeMeasures,
    result_ids: tuple[str, ...],
) -> QuestionBankItem:
    """`gold_answer["top_3"]` is machine-gradeable today (Jaccard against the Expert's own top-3,
    DoD §4.7's own metric). `gold_answer["reason"]` is NOT wired to any grading metric yet - how
    to score the Expert's free-text "why" against it (human rubric / LLM-as-judge / both with
    agreement reported) is still an open question (architecture doc §8), to be decided in E3.3.
    The field is kept here because it is free to compute and will be needed whenever that
    decision is made - it just is not evaluated by anything today."""
    window = descriptive_window(row)
    top3 = top_bottleneck_edges(mean_edgedata, k=3)
    reason = bottleneck_reason(
        top3[0], merge_edges=MERGE_BOTTLENECK_EDGES, signalised_edges=SIGNALISED_CORRIDOR_EDGES
    )
    text = (
        f"Which three edges form the main bottleneck between {window.start:.0f}s and "
        f"{window.end:.0f}s in the scenario with {row.description}, and why?"
    )
    kwargs = _base_kwargs(
        scenario, intent=Intent.DIAGNOSE, network_id=network_id, demand_id=demand_id,
        context_tags=context_tags, metrics_of_interest=("delay",), time_window=window,
    )
    question = Question(text=text, **kwargs)
    return QuestionBankItem(
        id=f"{row.id}-diag",
        question=question,
        scenario_id=scenario.scenario_id,
        result_ids=result_ids,
        gold_answer={"top_3": top3, "reason": reason},
        evidence={
            "score_measure": "time_loss * entered (mean of 3 seeds)",
            "scores": {
                edge_id: mean_edgedata[edge_id][EdgeMeasure.TIME_LOSS]
                * mean_edgedata[edge_id][EdgeMeasure.ENTERED]
                for edge_id in top3
            },
        },
    )


def counterfactual_direction_item(
    row: MatrixRow,
    scenario: Scenario,
    baseline_scenario_id: str,
    *,
    network_id: str,
    demand_id: str,
    context_tags: frozenset[str],
    mean_edgedata: EdgeMeasures,
    baseline_mean_edgedata: EdgeMeasures,
    result_ids: tuple[str, ...],
    baseline_result_ids: tuple[str, ...],
) -> QuestionBankItem:
    window = descriptive_window(row)
    edge_id = target_edge(row)
    baseline_value = baseline_mean_edgedata[edge_id][EdgeMeasure.TIME_LOSS]
    value = mean_edgedata[edge_id][EdgeMeasure.TIME_LOSS]
    direction = classify_direction(baseline_value, value)
    text = (
        f"If {row.description}, does mean delay on {edge_id} increase, decrease, or stay "
        f"within 5% relative to the baseline, over {window.start:.0f}s-{window.end:.0f}s?"
    )
    kwargs = _base_kwargs(
        scenario, intent=Intent.COUNTERFACTUAL, network_id=network_id, demand_id=demand_id,
        context_tags=context_tags, metrics_of_interest=("delay",), time_window=window,
    )
    question = Question(text=text, **kwargs)
    return QuestionBankItem(
        id=f"{row.id}-cf-dir",
        question=question,
        scenario_id=scenario.scenario_id,
        result_ids=result_ids,
        gold_answer={
            "edge_id": edge_id,
            "direction": direction,
            "pct_change": pct_change(baseline_value, value),
        },
        evidence={
            "measure": EdgeMeasure.TIME_LOSS,
            "baseline_scenario_id": baseline_scenario_id,
            "baseline_result_ids": baseline_result_ids,
            "baseline_value": baseline_value,
            "intervention_value": value,
        },
    )


def counterfactual_top_k_item(
    row: MatrixRow,
    scenario: Scenario,
    baseline_scenario_id: str,
    *,
    network_id: str,
    demand_id: str,
    context_tags: frozenset[str],
    mean_edgedata: EdgeMeasures,
    baseline_mean_edgedata: EdgeMeasures,
    result_ids: tuple[str, ...],
    baseline_result_ids: tuple[str, ...],
    k: int = 5,
) -> QuestionBankItem:
    window = descriptive_window(row)
    top_k = top_k_by_delta(baseline_mean_edgedata, mean_edgedata, EdgeMeasure.TIME_LOSS, k=k)
    text = (
        f"If {row.description}, which {k} edges change the most in delay relative to the "
        f"baseline, over {window.start:.0f}s-{window.end:.0f}s?"
    )
    kwargs = _base_kwargs(
        scenario, intent=Intent.COUNTERFACTUAL, network_id=network_id, demand_id=demand_id,
        context_tags=context_tags, metrics_of_interest=("delay",), time_window=window,
    )
    question = Question(text=text, **kwargs)
    return QuestionBankItem(
        id=f"{row.id}-cf-topk",
        question=question,
        scenario_id=scenario.scenario_id,
        result_ids=result_ids,
        gold_answer={"top_k_by_delay_change": [[edge_id, delta] for edge_id, delta in top_k]},
        evidence={
            "measure": EdgeMeasure.TIME_LOSS,
            "baseline_scenario_id": baseline_scenario_id,
            "baseline_result_ids": baseline_result_ids,
        },
    )


def counterfactual_magnitude_item(
    row: MatrixRow,
    scenario: Scenario,
    baseline_scenario_id: str,
    *,
    network_id: str,
    demand_id: str,
    context_tags: frozenset[str],
    mean_delay: float,
    baseline_mean_delay: float,
    result_ids: tuple[str, ...],
    baseline_result_ids: tuple[str, ...],
) -> QuestionBankItem:
    change = pct_change(baseline_mean_delay, mean_delay)
    band = magnitude_band(change)
    text = f"By roughly how much does network-wide mean delay change if {row.description}?"
    kwargs = _base_kwargs(
        scenario, intent=Intent.COUNTERFACTUAL, network_id=network_id, demand_id=demand_id,
        context_tags=context_tags, metrics_of_interest=("delay",), time_window=None,
    )
    question = Question(text=text, **kwargs)
    return QuestionBankItem(
        id=f"{row.id}-cf-band",
        question=question,
        scenario_id=scenario.scenario_id,
        result_ids=result_ids,
        gold_answer={"band": band, "pct_change": change},
        evidence={
            "measure": "mean_delay (whole run)",
            "baseline_scenario_id": baseline_scenario_id,
            "baseline_result_ids": baseline_result_ids,
            "baseline_mean_delay": baseline_mean_delay,
            "intervention_mean_delay": mean_delay,
        },
    )
