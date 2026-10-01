# ADR-0035: A demand is described, never chosen by default; the Coordinator asks when it cannot find or obtain one

- Status: Accepted (2026-09-30, E3.7 triage); amended the same day by the E3.11 grilling (points 1, 3, 5
  and 7, consequences). Replaces ADR-0028 decision 4 and the Coordinator half of its decision 3; adds a row
  to ADR-0025 §2; replaces the "`historical_demand` is missing" fallback of the DatabaseMCP contract and
  GP-10. Built by E3.11. Point 3's line "historical data only with the `historical_demand` capability" and the
  "left to a separate task" entry on a user sending demand data are superseded by
  [ADR-0036](0036-raw-demand-data-aggregate.md)
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.3 (`Demand`,
  `Question`), §4.2; [ADR-0023](0023-coordinator-split-deterministic-executor.md),
  [ADR-0025](0025-executor-plan-shape-intent-rules-and-failures.md),
  [ADR-0028](0028-time-windows-are-time-of-day.md), [ADR-0034](0034-database-protocol-and-backends.md);
  work-plan E3.4, E3.7, E3.11, E5.1, E5.2, E6.2

## Context

Grilling the plan bank (E3.7) showed that the Coordinator has no rule for choosing a demand:

- Only 12 of the request bank's 73 concepts give a `demand_ref`. DEV-NET has three demands (`low`,
  `peak`, `incident`) over the same window, 08:00–09:00, so for about 60 concepts the Coordinator would
  pick one of three without any hint.
- A `Demand` records where its trips come from (`DemandSource`) and its intensity (`DemandSpec.profile`),
  but not what traffic it stands for: which day, a typical day or one specific date, an average, an event,
  or random trips.
- ADR-0028 read "peak hour" as the `peak` profile. A traffic engineer asked "what happens from 8 to 10"
  asks back which day is meant; the peak of a Saturday is not the peak of a Monday.
- ADR-0025 §2 makes every `intent` ensure baseline results, so a question about the network alone ("how
  many lanes has B0C0?") would need a demand and a simulation it does not use.

## Decision

1. **What a demand is.** A `Demand` is the set of trips on one network over one time window. It is built
   (random trips, or fitted to traffic counts), never measured; traffic counts are observations and live
   behind the `historical_demand` capability, not in `Demand`. Stored demands are the ones some study
   built, kept for reuse: they need not cover the calendar and may overlap. A `Demand` carries a
   `description` (free text, required, not blank) that says what it was built from, and `labels` (a free
   set, optional), with no closed vocabulary. Whoever creates the demand writes them: the Demand Generator
   in its draft (data, like `rationale`, not identity), or the person importing it. Code adds the profile
   to `labels`. Neither field is part of the id, so the same trips stored with another description are a
   conflict, as for any other content.
2. **No default demand.** The Coordinator matches `Question.demand_ref`, which is what the user said
   ("a typical Monday", "random traffic", "peak"), against the `description` and `labels` of the demands on
   the study's network.
3. **Resolution, in order.**
   - A stored demand matches and its window contains the requested one: reuse it (a wider demand is
     simulated whole; the Expert reads the requested period). Two demands are never joined; a partial
     overlap counts as not covered.
   - None is stored but one can be obtained: plan `generate_demand` with the description and the requested
     window. Random trips can always be obtained, so a request that accepts them ("peak", "random traffic")
     never reaches the next step. Historical data only with the `historical_demand` capability (E5.6).
     External datasets are not planned until the Demand Generator has an adapter that fetches them. How the
     Demand Generator fits counts of another granularity to the window is its own decision (E6.2, E6.5).
   - Otherwise, a `ClarificationRequest` that says what cannot be obtained and offers random trips as the
     alternative. There is no silent fallback to random demand, even when recorded; this replaces the
     contract's "`historical_demand` is missing" row, and GP-10 checks that the Coordinator asks.
   - The request says nothing about demand: a `ClarificationRequest` listing the stored demands as
     candidates. The Parser still does not flag this (it cannot know how many demands exist).
4. **"Peak hour" is a description**, interpreted by the Demand Generator. On DEV-NET it matches the random
   demand labelled `peak` because no other demand exists there, not by a fixed rule. A window no stored
   demand covers is generated when it can be obtained (point 3), not sent back to the user.
5. **A question about the network alone needs no demand.** The Input Parser marks it:
   `Question.network_only`, allowed only on a `describe` with no `demand_ref`, no `time_window`, no
   metrics and no changes. `intent` cannot tell it apart ("how many lanes has B0C0?" and "what was the
   delay on B0C0 at 8?" are both `describe`), and the absence of those fields is not enough either ("is
   B0C0 usually congested?" names no metric and is about traffic). It is planned with zero steps and its
   `network_id`. The Executor still asks the Expert, who answers from the network graph (`ExpertTask` with
   no `result_ids`). This adds a row to ADR-0025 §2.
6. **Networks by name.** No stored network matches and the name gives no way to build one (DEV-NET):
   `ClarificationRequest`. A real place (Barcelona) or a synthetic request (a grid): `generate_network`.
   Several stored networks match ("Barcelona" against `BCN-1347` and `BCN-1211`): `ClarificationRequest`
   with them as candidates. `Network` keeps its single `label`; aliases are left to a separate task.
   The Parser copies the name it reads and never checks it; whether the network exists is the
   Coordinator's question.
7. **What the Parser extracts.** `Question.demand_ref` is what the request says about the traffic, as one
   short English phrase put together from every part of the request that mentions it ("a typical
   Monday"), not a profile name; it is scored by presence only. `Question.time_window` is the period the
   user wants to look at, whatever the `intent` ("a typical Monday from 8 to 10, what if I close B0C0 from
   8:30 to 9?" keeps 08:00–10:00); the time of each change stays on the change. Without it the
   Coordinator could not tell `generate_demand` which window to build.

## Consequences

- Domain: `Demand.description` and `Demand.labels`; schemas, both `Database` backends (ADR-0034) and the
  DatabaseMCP demand record follow. The Demand Generator's draft (E6.2) writes both fields.
- DEV-NET's three demands get a description ("random trips, peak intensity, 08:00–09:00").
- The request bank (E3.4) names the demand in the concepts that need one (some with it spread across the
  text), keeps a few without it on purpose, and gains concepts for network-only questions (plus one traffic
  counterexample) and for networks not in the database. The Parser (E5.1) changes its bank and its prompt:
  the `demand_ref`, `time_window` and `network_only` rules are rewritten for the new contract. Both go in
  one tuning-log entry marked as a contract change, not tuning, and no other prompt edit goes with it; the
  held-out split is still unread. V2 measures the new bank. All of this is E3.11.
- The DatabaseMCP contract's "`historical_demand` is missing" row and GP-10 change to point 3. The
  frozen architecture body is not edited; this ADR supersedes its GP-10 row.
- `matrix.db` is rebuilt from `eval/scenario_matrix/build.py` once DEV-NET's demands are described.
- The plan bank (E3.7) encodes these rules; its "windows with no covering demand are a clarification"
  clause is replaced by point 4.
- Left to a separate task, with its own grilling: a catalogue of demands over days, events and
  aggregations, the level at which such data is labelled, fetching external demand data, network aliases,
  a user sending demand data (a CSV of trips or counts) when their database has none, and a user
  describing demand in words ("this street fills up, people mostly drive out of town") for the Demand
  Generator to build from.

## Alternatives considered

- **A default demand per network.** Rejected: it hides an assumption the user never made. When random
  trips are enough, the request says so.
- **Structured fields** (day type, date, aggregation, event, random or not). Rejected for now: nobody knows
  the vocabulary yet. Free text can be matched by the Coordinator's model, and fields can be added later.
- **The Parser flags a missing demand.** Rejected: it cannot see the database, so it can neither know
  whether one demand would do nor list the candidates.
- **Clarification for every uncovered window** (ADR-0028 §3). Rejected: a random demand for another hour
  is always obtainable, and asking would stop a study for nothing.
- **Fall back to random demand when `historical_demand` is missing** (the contract row and GP-10 before
  this ADR). Rejected: it swaps the traffic the user asked for with another one; a note in
  `reuse_decisions` does not make that the user's choice.
- **The Coordinator tells network-only questions apart** (this ADR before its amendment). Rejected: it
  is a reading of the text, which is the Parser's job, and a Parser flag makes the planning rule
  deterministic.
