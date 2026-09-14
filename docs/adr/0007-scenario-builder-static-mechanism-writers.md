# ADR-0007: Scenario Builder static mechanisms — one writer per mechanism behind `AdditionalFileWriter`

- Status: Accepted
- Date: kept from v0.1/v0.2; tool-exposure changed 2026-09-11 (v0.3)
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.4 (Scenario Builder), §2.5

## Context

Five of six intervention types (`lane_closure`, `edge_closure`, `speed_limit`, `signal_program`,
`demand_scale`; `custom` is the sixth) map to concrete SUMO additional-file mechanisms — rerouter, VSS, TLS
program, TAZ, or a regenerated demand. The mapping needs to be deterministic (identical specs must produce
structurally equivalent files across runs, per the Builder's "authoring determinism" Done criterion, §4.5)
and inspectable — the Builder agent's mechanism choice needs to be visible in its trace, not buried in
hidden dispatch logic.

## Decision

One deterministic writer class per mechanism (`RerouterWriter`, `VssWriter`, `TlsProgramWriter`,
`TazWriter`), each pure code with no LLM involved, behind a single `AdditionalFileWriter` port. Starting in
v0.3, these writers are exposed to the Builder agent as ordinary tools (`write_rerouter`, `write_vss`,
`write_tls_program`, `write_taz`, plus `write_traci_script`/`lint_script`/`dry_run` for the dynamic case)
rather than selected through a dispatch table the agent doesn't see — the agent's tool call *is* its
documented mechanism choice per §2.5's intervention → mechanism table. Specs the Builder cannot implement
with any writer or script go into `rejected[]` with a stated reason, never a silent best-effort file.

## Consequences

- Mechanism selection is auditable directly from the agent's tool-call trace, which is what the Builder DoD
  needs to check "mechanism selection 100 % of specs" and "authoring determinism" (§4.5) without inspecting
  file contents by hand.
- The writers themselves are unit-testable with no LLM in the loop, since they're plain deterministic code
  behind a port — the same testing property ADR-0001 gives the agents applies here to the tools they call.
- `rejected[]` is structured data with a reason, not something that has to be parsed out of agent prose.
- Every new mechanism needs both a new writer and a new tool registration — a two-step addition versus a
  single dispatch-table entry. Accepted: it's the same discoverability trade-off ADR-0003 makes for the
  network-tool catalogue, and for the same reason (the agent's choice must be visible, not implicit).

## Alternatives considered

- **A hidden dispatch table keyed only on intervention type, invisible to the agent.** Rejected: removes the
  Builder's genuine judgment call (window vs. condition, whether `custom` needs a script) and makes the
  trace show a decision the agent didn't actually visibly make — undermining the "specialist decides how"
  principle in §2.2.
