# ADR-0005: `resto.traci_api` scripts as the single dynamic mechanism

- Status: Accepted
- Date: 2026-09-11
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.4 (Scenario Builder, Simulation Runner, TraciMCP)

## Context

The pre-v0.3 design had a declarative `TraciPlan` and an interpreter for anything the static additional-file
mechanisms (ADR-0007) couldn't express. It duplicated a surface a plain Python API against TraCI already
offers, was awkward to keep expressive as new intervention shapes appeared (runtime `condition`, `custom`),
and every new declarative feature meant a new interpreter case to write and trust.

## Decision

Drop `TraciPlan` and its interpreter. Dynamic interventions are ordinary Python scripts, authored by the
Scenario Builder, against a small primitive API in `resto.traci_api`: low-level primitives (`close_lane`,
`open_lane`, `set_speed`, `set_tls_program`, `get_edge_occupancy`, `get_edge_speed`, `get_vehicle_count`,
`step`) plus two declarative registration helpers the API itself provides, `at_time(t, action)` and
`when(condition, action)`. A script that only calls `at_time`/`when` *is* the old plan, expressed through the
same typed primitives instead of a bespoke interpreter; `Intervention` gains a `custom` type as the
escape hatch for scripts that need more than the two helpers. Every primitive call logs to `applied_actions`
with an `origin` (`rule` for `at_time`/`when`-registered actions, `code` for free Python). Scripts are
AST-linted before execution (only `resto.traci_api` imports allowed), dry-run, then executed in a sandboxed
subprocess with the run's seed; a script that fails lint is rejected before SUMO starts, a script that
crashes marks the run failed with its traceback.

## Consequences

- One mechanism instead of two: the "common case" (`at_time`/`when`) and the escape hatch (`custom`, free
  Python) are the same code path, not a declarative interpreter plus a separate bypass around it.
- `applied_actions` gives a uniform audit trail regardless of whether an action came from a registered rule
  or free code, so effect-verification (E2.4) and the Runner's Done criteria (§4.6) don't need to
  special-case which.
- Safety properties the interpreter provided (bounded, inspectable side effects) now come from lint +
  dry-run + sandbox instead of from the mechanism being structurally unable to do more — a deliberate trade,
  since `custom` exists precisely to allow more.
- TraciMCP (Stretch) exposes the exact same primitives over MCP for a live agent, with no separate
  declarative surface to keep in sync.

## Alternatives considered

- **Keep `TraciPlan` for the declarative majority, free scripts only for `custom`.** Rejected: two
  mechanisms with overlapping jobs — as `condition`-based interventions grew, the interpreter kept needing
  to grow toward what the script API already offered, doubling the surface under test for no expressive gain.
