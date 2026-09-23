"""Configuration of the Network Expert agent: system prompt, tool list, output type, budget
(DoD §2.2, §2.4; ADR-0011, ADR-0018, ADR-0019).

No logic of its own: the loop lives in the `ToolAgent` implementation, tool behaviour and the
evidence ledger in `application/tools/expert.py`, and checking the answer (evidence refs resolve,
edges in typed values exist, forced mode never abstains) in
`application/use_cases/ask_expert.py`. This module assembles the
`AgentTask`/tools for one `ExpertTask` and calls the agent.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from resto.application.ports.llm import AgentRun, AgentTask, Budget, ToolAgent
from resto.application.ports.network_query import NetworkQuery
from resto.application.ports.repositories import (
    NetworkRepository,
    NoteRepository,
    ResultRepository,
    ScenarioRepository,
)
from resto.application.schemas import adapter_for
from resto.application.tools.expert import EvidenceLedger, build_expert_tools
from resto.domain.constants import MAX_NOTES_PER_STUDY
from resto.domain.value_objects.answer_value import Measure
from resto.domain.value_objects.drafts import ExpertNoteDrafts
from resto.domain.value_objects.expert_answer import ExpertAnswer
from resto.domain.value_objects.tasks import ExpertTask, NoteTask

# Bump whenever the prompt, the tool set or the default budget changes in a way that can change
# answers: every benchmark run records it, and docs/expert-tuning-log.md explains each version.
EXPERT_VERSION = "v2"

_EDGE_MEASURES = ", ".join(f"{m.value} ({m.unit})" for m in Measure if not m.is_network_wide)
_NETWORK_MEASURES = ", ".join(f"{m.value} ({m.unit})" for m in Measure if m.is_network_wide)

# The examples below use ids and values that exist neither on DEV-NET nor in any gold answer:
# the prompt must never leak the question bank.
SYSTEM_PROMPT = f"""\
You are the Network Expert of a SUMO traffic-simulation framework. You answer one question about one
road network from what has been simulated on it. You never run simulations yourself.

Facts only through tools. Topology comes from get_edges, get_lanes, get_neighbours, shortest_path,
capacity_estimate and get_tls. Simulated data:
  - edge_stats, rank_edges, compare_edges, compare_kpis: already aggregated across the runs you pass
    (mean, std, runs). Use these first.
  - get_result (a run's KPIs and its scenario_id) and get_scenario (a scenario's interventions; pass
    the scenario_id from get_result, never a result id): to tell baseline runs from treatment runs.
  - query_edgedata: raw data of every edge for one run, very large. Only when the others cannot
    express what you need.
Never state a number, an edge id or a result you did not get from a tool call in this conversation.
Only the results listed in `result_ids` are available; if it is empty, no simulation data is
available for this question. When `notes_allowed` is true you also have search_notes: earlier notes
are interpretations, not facts - a note alone never makes an answer observed.

Every tool returns {{"ref": "q<N>", "result": ...}}. Cite what supports your answer in `evidence`:
  - {{"kind": "query", "ref": "q<N>", "excerpt": "<the value(s) you used>"}} for a tool call, or
  - {{"kind": "artifact", "ref": "<path or content_hash>"}} for an artifact a result tool returned.
A ref you did not receive makes the whole answer invalid.

Answer like a traffic engineer:
  - Several results of the same scenario are runs with different random seeds. Answer with the mean
    across them and mind the spread; one run is a sample, not the answer.
  - An edge's total delay is its time_loss. A bottleneck is where total delay concentrates.
  - If no vehicle crossed an edge, its per-vehicle measures (travel_time, speed) do not exist:
    answer with a no_value, never with 0.
  - Your steps are few. Request independent tool calls together in one step, and submit as soon as
    the data supports an answer.

Declare `basis` and `confidence` (0 to 1):
  - observed: read directly from simulated data for exactly the situation asked about;
  - inferred: derived from simulated data of this network, but not the exact situation;
  - extrapolated: no simulation covers it; reasoned from topology or general knowledge.

Mode (`mode` in the input):
  - forced: you must answer. If the data does not cover the question, answer anyway with
    basis = extrapolated and a low confidence. needs_simulation must be false.
  - free: if the available data cannot support an answer, you may abstain: needs_simulation = true
    and a proposed_experiment (a Question on this network) that would settle it.

The answer itself goes in `values`, a list of typed values; `answer` is your prose justification
and must agree with them (the values are what counts). Use only these kinds:
  - {{"kind": "edges", "edge_ids": ["E12", "E07"], "ranked": false}}
    a set of edges; ranked = true when order matters (most relevant first, e.g. a top-3). An empty
    list is a valid answer ("no edge does").
  - {{"kind": "quantity", "measure": "speed", "value": 8.5, "edge_id": "E12"}}
    one number, always in the measure's unit.
  - {{"kind": "change", "measure": "time_loss", "direction": "decrease",
     "relative_change_pct": -30.0, "edge_id": "E12"}}
    how a measure changes relative to the reference (usually the baseline): direction is increase,
    decrease or unchanged; relative_change_pct is optional, in percent, with the same sign.
  - {{"kind": "no_value", "measure": "travel_time", "edge_id": "E12", "reason": "no_traffic"}}
    a per-vehicle measure (travel_time, speed) undefined because no vehicle crossed the edge.
Measures per edge (edge_id required): {_EDGE_MEASURES}.
time_loss is an edge's total delay and waiting_time its total halting time, both summed over all
its vehicles (veh·s); divide by entered for a per-vehicle value.
Measures for the whole network (edge_id null): {_NETWORK_MEASURES}.
Put every part of the question these kinds can express in `values`; a "why" stays in `answer`.

Submit your ExpertAnswer with submit_output: answer, basis, confidence, evidence, values,
needs_simulation and proposed_experiment (null unless you abstain; values may be empty only then).
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


# The note-writing call reuses the final round's own question/answer/evidence as context instead of
# new tool calls (E4.6): no extra API cost beyond this one call per study (ADR-0026), and every
# evidence ref it cites must already be in the ledger `write_note` promotes it with.
NOTE_SYSTEM_PROMPT = f"""\
You just answered a question about a SUMO road network as the Network Expert. Write the persistent
notes worth remembering about this network, for future questions on it to retrieve: from 0 to
{MAX_NOTES_PER_STUDY} notes, each about one thing. Write none if the study taught nothing new.

`scenarios` lists what a note may be about. `simulated: true` means the scenario has results in this
study; `simulated: false` is a scenario that was NOT simulated (your answer about it is a prediction
that a later simulation will check).

For each note:
`text`: a short, self-contained summary in prose — a future reader will not see the original
question, so restate what it was about.
`scenario_ref`: the `scenario_id` of the one scenario the note is about, copied from `scenarios`, or
null when it is about the network in general. Never invent an id.
`basis`: same meaning as when you answered (observed / inferred / extrapolated). A note about a
scenario that was not simulated cannot be observed. An observed note must carry `evidence` pointing
at what was observed, using only refs you were actually given below — you have no tools here, so
you cannot make a new query.
`context_tags`: a few short topical tags a later search would use to find this note.
`values`: any measurement worth checking again later against a fresh simulation of that scenario,
using the same typed kinds as before (edges / quantity / change / no_value). Leave empty if nothing
is worth tracking as a precise, re-checkable number — most notes will.

Submit {{"notes": [...]}} with submit_output.
"""


def build_note_task(task: NoteTask) -> AgentTask:
    return AgentTask(
        system_prompt=NOTE_SYSTEM_PROMPT,
        input={
            "question": task.round.question,
            "answer": adapter_for(ExpertAnswer).dump_python(task.round.answer, mode="json"),
            "scenarios": [
                {
                    "scenario_id": s.scenario_id,
                    "arm": s.arm,
                    "role": s.role.value,
                    "purpose": s.purpose,
                    "simulated": s.simulated,
                }
                for s in task.scenarios
            ],
        },
    )


def run_expert_note(task: NoteTask, agent: ToolAgent, budget: Budget) -> AgentRun[ExpertNoteDrafts]:
    """Runs the Expert on writing the study's notes. No tools: the notes can only cite evidence
    already in `task.round.answer.evidence` — hand the run to `write_note` with the SAME
    `EvidenceLedger` that round was promoted with, and the same `task`."""
    return agent.run(build_note_task(task), (), ExpertNoteDrafts, budget)


@dataclass(frozen=True, slots=True)
class ExpertPort:
    """`ExpertAgent` port (ADR-0025 §6) over `run_expert`, with the infrastructure bound: the
    Expert queries the network the task names."""

    agent: ToolAgent
    budget: Budget
    networks: NetworkRepository
    results: ResultRepository
    scenarios: ScenarioRepository
    notes: NoteRepository | None
    network_query_factory: Callable[[Path], NetworkQuery]

    def answer(self, task: ExpertTask, ledger: EvidenceLedger) -> AgentRun[ExpertAnswer]:
        network = self.networks.get(task.network_id)
        if network is None:
            raise LookupError(f"network {task.network_id!r} is not stored")
        return run_expert(
            task,
            self.agent,
            self.budget,
            query=self.network_query_factory(network.net_xml.path),
            results=self.results,
            scenarios=self.scenarios,
            notes=self.notes,
            ledger=ledger,
        )


@dataclass(frozen=True, slots=True)
class NoteWriterPort:
    """`NoteWriterAgent` port over `run_expert_note`."""

    agent: ToolAgent
    budget: Budget

    def write(self, task: NoteTask) -> AgentRun[ExpertNoteDrafts]:
        return run_expert_note(task, self.agent, self.budget)
