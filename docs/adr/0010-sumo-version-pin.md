# ADR-0010: SUMO 1.27.1 pinned from PyPI, no `SUMO_HOME`

- Status: Accepted
- Date: 2026-09-11
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) top-level "Environment"; CLAUDE.md "Environment & commands"

## Context

SUMO's output (edgedata, tripinfo) is not guaranteed byte-identical across versions, but the Simulation
Runner's reproducibility DoD (E2.1: 20/20 byte-identical runs, same scenario + seed) and the domain
invariant `SimulationResult.sumo_version == SUMO_VERSION` both need one unambiguous ground truth for "the
same simulation". SUMO can be installed via conda-forge, a native OS package, or PyPI (`eclipse-sumo`), and
a stray `SUMO_HOME` left over from another install (e.g. a macOS framework install) can silently shadow the
intended binaries with a different version — a real risk on a contributor's own machine, not a hypothetical.

## Decision

Pin SUMO to exactly **1.27.1**, installed from PyPI (`eclipse-sumo`, `sumolib`, `traci`; `libsumo` optional
via the `fast` extra) as a regular `pyproject.toml` dependency rather than a system or conda-forge install.
`SUMO_HOME` must be unset in the working shell — `sumolib`/`traci` import directly, and the SUMO binaries
resolve from `PATH` via the PyPI package with no environment-variable indirection to get wrong. Every
`SimulationResult.sumo_version` is checked against this constant as a domain invariant at construction, not
just documented as an expectation.

## Consequences

- `pip install -e ".[dev]"` inside the `resto` conda env reproduces the exact SUMO build for any
  contributor or CI runner, with no separate system-level SUMO install step to drift out of sync.
- CI and local dev use the identical mechanism (`sumo --version` check in CLAUDE.md's setup instructions),
  so "works on my machine" version skew is structurally ruled out rather than caught by chance.
- A wrong SUMO version turns from a silent reproducibility bug (different tripinfo numbers with no obvious
  cause) into a hard failure at `SimulationResult` construction.
- The thesis is locked to whatever SUMO 1.27.1 supports and whatever bugs it has; a version bump is a
  deliberate, thesis-wide decision affecting every stored artifact's reproducibility claim, not a routine
  dependency bump. Accepted: reproducibility across the whole evaluation matrix (scenario matrix, learning-
  effect experiment) outweighs early access to upstream SUMO fixes.

## Alternatives considered

- **conda-forge SUMO.** Rejected: mixes install mechanisms with the otherwise PyPI-first Python toolchain
  and makes `SUMO_HOME` handling ambiguous across the two install paths.
- **Track "latest SUMO".** Rejected: directly breaks the byte-identical reproducibility DoD, since there is
  then no fixed point two runs months apart can be compared against.
