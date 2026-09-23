# ADR-0028: Time windows are time of day — the Parser writes clock times, simulations run on the same clock

- Status: Accepted
- Date: 2026-09-23
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.3 (`TimeWindow`,
  `Question`, `Intervention`), §3 (DEV-NET demand profiles, scenario matrix), §4.1;
  [ADR-0023](0023-coordinator-split-deterministic-executor.md); work-plan E3.4, E3.7, E5.1, E5.2

## Context

`TimeWindow` is documented as a "simulation-time interval in seconds", but nothing says which clock time
simulation second 0 is. The DEV-NET demand profiles cover `[0, 3600)` and the scenario matrix's
windows are `[0, 300)`; the architecture doc's matrix example writes "08:00–09:00". Users speak in clock
time ("from 8 to 9", "at 8:15"), and since ADR-0023 the Input Parser has no database access: it cannot
know when any demand starts, so it cannot translate a clock time into an offset from a simulation start.

## Decision

1. **`TimeWindow` is time of day**: seconds since midnight of the simulated day, `[start, end)`.
   "08:00–09:00" is `TimeWindow(28800, 32400)`. A window past midnight continues the count
   ("23:00–01:00" is `[82800, 90000)`); SUMO time is not bounded by a day.
2. **Simulations run on the same clock.** A `Demand`'s departures and the Runner's begin/end are time of
   day (SUMO `begin` = the demand window's start), so a `Question`'s window reaches the Scenario Builder
   unchanged. No component converts between clocks.
3. **The Parser records the time; it never checks it.** Whether any demand covers a window is a question
   about the database: the Coordinator answers it (a clarification request) or promotion rejects it
   (`StepError(user_input)`, ADR-0025).
4. **"Peak hour" is not a time.** It is a textual `Question.demand_ref` (`"peak"`), resolved by the
   Coordinator like `network_ref`; the Parser leaves `time_window` unset unless a time is given.

## Consequences

- Domain: only `TimeWindow`'s docstring changes; no field or invariant does.
- The request bank (E3.4) writes clock times in its gold `Question`s and does not depend on DEV-NET.
- **Existing DEV-NET assets are not migrated yet.** The demand profiles (`[0, 3600)`) and the scenario
  matrix (`[0, 300)` windows) now read as 00:00–01:00. Moving them to the morning shifts departures,
  which changes every `Demand` content hash and therefore every downstream `Scenario`/`SimulationResult`
  id: the matrix and the question bank must be rebuilt. This is pending work, needed before the
  Coordinator's plan bank (E3.7) and E5.2 plan against a fixed DB state that user requests can match.
- The evaluation-plan convention of 2026-09-23 "peak hour → the window of the DEV-NET `peak` profile" is
  replaced by decision 4.

## Alternatives considered

- **Simulation second 0 = 08:00 as a global convention.** Rejected: every network and demand would be
  tied to one hour, and the Parser would carry a DEV-NET assumption it cannot check.
- **Only relative times in requests ("the first 5 minutes").** Rejected: not how users speak.
- **A clock origin on `Demand`, with the Coordinator converting clock windows to simulation offsets.**
  Rejected for now: two clocks and a conversion step where SUMO can simply run on the day's clock.
