# ADR-0008: stdlib dataclasses + `pydantic.TypeAdapter` at the boundary, no `contracts/` package

- Status: Accepted
- Date: 2026-09-11
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.6; CLAUDE.md "Conventions"

## Context

The framework needs a `domain/` layer with zero infrastructure dependencies (hexagonal architecture:
`domain/` imports nothing outside the standard library), and it needs validated, LLM-output-safe schemas at
the application boundary — every agent draft (ADR-0001) must be checked against a schema before promotion.
A common way to get both is two parallel type systems: plain dataclasses in the domain and separate
pydantic/DTO model classes at the boundary, connected by a mapping layer — which doubles every type
definition and every invariant, and the mapping layer inevitably drifts from the domain types it mirrors.

## Decision

One data model. Domain types are stdlib `@dataclass`es with invariants enforced in `__post_init__`.
`application/schemas.py` wraps those same dataclasses with `pydantic.TypeAdapter` rather than defining
parallel model classes: validation calls the dataclass constructor directly, so `__post_init__` invariants
fire during validation for free, and JSON-schema export walks the real domain types. No parallel
`contracts/`/DTO package, no mappers.

## Consequences

- No mapping code between two type systems that could drift — there's only one type system.
- An invariant is written once, in the domain type, and is enforced identically whether the caller is a unit
  test constructing the dataclass directly or an LLM draft being validated at the boundary. This is what
  makes "never validate invariants at the agent/prompt level" (CLAUDE.md) structurally true, not just a
  convention to remember.
- Round-trip tests (`validate_json(dump_json(x)) == x`) exercise the actual domain type, not a DTO shadow of
  it, so they catch real serialization bugs.
- Domain dataclasses must stay `TypeAdapter`-compatible (careful with `__post_init__` side effects and
  exotic field types) — a mild constraint on otherwise-plain dataclasses, cheaper than maintaining a second
  model family.

## Alternatives considered

- **Separate pydantic `BaseModel` DTOs in a `contracts/` package, mapped to/from domain dataclasses.**
  Rejected: doubles every type definition and every invariant, and the mapping layer is precisely the
  per-layer-DTO ceremony principle 8 (§1) rules out.
