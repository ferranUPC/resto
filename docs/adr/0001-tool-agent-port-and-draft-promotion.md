# ADR-0001: Single `ToolAgent` port; agents return drafts, promotion is code

- Status: Accepted
- Date: 2026-09-11
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §1 (principles 3–4), §2.2

## Context

Six functional modules (Coordinator, Network Author, Demand Generator, Scenario Builder, Network Expert,
Output Composer) each use an LLM to author something — a plan, a network recipe, trips, a scenario, an
answer, a report. Only the Simulation Runner is plain deterministic code. Without a shared abstraction,
each module risks its own bespoke LLM-calling code, its own ad hoc mocking strategy for tests, and — more
seriously — its own judgment call about whether it's safe to let the LLM assign identity, status, or
provenance to what it produces, which would make reproducibility (principle 5/6) a per-module accident
instead of a structural guarantee.

## Decision

Define one `Protocol`:

```python
class ToolAgent(Protocol):
    def run(self, task: AgentTask, tools: Sequence[Tool], output: type[T], budget: Budget) -> AgentRun[T]: ...
```

Every authoring module is *configuration* over this one port, not a distinct abstraction: a typed `task`
(what the Coordinator sends), a tool list, an expected `output` draft type. One real implementation (the
Anthropic client) and one fake implementation are shared by all six agents in tests. An agent's `output` is
always a typed **draft** — data plus artifact references plus a `rationale` string — never an id, a hash, a
`status`, or `provenance`. Promotion (draft → domain entity) is always deterministic code in `application/`,
in a fixed order: (1) syntactic validation via `TypeAdapter(Draft)`, (2) semantic validation against
referenced state, (3) deterministic construction (id from content/request hash), (4) persistence + tracing.

## Consequences

- One shared test fake replaces six bespoke ones; every agent module is tested the same way.
- Content-hash and request-hash identity (ADR-0002) stays trustworthy even though an LLM is in the write
  path, because the LLM never assigns the hash — it can only be wrong about the *content*, which is exactly
  what semantic validation and simulation (principle 6) check.
- Budget, tool-call tracing, and retry-on-validation-failure are implemented once, at the port, instead of
  once per agent.
- Every module is constrained to the same task-in/draft-out interaction shape even where a module's natural
  interaction pattern differs (the Coordinator is closer to an orchestrator calling other use cases as tools
  than a single-shot author). Accepted: the Coordinator's own outputs (`Question` + `StudyPlan`, then
  `StudyOutcome`) still fit the draft shape, and a second port for one module would break the "one shared
  test fake" property this ADR exists for.

## Alternatives considered

- **Per-agent bespoke interfaces.** Rejected: no shared test fake, and tool-budget/tracing logic would be
  duplicated six times with six chances to diverge.
- **Agents writing directly to repositories/domain entities.** Rejected: violates principle 4 outright and
  makes identity (ADR-0002) and replay determinism (ADR-0003, ADR-0006) unenforceable — there would be
  nothing stopping an agent from minting its own id or silently overwriting `status`.
