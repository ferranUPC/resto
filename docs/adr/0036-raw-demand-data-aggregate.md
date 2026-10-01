# ADR-0036: Raw demand data is an aggregate with one envelope and a content per kind; the Demand Generator discovers it through `raw_demand_data`

- Status: Accepted (2026-10-01, grilling on demand data). Replaces the `historical_demand` capability of the
  DatabaseMCP contract (§5.6, §10 point 3), the `HistoricalDbSource` variant of `DemandSource`, and the
  "historical data only with the `historical_demand` capability" line of ADR-0035 point 3. Adds a seventh
  aggregate to the six of the frozen architecture body. Built by E6.8, E6.9, E6.10 and E6.11
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.3 (`Demand`,
  `DemandSource`), §4.3 to §4.4; [ADR-0006](0006-demand-as-aggregate-with-calibration-loop.md),
  [ADR-0028](0028-time-windows-are-time-of-day.md), [ADR-0034](0034-database-protocol-and-backends.md),
  [ADR-0035](0035-described-demand-no-default.md); [`DATABASE_MCP_CONTRACT.md`](../DATABASE_MCP_CONTRACT.md)
  §5.6, §10; work-plan E5.6, E6.5, E6.8 to E6.11

## Context

ADR-0035 left measured data behind an optional `historical_demand` capability and listed what it did not
settle: a user sending demand data, fetching external data, and a catalogue of demands over days and events.
The capability as written cannot carry what the Demand Generator will need:

- `get_historical_demand(network_id, day_type, hour)` returns one number per edge. It has no detector, no
  real date, no interval length, and no room for a measurement over a whole road or for an origin-destination
  matrix.
- `CONTEXT.md` already defines **Traffic counts** as per detector and interval, which the contract
  contradicted.
- A "typical Monday" is not data. It is computed from measured days, so a stored `day_type` mixes
  measurement with an aggregation someone else chose.
- `HistoricalDbSource` stores only a `query`. If the backend's data changes, the same `Demand.id` stands for
  trips that no longer reproduce.
- A client may have counts, flows, an OD matrix, or nothing. The framework cannot assume which.

## Decision

1. **`RawDemandData` is an aggregate**, the seventh. Its id is the content hash, like `Network` and `Demand`,
   because what is imported is what identifies it. It holds `network_id` (an id, never the network),
   a `description` (free text, required), a `provenance` (where it came from), and one `content`. Several
   `Demand`s can be built from the same `RawDemandData`; it exists before any demand does.
2. **One envelope, one content per kind.** `content` is a discriminated union of small dataclasses
   (the repo's convention for variants), not a class hierarchy. Kinds that exist now: `counts` (a
   measurement at one point, per detector) and `od_matrix`. `flows` (a measurement aggregated over a whole
   edge) is E6.11. Data a third party already aggregated ("average weekday") is a kind of its own, added
   when a real case needs it. Adding a kind is one dataclass, one entry in the generator's registry and
   one line in the contract. Composition over inheritance is a bet recorded here, cheap to revisit while
   nothing is built.
3. **`ObservationInterval`: a start and an end, both datetimes with a time zone.** One instant has one
   writing and an interval may cross midnight. Naive datetimes are rejected in `__post_init__`. There is no
   day type and no typical day in raw data. The content has a time axis (a tuple of intervals, ordered and
   without overlap) and its observations hold values aligned with it, `None` where there is no measurement.
   A length mismatch is a `ValueError`.
4. **Time of day stays where ADR-0028 put it.** Simulations and `Demand` keep running on the day's clock.
   The Demand Generator converts a dated interval to seconds since midnight, in one place, when it builds a
   `Demand`. A "typical Monday" is computed there from the measured Mondays it selects.
5. **`ZoneMap` travels with each OD matrix.** One network can have several matrices with different zones.
   A zone is a set of edges, each with a role: `source` (trips leave from it), `sink` (trips arrive at
   it) or `both`. An imported SUMO TAZ file with plain `edges=` maps every edge to `both`. Per-edge weights
   are left out until a case needs them. The importer rejects a matrix when a zone or cell names an edge
   that is not in the network, a cell cites an undefined zone, a zone used as an origin has no `source` or
   `both` edge, or a zone used as a destination has no `sink` or `both` edge.
6. **Raw demand data is bound to one network** by `network_id`. The importer checks every detector and edge
   id against that network and rejects what does not match.
7. **The capability becomes `raw_demand_data`, replacing `historical_demand`.** It is an optional group,
   outside the `Database` protocol of ADR-0034 (a backend without it still satisfies the minimum contract
   and GP-10). Reading: `list_demand_data(network_id, window?)` returns, for each item, its id, kind,
   description, source and the ranges it covers and its gaps, with no values; `get_demand_data(id, intervals)`
   returns only the intervals asked for. Writing is a separate optional group, `store_demand_data`. A
   backend may offer reading without writing. When there is no data, the list is empty; an absent group
   reads the same.
8. **The contract defines the kinds.** A backend offers only kinds the contract defines, so a client with
   flows data does not expose it before E6.11. A kind the generator does not know (a backend ahead of the
   framework's version) is ignored and noted in the draft's `rationale`.
9. **The Demand Generator discovers, it does not assume.** It calls `list_demand_data`, sees what exists,
   and picks a path per kind through a registry: counts calibrate with `routeSampler` (ADR-0006), an OD
   matrix is turned into trips by a path E6.9 designs. It may use one source or several. Which to prefer or
   whether to mix them is its decision, or the user's, not a rule of the contract. For a typical day it reads
   the coverage, selects the dates that match (the Mondays of a month), and requests those.
10. **`RawDataSource` replaces `HistoricalDbSource`.** It records the `RawDemandData.id` and the intervals
    used. The id is a content hash, so no snapshot is stored beside it; the rule that data from outside
    is frozen stays one rule, and `ExternalDatasetSource` keeps its own snapshot.
11. **Plan checks use the list.** `plan_validation` rejects a step that needs a kind of data, for a
    network, that `list_demand_data` does not return. `has_historical_demand` goes away.

## Left open

- A day with a clock change (23 or 25 hours): an interval measures what it measures, and the generator's
  conversion to time of day takes it as it is.
- Whether a demand zone and the `taz` of the Scenario Builder (`InterventionTarget`, a writer with no code)
  share a definition. They are separate today; decide it when the Scenario Builder needs zones.
- The importer (E6.10): input formats (a CSV per kind, plus a SUMO TAZ file for OD) and importing the
  same content with another description, which will be a conflict as it is for `Demand` in ADR-0035.
- `flows` (E6.11) and the pre-aggregated kind.
- How the Generator turns an OD matrix into trips (`od2trips` and `duarouter`, or another route): E6.9.

## Consequences

- Domain: `RawDemandData`, `ObservationInterval`, the content dataclasses, `ZoneMap`; schemas follow.
  `DemandSource` gets `RawDataSource` in place of `HistoricalDbSource`.
- Contract: §5.6 and §10 point 3 are replaced by this group; the GP-10 row that reads "`historical_demand`
  is missing" becomes "no raw demand data of the needed kind". The frozen architecture body is not edited;
  this ADR supersedes its aggregate count and its GP-10 row.
- ADR-0035 point 3 and its "left to a separate task" entry for a user sending demand data are superseded
  by E6.10; fetching external data stays with the Demand Generator. ADR-0006's mention of
  `historical_demand` as a source is replaced by this decision; the calibration loop is unchanged.
- E5.6 negotiates `raw_demand_data` and checks `list_demand_data`. E6.5 no longer includes the synthetic
  `historical_demand`; E6.8 and E6.9 take it.
- `CONTEXT.md` gains **Raw demand data**, **Observation interval**, **Traffic flows**, **OD matrix** and
  **Zone map**; **Traffic counts** and **Demand** are reworded.

## Alternatives considered

- **A class hierarchy** (an abstract base with one subclass per kind). Rejected for now: the three kinds
  share an envelope, not behaviour, and the repo already types variants as unions that `TypeAdapter` validates
  and `match` covers exhaustively. A shared behaviour can be added as a `Protocol` later.
- **Two interval variants, dated and typical** (`DatedInterval`, a day type plus time of day). Rejected: a
  typical day is computed, not measured, and a second variant would let aggregations enter as if measured.
- **Keep counts with a day type and an hour.** Rejected: it fixes the aggregation before the generator knows
  what the request needs.
- **Treat flows as counts.** Rejected: a count covers a point, a flow a whole road. Merging them hides what
  was measured.
- **The backend declares its kinds during capability negotiation.** Rejected: the generator can ask what
  data exists, and the list also says what it covers.
- **A sixth repository in `Database`.** Rejected: a backend with no demand data would no longer satisfy the
  minimum contract.
- **A separate ingestion API.** Rejected: `DatabaseMCP` is already the way in; a client with its own
  database implements the contract and sends nothing.
- **The zone as part of `Network`.** Rejected: one network can have several zonings, and `Network.id` is the
  hash of the `.net.xml`.
- **A snapshot artifact for `RawDataSource`.** Rejected: the id is a content hash.
