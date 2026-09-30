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
                 ledger (query) or to an artifact a result tool call returned (artifact); every
                 typed value that names an edge names a network of the task and the edge exists on
                 it (ADR-0032); a proposed experiment targets the task's network.
  3. construct - `ExpertRound(question, answer)`.
Attaching the round to a `Study` and persisting it is the Executor's job (E5,
`application/executor/`), not this module's.
"""

from __future__ import annotations

from resto.application.ports.llm import AgentRun, StopReason
from resto.application.ports.network_query import NetworkQueryLoader
from resto.application.tools.expert import EvidenceLedger
from resto.domain.value_objects.answer_value import (
    AnswerValue,
    BottleneckCauses,
    Edges,
)
from resto.domain.value_objects.expert_answer import EvidenceKind, ExpertAnswer
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.question import Mode
from resto.domain.value_objects.tasks import ExpertTask


class ExpertRunFailed(RuntimeError):
    """The Expert stopped (budget/error) without an `ExpertAnswer`."""


class ExpertAnswerRejected(ValueError):
    """The Expert returned a well-formed answer that breaks a semantic rule."""


def ask_expert(
    task: ExpertTask,
    run: AgentRun[ExpertAnswer],
    ledger: EvidenceLedger,
    *,
    loader: NetworkQueryLoader,
) -> ExpertRound:
    if run.stop_reason is not StopReason.OUTPUT or run.output is None:
        raise ExpertRunFailed(f"expert stopped on {run.stop_reason} without an answer")
    answer = run.output
    _check_mode(task, answer)
    _check_evidence(answer, ledger)
    _check_values(task, answer, loader)
    _check_proposed_experiment(task, answer)
    return ExpertRound(question=task.question, answer=answer)


def _check_mode(task: ExpertTask, answer: ExpertAnswer) -> None:
    if task.mode is Mode.FORCED and answer.needs_simulation:
        raise ExpertAnswerRejected("forced mode must answer; needs_simulation is not allowed")


def _check_evidence(answer: ExpertAnswer, ledger: EvidenceLedger) -> None:
    artifact_ids = ledger.artifact_ids()
    for evidence in answer.evidence:
        if evidence.kind is EvidenceKind.QUERY and ledger.get(evidence.ref) is None:
            raise ExpertAnswerRejected(
                f"evidence ref {evidence.ref!r} does not match any tool call of this run"
            )
        if evidence.kind is EvidenceKind.ARTIFACT and evidence.ref not in artifact_ids:
            raise ExpertAnswerRejected(
                f"artifact {evidence.ref!r} was not returned by any result tool call of this run"
            )


def _check_values(task: ExpertTask, answer: ExpertAnswer, loader: NetworkQueryLoader) -> None:
    # Load the task's network first: one that is not stored fails here even when no value names an
    # edge, as it did when the caller passed the query in.
    loader.load(task.network_id)
    for value in answer.values:
        for network_id, edge_id in _edge_references(value):
            if network_id != task.network_id:
                raise ExpertAnswerRejected(
                    f"edge {edge_id!r} names network {network_id!r}, "
                    f"which is not the task's network {task.network_id!r}"
                )
            if not loader.load(network_id).has_edge(edge_id):
                raise ExpertAnswerRejected(
                    f"edge {edge_id!r} in the answer is not on network {network_id!r}"
                )


def _edge_references(value: AnswerValue) -> tuple[tuple[str, str], ...]:
    """Every (network id, edge id) a value names; network-wide values name none."""
    if isinstance(value, Edges):
        return tuple((value.network_id, e) for e in value.edge_ids)
    if isinstance(value, BottleneckCauses):
        return tuple((c.network_id, c.edge_id) for c in value.causes)
    if value.edge_id is None or value.network_id is None:
        return ()
    return ((value.network_id, value.edge_id),)


def _check_proposed_experiment(task: ExpertTask, answer: ExpertAnswer) -> None:
    proposed = answer.proposed_experiment
    if proposed is not None and proposed.network_ref not in (None, task.network_id):
        raise ExpertAnswerRejected(
            f"proposed experiment targets network {proposed.network_ref!r}, "
            f"not {task.network_id!r}"
        )
