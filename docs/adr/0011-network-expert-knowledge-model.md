# ADR-0011: Network Expert knowledge model — facts via tools, opinions via `ExpertNote` RAG

- Status: Accepted
- Date: kept from v0.1/v0.2, unchanged through v1.0
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.4 (Network Expert), §4.7

## Context

The Network Expert is the thesis's research focus and must never answer from an LLM's unstated prior —
every claim needs to be checkable against something the framework actually knows (principle 6, "simulation
is ground truth"; principle 7, "every answer carries evidence"). But part of an expert's value is
accumulated interpretation across experiments ("this corridor tends to reroute a particular way when closed
at peak") — a claim that outlives any single question and isn't something a single tool call returns.

## Decision

Split expert knowledge into two kinds with different provenance rules. **Facts** — topology, edgedata, KPIs
— are retrieved only through tools (`get_edge`, `get_lanes`, `get_neighbours`, `shortest_path`,
`capacity_estimate`, `get_tls` via NetworkMCP; `query_edgedata`, `get_result`, `list_results` via
DatabaseMCP); the Expert never states a factual number from memory, and every answer's `evidence[]` must
resolve to an artifact or a query call visible in the trace. **Opinions** — interpretive claims meant to
persist — are written as `ExpertNote`s: prose with `provenance`, `basis` (observed / inferred /
extrapolated), and a verification `status` that changes only because of a later `SimulationResult`, never
because the agent revises its own opinion unprompted. Notes are retrieved via `search_notes` in later
questions (RAG), scoped by `context_tags` structured in `Scenario`.

## Consequences

- The §4.7 Done criterion "every fact in an answer must come from a tool call visible in the agent trace" is
  directly checkable — facts and opinions never share a code path, so a number in an answer either traces to
  a tool call or it doesn't.
- `ExpertNote.status` changing only via simulation is what makes the learning-effect experiment (E4.9: notes
  at store sizes 0/5/15/25 with confidence intervals) measure accumulated *verified* knowledge, not
  accumulated agent confidence — a note the Expert "still believes" but that a later run contradicted is
  visibly stale, not silently rewritten.
- `basis` gives a principled way to answer in `forced` mode (must answer; `basis = extrapolated` is an
  honest label) versus abstaining in `free` mode (`needs_simulation` + `proposed_experiment`).
- Two knowledge paths (tool-verified facts vs. note-based opinions) is more machinery than a single
  RAG-over-everything design. Accepted: facts and interpretations have genuinely different trust and
  verification lifecycles, and conflating them would make every evidence claim unfalsifiable — exactly what
  principle 7 exists to prevent.

## Alternatives considered

- **A single RAG store over both facts and interpretations.** Rejected: a stale or wrong "fact" retrieved
  from a note would be indistinguishable from a tool-verified one, defeating the evidence guarantee.
- **No persistent notes; re-derive everything per question.** Rejected: makes the learning-effect experiment
  — a thesis result — impossible to run, since there would be nothing to accumulate across store sizes.
