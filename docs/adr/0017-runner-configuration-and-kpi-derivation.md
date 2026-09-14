# ADR-0017: Runner configuration lives entirely in `.sumocfg` files (scenario cfg + derived run cfg); KPIs derived from `statistic-output`

- Status: Accepted
- Date: 2026-09-14
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.2 (Scenario
  Builder tools, `write_sumocfg`), §2.4 (Simulation Runner), §4.6; work-plan E2.1, E2.2, E2.4

## Context

The architecture fixes that a `Scenario` carries one `sumocfg` artifact and that the Runner "runs `sumo` on
the `sumocfg`", but three things it depends on were unspecified when E2.1 started:

1. **What goes in the cfg vs. on the command line.** A `Scenario` is hashed by its request and serves any
   number of runs, while the seed and the output paths belong to one run. If they lived in the scenario cfg,
   one scenario would need one cfg per run; if they lived on the Runner's command line, reproducing a run
   would require knowing which flags the Runner used, which is exactly the knowledge an artifact should carry.
2. **Which SUMO output feeds each `Kpis` field.** `mean_delay`, `mean_travel_time`, `teleports`,
   `departed`, `arrived` are named in §2.3 but no source is stated; the DEV-NET eval scaffolding runs SUMO
   with `--duration-log.disable`, which suppresses the very block (`<vehicleTripStatistics>`) that carries
   most of them.
3. **The time resolution of edgedata.** `--edgedata-output` in SUMO 1.27.1 has no period option (checked in
   `sumoConfigurationType.xsd`: `edgedata-output` exists, `edgedata-output.period` does not) and aggregates
   the whole run into one interval. The effect checks of §4.5 ("flow 0 inside the window, > 0 outside")
   need intervals.

`sumoConfigurationType.xsd` confirms every option the Runner needs has a cfg element: `seed` under
`random_number`; `tripinfo-output`, `statistic-output`, `summary-output` under `output`;
`duration-log.statistics`, `no-step-log` under `report`. Nothing forces the command line.

## Decision

**Two cfg files, nothing on the command line but `-c`.**

- The **scenario cfg** is written by the `write_sumocfg` writer (`adapters/sumo/writers/sumocfg.py`,
  exposed to the Builder as a tool) from a `SimulationSettings` record: `input` (net, routes, additional
  files), `time` (`begin`, `end`, `step-length`) and `processing` (`time-to-teleport`). It contains **no**
  `random_number` and **no** `output` section. All paths are written **relative to the cfg's own directory**,
  never absolute, so its `content_hash` is stable across machines. It is the artifact the `Scenario` holds.
- The **run cfg** is derived by the Runner (`adapters/sumo/runner.py`) for every execution: the scenario cfg
  with input paths rebased to the run directory, plus `<random_number><seed>`, plus a fixed `<output>` block
  (`tripinfo-output`, `statistic-output`, `summary-output`), plus `<report>` (`duration-log.statistics`,
  `no-step-log`). It is written into the run's directory and recorded in `SimulationResult.artifacts` with
  kind `sumocfg`. `sumo -c run.sumocfg` reproduces the run with no further knowledge of the Runner.
- **Edgedata comes from an `<edgeData>` additional file**, also written by the Runner into the run
  directory and appended to the run cfg's `additional-files`, with a fixed aggregation period
  `EDGEDATA_PERIOD_S = 300` (5 min; 12 intervals per simulated hour, enough for the §4.5 window checks and
  coarse enough to keep the file small). `query_edgedata` already aggregates across intervals, so consumers
  see no difference between one interval and twelve.

**KPI mapping** (from `statistic-output`, which requires `duration-log.statistics`):

| `Kpis` field | SUMO source |
|---|---|
| `mean_travel_time` | `vehicleTripStatistics/@duration` |
| `mean_delay` | `vehicleTripStatistics/@timeLoss` |
| `teleports` | `teleports/@total` |
| `departed` | `vehicles/@inserted` |
| `arrived` | `vehicleTripStatistics/@count` (vehicles that completed their trip) |

`inserted >= count` always holds in SUMO, so the `Kpis` invariant `arrived <= departed` is satisfied by
construction. When `count == 0` the means are reported as `0.0`.

**Reproducibility hash.** `SimulationResult.content_hash` covers only the deterministic artifacts
(`sumocfg`, the edgedata `additional`, `edgedata`, `tripinfo`), each hashed with SUMO's `<!-- generated
on ... -->` header comment stripped (it carries a timestamp and the absolute paths of the run; 1.27.1 has
no option to omit it). `statistic-output` and `summary-output` are kept as artifacts (the former is the
KPI source) but excluded from the hash: `<performance>` carries wall-clock timestamps and every summary
`<step>` carries `duration`, its computation time in ms. Both were observed to differ between two
otherwise identical runs on DEV-NET.

**Failed runs are stored, not deduplicated.** A failed `SimulationResult` (SUMO error, non-zero exit,
missing outputs) is persisted with the SUMO message so the failure is on record, but `run_simulation` only
short-circuits on an existing **ok** result for the same `result_id`; a failed one is re-run.

**Ephemeral runs** (`probe_run`, `calibration_run`) go through `run_ephemeral`, which takes no repository
at all — it cannot write to the results store by construction, not by discipline.

## Consequences

- The Runner has one place that decides outputs, and it is a file the user can read and re-execute. Changing
  what a run produces (an extra output, a different edgedata period) is a change to the run cfg derivation
  and shows up as a different `sumocfg` artifact.
- The scenario cfg is small and hashable; two Builders producing the same settings produce the same bytes.
- The Runner must parse and rewrite the scenario cfg (rebase relative paths). This is a few lines of
  `ElementTree` and is tested; it is the price of relative paths, which the hash stability needs.
- `EDGEDATA_PERIOD_S` is a constant of the run, so results simulated under a different period are not
  byte-comparable. It is recorded in the run cfg's additional file, which is hashed, so a change is visible.
- `--duration-log.disable` in the eval scaffolding (`eval/dev-net/demand/sim_utils.py`) stays as is: that
  code is not framework code and measures congestion from edgedata, not from KPIs.

## Alternatives considered

- **Seed and outputs on the command line, scenario cfg only.** Rejected: reproducing a run would require
  the Runner's flag list; the artifact would not be the command.
- **One cfg per run written by the Builder.** Rejected: the Builder does not know the seed; it would also
  break `Scenario` = one cfg, N runs.
- **`--edgedata-output` with whole-run aggregation.** Rejected: §4.5 effect checks need time intervals and
  1.27.1 offers no period option for that flag.
- **Compute KPIs from `tripinfo-output` in Python.** Rejected for v1: `statistic-output` is SUMO's own
  aggregate of the same per-vehicle records, so re-averaging in Python adds code without adding information.
  `tripinfo` is still kept as an artifact for per-vehicle analysis by the Expert.
