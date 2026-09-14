# ADR-0006: `Demand` as an aggregate with a calibration loop against control-edge counts

- Status: Accepted
- Date: 2026-09-11
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.3, §2.4 (Demand Generator)

## Context

Demand (trip generation) previously had no first-class identity or store. Without one, "the same demand"
profile reused across DEV-NET/REAL-NET runs couldn't be deduped or referenced via `derived_from`, and
calibration against real traffic counts had nowhere to record its evidence — a real gap given principle 7
("every answer carries evidence").

## Decision

`Demand` is an aggregate: trips (origin, destination, departure) plus routes computed for one specific
network, id = `content_hash(trips)` (ADR-0002). Sources are explicit parameters, `historical_demand` (an
optional DatabaseMCP capability), or an external dataset found on the web and **frozen as an artifact**
(`ExternalDataset(url, snapshot, transformation)` — a changed URL must not change the demand). When only
aggregate counts at control edges are available, the Demand Generator calibrates: generate abundant
candidate routes (`randomTrips` + `duarouter`) → `routeSampler --edgedata-files counts` → simulate a short,
ephemeral calibration scenario via `run_simulation` → measure at the control edges → adjust (scale,
`--optimize`, more candidates) → repeat, at most `max_calibration_rounds` (5). Calibration runs never enter
the results store; the last one leaves its edgedata as `Fidelity.evidence`.
`reroute_demand(demand, network)` is **deterministic code, not an agent call**: same trips, new routes for a
new network, `derived_from` set — this is what keeps GP-11 ("add an edge") fair, since baseline and
treatment then differ only in the network, not in independently re-sampled demand.

## Consequences

- `demands` becomes a required DatabaseMCP capability, giving `Demand` the same lookup/reuse story as
  `Network`.
- Calibration evidence (`Fidelity.evidence`) is always the edgedata of an actual simulation run, so a
  fidelity claim is traceable per principle 7 by construction, not by convention.
- `reroute_demand` being deterministic rather than agent-driven removes demand-generation variance as a
  confound in any baseline-vs-treatment comparison that changes only the network.
- Calibration is bounded (`max_calibration_rounds = 5`); a demand spec that genuinely needs more rounds to
  converge reports whatever fidelity it reached at the bound rather than looping indefinitely — the ±15 %
  (DEV-NET) / ±25 % (REAL-NET) thresholds in §4.4 are calibrated against this bound, not around it.

## Alternatives considered

- **Model `Demand` as a value object owned by `Scenario`.** Rejected: prevents reuse of the same demand
  across multiple scenarios/networks and gives `reroute_demand` nothing stable to derive from.
- **Unbounded calibration.** Rejected: an agent-adjacent loop with no termination guarantee conflicts with
  principle 1's evaluation-first, budget-aware design.
