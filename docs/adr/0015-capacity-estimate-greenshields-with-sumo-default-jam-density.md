# ADR-0015: `capacity_estimate` uses a Greenshields estimate with a jam density derived from SUMO's default vehicle length/minGap

- Status: Accepted
- Date: 2026-09-14
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §4.9 (NetworkMCP); work-plan E1.1

## Context

`NetworkQuery.capacity_estimate(edge_id)` (`application/ports/network_query.py`) must return a
veh/h capacity figure for an edge. `sumolib` does not compute this — it only exposes raw
attributes (`getLaneNumber()`, `getSpeed()`). There is no per-network, per-edge measured capacity
to read; it has to be estimated from the free-flow speed and lane count alone, since at NetworkMCP
query time no `Demand` (and therefore no vehicle types) is necessarily loaded yet.

## Decision

`adapters/sumo/netxml.py::SumolibNetworkQuery.capacity_estimate` uses the Greenshields
fundamental-diagram result `q_max = v_free · k_jam / 4` (max flow, attained at `v = v_free / 2`),
per lane, summed over the edge's lane count. `k_jam` (jam density, veh/km/lane) is **not** an
independently chosen constant — it is derived from SUMO's own documented default vehicle
attributes: default vehicle length **5.0 m** + default `minGap` **2.5 m** ⇒ one vehicle every
7.5 m at jam density ⇒ `k_jam = 1000 / 7.5 ≈ 133.3` veh/km/lane. The two source numbers (5.0,
2.5) are named constants in the module, not inlined into the formula.

## Consequences

- **This is a rough estimate, not a measurement.** It assumes every vehicle on the edge has
  SUMO's default `length`/`minGap`. Any `Demand`/`vType` that overrides either (larger trucks,
  tighter `minGap` for aggressive driving, pedestrian/bike lanes with a different physical
  footprint) makes the real capacity diverge from this number without `capacity_estimate` ever
  knowing — it has no visibility into `Demand` at all.
- **It silently goes stale if SUMO changes its defaults.** SUMO 1.27.1 is pinned
  (ADR-0010), so this is currently frozen, but a future SUMO version bump is exactly the moment
  this needs re-checking: if the upstream default `length` or `minGap` changes,
  `_JAM_DENSITY_VEH_PER_KM` in `netxml.py` must be re-derived by hand — nothing fails loudly on
  its own, since sumolib does not expose these defaults as an importable constant to assert
  against (confirmed while implementing this adapter — no such value exists in `sumolib`'s public
  API as of 1.27.1).
- Treat any number this method returns as an order-of-magnitude planning figure (e.g. "is this
  edge plausibly congested"), never as ground truth fed into a metric that is scored/evaluated
  numerically (DoD §4.9's "magnitude band" thresholds etc. must come from simulated results, not
  from this estimate).
- **Watch-for trigger**: revisit `_JAM_DENSITY_VEH_PER_KM` whenever `SUMO_VERSION`
  (`domain/constants.py`) changes, and whenever a `capacity_estimate` value looks implausible
  against a simulated edge's actual measured throughput (`edgedata`) during E1.6's latency/sanity
  pass or later evaluation work.

## Alternatives considered

- **HCM base saturation flow tables** (e.g. ~1900 pc/h/lane for freeway, lower for signalised
  urban). Rejected for now: more "standard" in traffic engineering but just as arbitrary here —
  picking one HCM facility class per edge needs classification data (`edge.getType()` /
  `getPriority()` alone are not a reliable proxy) that DEV-NET/REAL-NET don't consistently carry
  yet, and it would still need the same kind of written caveat.
- **Flat constant capacity per lane** (e.g. 1800 veh/h/lane regardless of speed). Rejected:
  ignores `edge.getSpeed()` entirely, which is the one piece of real per-edge information
  `sumolib` does give us for free.
- **Read capacity from actual simulated throughput instead of estimating it.** Not available at
  NetworkMCP's query time by construction (§2.1: NetworkMCP is a read-only query over a
  `.net.xml`, it never runs a simulation) — this is what `SimulationResult`/`query_edgedata`
  are for, and is not a substitute for a Network-level tool.
