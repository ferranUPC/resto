"""Network Expert promotion: an already-run `AgentRun[ExpertAnswer]` -> an `ExpertRound`
(DoD §2.2, §2.4, §4.7; ADR-0001, ADR-0011, ADR-0018, ADR-0019).

Like `build_scenario`, this takes the agent's run as a finished fact: running the Expert is
`adapters/llm/agents/expert.py::run_expert`, which must be given the same `EvidenceLedger` passed
here.

Promotion order (ADR-0001):
  1. syntactic - the run stopped with an `ExpertAnswer` (its invariants already ran: evidence and
                 typed values unless abstaining, confidence in [0, 1], a proposed experiment when
                 abstaining, each value's own scope/sign rules).
  2. semantic  - forced mode never abstains; every evidence ref resolves to a tool call in the
                 ledger (query) or to an artifact a result tool call returned (artifact); every edge
                 named in a typed value exists on the network; a proposed experiment targets the
                 task's network.
  3. construct - `ExpertRound(question, answer)`.
Attaching the round to a `Study` and persisting it is the Executor's job (E5,
`application/executor/`), not this module's.
"""

from __future__ import annotations

from resto.application.ports.llm import AgentRun
from resto.application.ports.network_query import NetworkQuery
from resto.application.promotion import DraftRejected, require_draft
from resto.application.tools.expert import EvidenceLedger
from resto.domain.value_objects.answer_value import BottleneckCauses, Edges
from resto.domain.value_objects.expert_answer import EvidenceKind, ExpertAnswer
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.question import Mode
from resto.domain.value_objects.tasks import ExpertTask


def ask_expert(
    task: ExpertTask,
    run: AgentRun[ExpertAnswer],
    ledger: EvidenceLedger,
    *,
    query: NetworkQuery,
) -> ExpertRound:
    answer = require_draft(run, "expert")
    _check_mode(task, answer)
    _check_evidence(answer, ledger)
    _check_values(answer, query)
    _check_proposed_experiment(task, answer)
    return ExpertRound(question=task.question, answer=answer)


def _check_mode(task: ExpertTask, answer: ExpertAnswer) -> None:
    if task.mode is Mode.FORCED and answer.needs_simulation:
        raise DraftRejected("forced mode must answer; needs_simulation is not allowed")


def _check_evidence(answer: ExpertAnswer, ledger: EvidenceLedger) -> None:
    artifact_ids = ledger.artifact_ids()
    for evidence in answer.evidence:
        if evidence.kind is EvidenceKind.QUERY and ledger.get(evidence.ref) is None:
            raise DraftRejected(
                f"evidence ref {evidence.ref!r} does not match any tool call of this run"
            )
        if evidence.kind is EvidenceKind.ARTIFACT and evidence.ref not in artifact_ids:
            raise DraftRejected(
                f"artifact {evidence.ref!r} was not returned by any result tool call of this run"
            )


def _check_values(answer: ExpertAnswer, query: NetworkQuery) -> None:
    for value in answer.values:
        edge_ids = (
            value.edge_ids if isinstance(value, Edges | BottleneckCauses) else (value.edge_id,)
        )
        for edge_id in edge_ids:
            if edge_id is not None and not query.has_edge(edge_id):
                raise DraftRejected(f"edge {edge_id!r} in the answer is not on the network")


def _check_proposed_experiment(task: ExpertTask, answer: ExpertAnswer) -> None:
    proposed = answer.proposed_experiment
    if proposed is not None and proposed.network_ref not in (None, task.network_id):
        raise DraftRejected(
            f"proposed experiment targets network {proposed.network_ref!r}, "
            f"not {task.network_id!r}"
        )
