"""Executor (ADR-0023, ADR-0025, ADR-0026, ADR-0027): user text -> a closed `Study`, by
deterministic code. It decides nothing about the domain: agents decide, promoters
certify, the `Study` makes its own transitions, this module chains them.

    Study (at the request) -> parse -> [plan -> validate -> execute steps -> ask the Expert]*
    -> notes -> report

- **Agents** are reached through their ports (`application/ports/agents/`), their drafts promoted
  by the promoters (`application/promoters/`; network, demand and reroute pending until E6.1 and
  E7.1); both are bound in the composition root (`interface/dependencies.py`).
- **Persistence.** Every change (a step, a new phase, a network added, the note ids) is a
  transition of the `Study` (ADR-0041 §4), which returns the next `Study` and the domain events it
  produced, so the domain decides each state and its invariants check every one. `StudyRecorder`
  is the only writer: it stores the new study, then publishes its events on the event bus
  (`resto.application.event_bus`), whose handlers are the trace and note verification
  (`resto.application.event_handlers`).
  Telemetry (`ModelCall`, `NoteWriterFailed`) goes straight to the `Tracer` port.
- **Spend.** `StudySpend` starts at zero, counts tokens, agent calls (the Input Parser's included)
  and simulations, and checks the `StudyBudget` before each agent call and each batch of new
  simulations.
- **Failures.** The first failure becomes a failed `StepRecord` with a `StepError` (ADR-0025 §3,
  classified in `failures`), the pending plan steps are recorded as skipped and the study is
  `failed` - all in one state. No re-ask: the only retry is inside `ToolAgent`.
- **Guards in code.** No re-run of an existing ok `result_id` (checked before the Runner), no
  Builder call for a scenario already stored under the requested id, a per-`Study` budget
  (`StudyBudget`) checked before every agent call and simulation, `max_rounds` with the last round
  forced (ADR-0025 §4).
- **Notes** (ADR-0026) are written once, after the final round; a failing note writer is traced and
  never fails the study. Unverified notes are checked against every *new* ok result only, once
  the study recorded the run step (`NoteVerificationHandler`, a bus handler: its failure is traced
  and never fails the study either).
"""

from resto.application.executor.deps import (
    StudyAgents,
    StudyBudget,
    StudyDeps,
    StudySettings,
)
from resto.application.executor.executor import execute_study

__all__ = [
    "StudyAgents",
    "StudyBudget",
    "StudyDeps",
    "StudySettings",
    "execute_study",
]
