# ADR-0033: A tool is declared once; schema and binding are derived

- Status: Accepted (2026-09-29) — refines ADR-0018 and ADR-0022 (tool sets); does not change ADR-0007
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.2;
  work-plan E5.2, E2.6, E6.1, E6.2, E5.3

## Context

Adding or changing one parameter of an Expert tool means five edits: the name tuple, the prompt prose, the
`_SCHEMAS` entry, the binding lambda that repeats parameters and defaults, and the function. About twenty
tools arrive in the next weeks (E5.2, E2.6, E6.1, E6.2), and E5.3 adds `network_id` to every topology tool.
Builder collaborators have the same problem: each mechanism adds a keyword argument across the tool, the agent
and `main.py`.

## Decision

- **One declaration per tool.** A decorator gives the name and an explicit `description=`; the input schema
  is derived from the function's annotations with pydantic. Parameters the model must not see (a
  `NetworkQuery`, repositories) arrive through a first `ctx` parameter and are left out of the schema. The
  description is explicit, not the docstring, because it changes model behaviour and is versioned with the
  agent (`EXPERT_VERSION`).
- **Collaborators as one value.** Each agent's collaborators are grouped in a single dataclass passed from the
  composition root, instead of one keyword argument per collaborator.
- **Guidance lives with the tool.** Once the migration is done, per-tool advice moves from the system prompt
  into descriptions, and the prompt keeps only rules that span tools. That change comes second, after the
  neutral migration, with its own development run and an `EXPERT_VERSION` bump, so a regression can be
  blamed on the text and not on the refactor.
- All existing tools (Expert, network, Builder) migrate; the tool set the model sees does not change.

## Consequences

- ADR-0007 still holds: this changes how a tool is declared, adds no dispatch table, and the choice of
  mechanism stays visible in the trace of tool calls.
- The cross-tool parts of the prompt stay hand-written.
