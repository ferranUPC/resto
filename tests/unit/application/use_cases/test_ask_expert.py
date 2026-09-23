"""`ask_expert` promotion (E4.1; ADR-0001, ADR-0011, ADR-0019): an answer is accepted only if every
evidence ref resolves to this run's tool calls, every edge in its typed values exists, forced mode
never abstains, and a proposed experiment stays on the task's network."""

from __future__ import annotations

from dataclasses import replace

import pytest

from resto.application.ports.llm import AgentRun, StopReason
from resto.application.tools.expert import EvidenceLedger
from resto.application.use_cases.ask_expert import (
    ExpertAnswerRejected,
    ExpertRunFailed,
    ask_expert,
)
from resto.domain.value_objects.answer_value import (
    AnswerValue,
    Change,
    ChangeDirection,
    Edges,
    Measure,
    Quantity,
)
from resto.domain.value_objects.expert_answer import (
    Basis,
    Evidence,
    EvidenceKind,
    ExpertAnswer,
)
from resto.domain.value_objects.question import Intent, Mode, Question
from resto.domain.value_objects.step_record import Usage
from resto.domain.value_objects.tasks import ExpertTask
from tests.unit.application.use_cases.test_build_scenario import StubNetworkQuery

NETWORK = "abc123"
INCREASE_ON_B2C2 = Change(
    measure=Measure.TIME_LOSS, direction=ChangeDirection.INCREASE, relative_change_pct=20.0,
    edge_id="B2C2",
)
QUERY = StubNetworkQuery(edges=frozenset({"B2C2", "B1B0"}))


def _task(mode: Mode = Mode.FORCED) -> ExpertTask:
    return ExpertTask(
        question="does delay on B2C2 increase?", mode=mode, network_id=NETWORK, result_ids=("r1",)
    )


def _run(
    answer: ExpertAnswer | None, stop: StopReason = StopReason.OUTPUT
) -> AgentRun[ExpertAnswer]:
    return AgentRun(output=answer, tool_calls=(), usage=Usage(), stop_reason=stop)


def _ledger() -> EvidenceLedger:
    ledger = EvidenceLedger()
    ledger.record(
        "get_result",
        {"result_id": "r1"},
        {"result_id": "r1", "artifacts": [{"path": "/runs/r1/edgedata.xml", "content_hash": "h1"}]},
    )
    ledger.record("query_edgedata", {"result_id": "r1"}, {"B2C2": {"time_loss": 12.0}})
    return ledger


def _answer(
    *evidence: Evidence, values: tuple[AnswerValue, ...] = (INCREASE_ON_B2C2,)
) -> ExpertAnswer:
    return ExpertAnswer(
        answer="delay on B2C2 rises by about 20 %",
        basis=Basis.OBSERVED,
        confidence=0.8,
        evidence=evidence or (Evidence(kind=EvidenceKind.QUERY, ref="q2", excerpt="12.0"),),
        values=values,
    )


def _abstention(network_ref: str | None = NETWORK) -> ExpertAnswer:
    return ExpertAnswer(
        answer="no simulation covers this closure",
        basis=Basis.EXTRAPOLATED,
        confidence=0.2,
        needs_simulation=True,
        proposed_experiment=Question(
            text="close B2C2 lane 0 at peak", intent=Intent.COUNTERFACTUAL, network_ref=network_ref
        ),
    )


def test_a_fully_resolvable_answer_becomes_a_round() -> None:
    answer = _answer(
        Evidence(kind=EvidenceKind.QUERY, ref="q1"),
        Evidence(kind=EvidenceKind.QUERY, ref="q2", excerpt="12.0"),
    )
    round_ = ask_expert(_task(), _run(answer), _ledger(), query=QUERY)
    assert round_.question == _task().question
    assert round_.answer == answer
    assert not round_.forced_by_limit


@pytest.mark.parametrize("ref", ["/runs/r1/edgedata.xml", "h1"])
def test_artifact_evidence_resolves_by_path_or_content_hash(ref: str) -> None:
    answer = _answer(Evidence(kind=EvidenceKind.ARTIFACT, ref=ref))
    assert ask_expert(_task(), _run(answer), _ledger(), query=QUERY).answer == answer


@pytest.mark.parametrize("stop", [StopReason.BUDGET, StopReason.ERROR])
def test_a_run_without_an_answer_fails(stop: StopReason) -> None:
    with pytest.raises(ExpertRunFailed):
        ask_expert(_task(), _run(None, stop), _ledger(), query=QUERY)


def test_a_query_ref_not_in_the_ledger_is_rejected() -> None:
    answer = _answer(Evidence(kind=EvidenceKind.QUERY, ref="q9"))
    with pytest.raises(ExpertAnswerRejected, match="q9"):
        ask_expert(_task(), _run(answer), _ledger(), query=QUERY)


def test_a_ref_invented_in_another_format_is_rejected() -> None:
    answer = _answer(Evidence(kind=EvidenceKind.QUERY, ref="query_edgedata:r1"))
    with pytest.raises(ExpertAnswerRejected):
        ask_expert(_task(), _run(answer), _ledger(), query=QUERY)


def test_an_artifact_no_result_call_returned_is_rejected() -> None:
    answer = _answer(Evidence(kind=EvidenceKind.ARTIFACT, ref="/runs/other/edgedata.xml"))
    with pytest.raises(ExpertAnswerRejected, match="artifact"):
        ask_expert(_task(), _run(answer), _ledger(), query=QUERY)


@pytest.mark.parametrize(
    "value",
    [
        Edges(edge_ids=("B1B0", "Z9Z9")),
        Quantity(measure=Measure.TRAVEL_TIME, value=23.4, edge_id="Z9Z9"),
        replace(INCREASE_ON_B2C2, edge_id="Z9Z9"),
    ],
)
def test_an_edge_that_is_not_on_the_network_is_rejected(value: AnswerValue) -> None:
    with pytest.raises(ExpertAnswerRejected, match="Z9Z9"):
        ask_expert(_task(), _run(_answer(values=(value,))), _ledger(), query=QUERY)


def test_network_wide_values_need_no_edge_check() -> None:
    value = Change(measure=Measure.MEAN_DELAY, direction=ChangeDirection.UNCHANGED)
    round_ = ask_expert(_task(), _run(_answer(values=(value,))), _ledger(), query=QUERY)
    assert round_.answer.values == (value,)


def test_forced_mode_never_abstains() -> None:
    with pytest.raises(ExpertAnswerRejected, match="forced"):
        ask_expert(_task(Mode.FORCED), _run(_abstention()), _ledger(), query=QUERY)


def test_free_mode_may_abstain_with_a_proposed_experiment() -> None:
    round_ = ask_expert(_task(Mode.FREE), _run(_abstention()), EvidenceLedger(), query=QUERY)
    assert round_.answer.needs_simulation


def test_proposed_experiment_without_a_network_ref_is_accepted() -> None:
    answer = _abstention(network_ref=None)
    round_ = ask_expert(_task(Mode.FREE), _run(answer), EvidenceLedger(), query=QUERY)
    assert round_.answer.proposed_experiment is not None


def test_proposed_experiment_on_another_network_is_rejected() -> None:
    with pytest.raises(ExpertAnswerRejected, match="network"):
        ask_expert(
            _task(Mode.FREE), _run(_abstention(network_ref="other")), EvidenceLedger(), query=QUERY
        )
