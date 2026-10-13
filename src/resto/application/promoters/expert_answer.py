"""Network Expert promotion: an already-run `AgentRun[ExpertAnswer]` -> an `ExpertRound`
(DoD §2.2, §2.4, §4.7; ADR-0001, ADR-0011, ADR-0018, ADR-0019, ADR-0042 §5).

Running the Expert is `adapters/llm/agents/expert.py::run_expert`, which must be given the same
`EvidenceLedger` this context carries. The caller loads the `NetworkQuery` of every network of the
task's scope first, so a network that is not stored fails at load time, before promotion.

Promotion order (ADR-0001):
  1. syntactic - the run stopped with an `ExpertAnswer` (its invariants already ran: evidence and
                 typed values unless abstaining, confidence in [0, 1], a proposed experiment when
                 abstaining, each value's own scope/sign rules).
  2. semantic  - forced mode never abstains; every evidence ref resolves to a tool call in the
                 ledger (query) or to an artifact a result tool call returned (artifact); every
                 typed value that names an edge names a network of the task's scope and the edge
                 exists on it (ADR-0032); a proposed experiment targets a network of the scope.
  3. construct - `ExpertRound(question, answer)`.
Attaching the round to a `Study` is the study flow's job (`application/run_study/`).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from resto.application.ports.llm import AgentRun
from resto.application.ports.network_query import NetworkQuery
from resto.application.promotion import DraftRejected, require_draft
from resto.application.tools.expert import EvidenceLedger
from resto.domain.value_objects.expert_answer import ExpertAnswer
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.question import Mode
from resto.domain.value_objects.tasks import ExpertTask


@dataclass(frozen=True, slots=True)
class ExpertAnswerContext:
    """What the Expert was given: its task, the ledger its tool calls filled, and the loaded
    `NetworkQuery` of each network of the task's scope, by network id."""

    task: ExpertTask
    ledger: EvidenceLedger
    networks: Mapping[str, NetworkQuery]

    def __post_init__(self) -> None:
        if set(self.networks) != set(self.task.network_ids):
            raise ValueError(
                f"the context's networks {sorted(self.networks)} are not the task's scope "
                f"{list(self.task.network_ids)}"
            )


@dataclass(frozen=True, slots=True)
class ExpertAnswerPromoter:
    def promote(self, run: AgentRun[ExpertAnswer], context: ExpertAnswerContext) -> ExpertRound:
        task = context.task
        answer = require_draft(run, "expert")
        _check_mode(task, answer)
        context.ledger.ensure_cited(answer.evidence)
        _check_values(task, answer, context.networks)
        _check_proposed_experiment(task, answer)
        return ExpertRound(question=task.question, answer=answer)


def _check_mode(task: ExpertTask, answer: ExpertAnswer) -> None:
    if task.mode is Mode.FORCED and answer.needs_simulation:
        raise DraftRejected("forced mode must answer; needs_simulation is not allowed")


def _check_values(
    task: ExpertTask, answer: ExpertAnswer, networks: Mapping[str, NetworkQuery]
) -> None:
    for value in answer.values:
        for network_id, edge_id in value.edge_references:
            if network_id not in networks:
                raise DraftRejected(
                    f"edge {edge_id!r} names network {network_id!r}, "
                    f"which is not in the study's networks {list(task.network_ids)}"
                )
            if not networks[network_id].has_edge(edge_id):
                raise DraftRejected(
                    f"edge {edge_id!r} in the answer is not on network {network_id!r}"
                )


def _check_proposed_experiment(task: ExpertTask, answer: ExpertAnswer) -> None:
    proposed = answer.proposed_experiment
    if proposed is not None and proposed.network_ref not in (None, *task.network_ids):
        raise DraftRejected(
            f"proposed experiment targets network {proposed.network_ref!r}, "
            f"which is not in the study's networks {list(task.network_ids)}"
        )
