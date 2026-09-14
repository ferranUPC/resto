# DEV-NET demand profiles

Work plan E0.6: `low` / `peak` / `incident` demand on DEV-NET, seeded, stored as trips + routes,
with synthetic counts at control edges and a verification notebook confirming `peak` congests
~10-20% of edges. Same spirit as `../generate.sh` for the network itself: every parameter below was
chosen empirically (by running SUMO, not guessed) and is reproducible from `generate_demand.sh`.

## Two different seeds

The domain model has two independent sources of randomness, and this matters for how "verify
statistically" was interpreted here:

- `DemandSpec.seed` — seeds `randomTrips`, i.e. decides *which trips* a profile generates. Each
  profile gets exactly **one** fixed seed (`1`), so `low.rou.xml` / `peak.rou.xml` /
  `incident.rou.xml` are the three canonical, reproducible demand sets E0.6 asks for.
- `SimulationResult.seed` — SUMO's own stochasticity (car-following, lane-changing) when simulating
  a *fixed* set of routes. `verification.ipynb` runs each profile's stored routes through several
  different simulation seeds (`SIM_SEEDS`, currently 1-9) and reports congestion as mean ± std
  across them, matching the project's own convention elsewhere (E3.1, E4.7) of repeating a
  measurement over several seeds rather than trusting one run.

  This turned out to matter in practice, not just in principle: the original `incident` rate (980
  veh/h) passed cleanly on the first 3 seeds tried, but widening to 9 seeds surfaced simulation-seed
  8 collapsing into gridlock (112 teleports). See "Why 950, not closer to the cliff" below — a
  proposed further widening (`SIM_SEEDS = range(1, 20)`) would have caught it even with the original
  3-seed check being pure luck. Prefer more seeds over fewer when a profile sits near a capacity
  cliff, since the whole point of a metastable regime is that few samples can look deceptively
  stable.

This separates "does congestion depend on SUMO's internal noise" (what the notebook checks) from
"did we get lucky with one random trip realization" (not in scope — would mean more than 3 stored
demand sets, which isn't what the deliverable asks for).

## Congestion metric

An edge counts as congested in a run if, over the whole 1 h aggregation window
(`--edgedata-output`):

- `sampledSeconds > 0` (it carried traffic at all), and
- `speedRelative <= 0.5` (average speed at or under half its speed limit), and
- `occupancy >= 0.5` (%).

The occupancy floor exists because speed alone is contaminated by DEV-NET's own signalised
corridor: a single car waiting through one red phase drags an otherwise-empty approach edge's
average speed below 50% of free-flow just as effectively as a real queue does. Empirically, an
idle-signal artifact stays under ~0.15% occupancy here; a genuinely queued approach clears 1%.
`sim_utils.CONGESTION_SPEED_RATIO` / `CONGESTION_MIN_OCCUPANCY` hold these thresholds.

Percentage = (# congested edges) / 80 (all of DEV-NET's directed edges, matching the plain reading
of "≈10-20% edges congested").

## Profiles

All three share `window = [0, 3600)` (1 h), `seed = 1`, Poisson-distributed departures
(`--poisson`), random depart/arrival position on the edge, and are validated for connectivity
(`--validate`) before routing with `duarouter`.

| profile | `vehicles_per_hour` | routing | congestion (mean, 9 sim seeds) | teleports |
|---|---|---|---|---|
| `low` | 300 | uniform over all edges | ~5% | 0/9 |
| `peak` | 1200 | uniform over all edges | 16.5% | 0/9 |
| `incident` | 950 | every trip forced via `B0C0` (`-i 1 --weights-prefix incident`, `incident.via.xml` gives `B0C0` weight 1 and every other edge weight 0 — see `LoadedProps` in `randomTrips.py`) | ~20% (network-wide) — concentrated: **B0C0 occupancy is 26x peak's** (0.22% → 5.72%) | 0/9 |

**How `peak` was picked**: swept `vehicles_per_hour` from 300 to 4000 (`sim_utils.congestion_fraction`
over 3 sim seeds each). The network saturates hard: congestion is ≈flat at 15-17.5% for anything
between 600 and 1500 veh/h, crosses 20% around 1800, and only breaks down (teleports appear) past
~4000. 1200 sits in the middle of that stable plateau, comfortably inside [0.10, 0.20] on every
individual seed (not just the mean) — safer than picking a rate near either boundary.

**Why `peak`'s congestion is *not* at the bottleneck**: under uniform random OD, only ~42-46 veh/h
ever cross `B0C0` (traffic spreads over many possible routes in a 5x5 grid) — nowhere near its
capacity. All of `peak`'s congested edges are row-2 corridor approaches instead: a traffic light
imposes a capacity/delay penalty that a plain priority junction in this network doesn't reach until
far higher, more degenerate demand. This is a real property of DEV-NET, not a metric bug (see
`incident` below for evidence the bottleneck *can* be stressed).

**Why `incident` is a forced-via profile, not just scaled-up `peak`**: swept `vehicles_per_hour`
forced through `B0C0` alone (same mechanism) and found a sharp capacity cliff for this single lane:
stable up to ~950-990 veh/h (`speedRelative` 0.66-0.76, 0 teleports on the first seed tried), then
complete breakdown at 1000+ (`speedRelative` ≈0.02-0.05, hundreds of teleports out of ~1000
vehicles — a degenerate, unusable fixture). This models "an incident elsewhere pushes
through-traffic onto this corridor" rather than "a closure inside DEV-NET itself" (that would be a
Scenario Builder `Intervention`, not a demand profile). The 2→1 lane merge never gets a chance to
show this trait under uniform peak demand alone — `incident` is what actually exercises it.

**Why 950, not closer to the cliff (e.g. 980)**: the cliff is not a hard wall at a fixed
`vehicles_per_hour` — it's a *metastable capacity drop*, a well-known real-traffic phenomenon where
operation just below nominal capacity is stable most of the time but a locally bursty arrival
pattern (the trips are Poisson-distributed) can occasionally tip the merge into a queue that never
dissipates for the rest of the hour. Concretely: at 980 veh/h, sweeping simulation seeds 1-20 (fixed
trips, only SUMO's internal stochasticity varying) teleported on 5/20 seeds — a 25% failure rate,
not a rare fluke. The same sweep at 950 stayed teleport-free on 20/20 seeds. 950 is the value
actually committed; DEV-NET is meant to give deterministic, construction-known answers downstream,
so a demand profile that has a real chance of randomly gridlocking depending on which
`SimulationResult.seed` a later scenario picks is a correctness risk, not an interesting feature.

## Control edges (synthetic counts for calibration)

| edge | why |
|---|---|
| `B0C0` | bottleneck approach (2 lanes, row 0) |
| `C0D0` | bottleneck exit (1 lane, row 0) |
| `C2D2` | inside the signalised corridor (row 2) |
| `A0A1` | baseline, far from both features (column A, south) |
| `E2E3` | leaving the corridor northbound (column E) |

`control_counts.json` holds, per profile, the mean vehicle count (`left`, i.e. vehicles that
crossed the edge) at each control edge over `SIM_SEEDS` — the synthetic ground truth a
future Demand Generator calibration round (`Fidelity`/`EdgeFidelity`, architecture doc §4.4) would
try to reproduce within tolerance.

## Files

- `generate_demand.sh` — reproducible build (`randomTrips` + `duarouter`, run inside the `resto`
  conda env with `SUMO_HOME` unset). Regenerates `{low,peak,incident}.trips.xml` / `.rou.xml`.
- `incident.via.xml` — the one non-default input: a `randomTrips` weights file forcing every
  `incident` trip through `B0C0`.
- `sim_utils.py` — shared helpers (run a sim, parse `edgedata`, the congestion predicate, the
  control-edge list) used by both the calibration exploration (not committed) and
  `verification.ipynb`, so the notebook checks the exact same thing the parameters were tuned
  against.
- `verification.ipynb` — runs all 3 profiles × `SIM_SEEDS` (currently `range(1, 10)`), asserts
  `peak` congestion ∈ [0.10, 0.20] and 0 teleports everywhere, shows the per-control-edge table
  that distinguishes `incident` from `peak`, and writes `control_counts.json`. Pre-executed;
  outputs are saved in the notebook so it's readable without re-running.
- `control_counts.json` — the synthetic control-edge counts (see above).
