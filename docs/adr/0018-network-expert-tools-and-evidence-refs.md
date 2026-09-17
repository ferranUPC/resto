# ADR-0018: Network Expert tools — `get_scenario`, result allow-list, evidence refs from a call ledger

- Status: Accepted
- Date: 2026-09-17
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.2 (Network
  Expert tools), §2.4, §4.7; [ADR-0011](0011-network-expert-knowledge-model.md); work-plan E4.1

## Context

Building the Expert on the `ToolAgent` port (E4.1) exposed three gaps in §2.2 and ADR-0011:

1. **No tool reaches a scenario's interventions.** `get_result` returns a `scenario_id`, and nothing in the
   Expert's list turns it into interventions. A counterfactual question cannot be answered without knowing
   which available result is the baseline and which carries the intervention.
2. **"Available `result_ids[]`" had no enforced meaning.** Nothing stopped the Expert from reading any
   stored result, which would make held-out evaluation (E4.9) meaningless.
3. **ADR-0011 requires every `evidence[]` entry to resolve to a query call or artifact visible in the
   trace, but fixes no ref format.** A free-form ref (`"query_edgedata:r1"`) cannot be checked against what
   the agent actually called.

## Decision

- **Add `get_scenario(scenario_id)`** to the Expert's tools: read-only, over `ScenarioRepository` (already a
  DatabaseMCP capability), limited to scenarios that have at least one available result.
- **`ExpertTask.result_ids` is an allow-list.** `get_result` and `query_edgedata` refuse any other id,
  `list_results` filters to it. An empty list means no simulated evidence is available.
- **Evidence refs come from a per-run call ledger.** Every successful Expert tool call is recorded in an
  `EvidenceLedger` (`application/tools/expert.py`) and returned to the agent as
  `{"ref": "q<N>", "result": ...}`. `Evidence(kind=query)` must cite such a ref;
  `Evidence(kind=artifact)` must cite the path or content hash of an artifact a result tool call returned.
  `ask_expert` rejects an answer with any ref the ledger does not hold. Failed calls are not recorded.

## Consequences

- ADR-0011's resolvability rule is enforced in promotion, deterministically, for every answer — not left to
  the prompt or to a later audit.
- The caller must create one ledger per run and pass it to both `run_expert` and `ask_expert`.
- Refs are only meaningful within one run; a stored `ExpertAnswer` keeps `q<N>` refs that point at that
  run's trace, not at global ids.
- The §4.7 check "no number without a matching tool call" still needs the numbers themselves compared to
  ledger results; that is an evaluation concern (E3.3/E4.7), and the ledger is what makes it possible.

## Alternatives considered

- **Put each result's scenario and interventions in the task input.** Rejected: facts would reach the agent
  through the prompt instead of a traceable tool call, against ADR-0011.
- **Check refs against `AgentRun.tool_calls`.** Rejected: that tuple is produced by the `ToolAgent`
  implementation (canned in the fake), while the ledger is filled by the tools themselves, so it records
  exactly what was executed whichever implementation ran.
