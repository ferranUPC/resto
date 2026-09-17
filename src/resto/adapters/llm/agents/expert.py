"""Configuration of the Network Expert agent: system prompt, tool list, output type, budget
(DoD §2.2, §2.4; ADR-0011, ADR-0018).

No logic of its own: the loop lives in the `ToolAgent` implementation, tool behaviour and the
evidence ledger in `application/tools/expert.py`, and checking the answer (evidence refs resolve,
forced mode never abstains) in `application/use_cases/ask_expert.py`. This module assembles the
`AgentTask`/tools for one `ExpertTask` and calls the agent.
"""

from __future__ import annotations

from resto.application.ports.llm import AgentRun, AgentTask, Budget, ToolAgent
from resto.application.ports.network_query import NetworkQuery
from resto.application.ports.repositories import (
    NoteRepository,
    ResultRepository,
    ScenarioRepository,
)
from resto.application.tools.expert import EvidenceLedger, build_expert_tools
from resto.domain.value_objects.expert_answer import ExpertAnswer
from resto.domain.value_objects.tasks import ExpertTask

SYSTEM_PROMPT = """\
You are the Network Expert of a SUMO traffic-simulation framework. You answer one question about one
road network from what has been simulated on it. You never run simulations yourself.

Facts only through tools. Topology comes from get_edge, get_lanes, get_neighbours, shortest_path,
capacity_estimate and get_tls. Simulated data comes from get_result, list_results, query_edgedata
and get_scenario (use it to tell which result is the baseline and which one carries an
intervention). Never state a number, an edge id or a result you did not get from a tool call in
this conversation. Only the results listed in `result_ids` are available; if it is empty, no
simulation data is available for this question. When `notes_allowed` is true you also have
search_notes: earlier notes are interpretations, not facts - a note alone never makes an answer
observed.

Every tool returns {"ref": "q<N>", "result": ...}. Cite what supports your answer in `evidence`:
  - {"kind": "query", "ref": "q<N>", "excerpt": "<the value(s) you used>"} for a tool call, or
  - {"kind": "artifact", "ref": "<path or content_hash>"} for an artifact a result tool returned.
A ref you did not receive makes the whole answer invalid.

Declare `basis` and `confidence` (0 to 1):
  - observed: read directly from simulated data for exactly the situation asked about;
  - inferred: derived from simulated data of this network, but not the exact situation;
  - extrapolated: no simulation covers it; reasoned from topology or general knowledge.

Mode (`mode` in the input):
  - forced: you must answer. If the data does not cover the question, answer anyway with
    basis = extrapolated and a low confidence. needs_simulation must be false.
  - free: if the available data cannot support an answer, you may abstain: needs_simulation = true
    and a proposed_experiment (a Question on this network) that would settle it.

Submit your ExpertAnswer with submit_output: `answer` in plain prose, then basis, confidence,
evidence, needs_simulation and proposed_experiment (null unless you abstain).
"""


def build_task(task: ExpertTask) -> AgentTask:
    return AgentTask(
        system_prompt=SYSTEM_PROMPT,
        input={
            "question": task.question,
            "mode": task.mode.value,
            "network_id": task.network_id,
            "result_ids": list(task.result_ids),
            "notes_allowed": task.notes_allowed,
        },
    )


def run_expert(
    task: ExpertTask,
    agent: ToolAgent,
    budget: Budget,
    *,
    query: NetworkQuery,
    results: ResultRepository,
    scenarios: ScenarioRepository,
    notes: NoteRepository | None,
    ledger: EvidenceLedger,
) -> AgentRun[ExpertAnswer]:
    """Runs the Expert on `task`; every tool call lands in `ledger`. The returned answer is
    unchecked - hand the run and the same ledger to `ask_expert` to promote it."""
    tools = build_expert_tools(
        task=task, query=query, results=results, scenarios=scenarios, notes=notes, ledger=ledger
    )
    return agent.run(build_task(task), tools, ExpertAnswer, budget)
