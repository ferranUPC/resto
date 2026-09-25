# DEV-NET/peak scenario matrix (work-plan E3.1)

Built by `python -m eval.scenario_matrix.build` from `eval/scenario_matrix/rows.py` (20 rows x 3 seeds = 60 `SimulationResult`s), stored via DatabaseMCP in `matrix.db`. Each row's own DoD §4.5 effect is re-checked against its seed-1 result before it counts as built (skipped for `signal_program`, `baseline` - see `build.py`'s module docstring).

| scenario_id | mechanism | description | mean departed (3 seeds) | mean delay (s) |
|---|---|---|---|---|
| S00 (`4c8d8002a6d3`) | baseline | no interventions | 1200.0 | 28.2 |
| S01 (`948978090cdc`) | lane_closure | lane_closure B2C2 lane 0, 08:00-08:05 | 1199.0 | 31.4 |
| S02 (`882d4871cbad`) | lane_closure | lane_closure C2D2 lane 0, 08:00-08:05 | 1198.0 | 31.3 |
| S03 (`8a24733cc79f`) | lane_closure | lane_closure B0C0 lane 0, 08:00-08:05 (bottleneck approach, lane 1 stays open) | 1200.0 | 28.7 |
| S04 (`5a95ab194df0`) | lane_closure | lane_closure C1D1 lane 0, 08:00-08:05 | 1200.0 | 28.6 |
| S05 (`663c33060042`) | edge_closure | edge_closure C0D0, 08:00-08:05 (bottleneck exit, single lane - full closure) | 1200.0 | 28.9 |
| S06 (`e570d6a1a0dc`) | edge_closure | edge_closure A1B1, 08:00-08:05 | 1198.0 | 28.6 |
| S07 (`8d1ba98a463c`) | edge_closure | edge_closure D2E2, 08:00-08:05 | 1199.0 | 29.7 |
| S08 (`cac893e22cf5`) | edge_closure | edge_closure B2C2, 08:00-08:05 | 1199.0 | 31.4 |
| S09 (`c2b9a6f103bb`) | speed_limit | speed_limit B2C2 lane 0 at 5 m/s, 08:00-08:05 | 1200.0 | 28.4 |
| S10 (`09da8eac421b`) | speed_limit | speed_limit C1D1 lane 0 at 5 m/s, 08:00-08:05 | 1200.0 | 28.1 |
| S11 (`d392d65f6fe0`) | speed_limit | speed_limit A2B2 lane 0 at 8 m/s, 08:00-08:05 | 1200.0 | 28.4 |
| S12 (`2f48eef2b60d`) | speed_limit | speed_limit B0C0 lane 0 at 5 m/s, 08:00-08:05 | 1200.0 | 28.2 |
| S13 (`ea1adb1d387b`) | signal_program | signal_program C2 -> program 1, 08:02-08:05 | 1200.0 | 29.7 |
| S14 (`50a08a679556`) | signal_program | signal_program B2 -> program 1, 08:05-08:08 | 1200.0 | 28.5 |
| S15 (`7c25a65b89bc`) | signal_program | signal_program D2 -> program 1, 08:08-08:11 | 1200.0 | 29.3 |
| S16 (`c0b9a49d9717`) | signal_program | signal_program A2 -> program 1, 08:11-08:14 | 1200.0 | 28.5 |
| S17 (`39c3902620af`) | demand_scale | demand_scale x1.2 (heavier peak) | 1440.0 | 30.4 |
| S18 (`28cc0b2131b8`) | demand_scale | demand_scale x0.8 (lighter peak) | 960.0 | 26.9 |
| S19 (`11e411e996d0`) | demand_scale | demand_scale x1.5 (much heavier peak) | 1799.3 | 32.8 |
