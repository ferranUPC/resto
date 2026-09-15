# DEV-NET/peak scenario matrix (work-plan E3.1)

Built by `python -m eval.scenario_matrix.build` from `eval/scenario_matrix/rows.py` (20 rows x 3 seeds = 60 `SimulationResult`s), stored via DatabaseMCP in `matrix.db`. Each row's own DoD §4.5 effect is re-checked against its seed-1 result before it counts as built (skipped for `signal_program`, `baseline` - see `build.py`'s module docstring).

| scenario_id | mechanism | description | mean departed (3 seeds) | mean delay (s) |
|---|---|---|---|---|
| S00 (`9bf1ee8ea4e9`) | baseline | no interventions | 1200.0 | 28.2 |
| S01 (`f12914bff5cd`) | lane_closure | lane_closure B2C2 lane 0, [0, 300) | 1199.0 | 31.4 |
| S02 (`fe942630244f`) | lane_closure | lane_closure C2D2 lane 0, [0, 300) | 1198.0 | 31.3 |
| S03 (`9000329f9823`) | lane_closure | lane_closure B0C0 lane 0, [0, 300) (bottleneck approach, lane 1 stays open) | 1200.0 | 28.7 |
| S04 (`7e55b671b20c`) | lane_closure | lane_closure C1D1 lane 0, [0, 300) | 1200.0 | 28.6 |
| S05 (`56a99f0d5d98`) | edge_closure | edge_closure C0D0, [0, 300) (bottleneck exit, single lane - full closure) | 1200.0 | 28.9 |
| S06 (`8d2ca7483129`) | edge_closure | edge_closure A1B1, [0, 300) | 1198.0 | 28.6 |
| S07 (`007d4368fe8e`) | edge_closure | edge_closure D2E2, [0, 300) | 1199.0 | 29.7 |
| S08 (`db8a3972baf5`) | edge_closure | edge_closure B2C2, [0, 300) | 1199.0 | 31.4 |
| S09 (`ed51a5cada16`) | speed_limit | speed_limit B2C2 lane 0 at 5 m/s, [0, 300) | 1200.0 | 28.4 |
| S10 (`93572479317c`) | speed_limit | speed_limit C1D1 lane 0 at 5 m/s, [0, 300) | 1200.0 | 28.1 |
| S11 (`73f567416279`) | speed_limit | speed_limit A2B2 lane 0 at 8 m/s, [0, 300) | 1200.0 | 28.4 |
| S12 (`2c5b7f44bbdd`) | speed_limit | speed_limit B0C0 lane 0 at 5 m/s, [0, 300) | 1200.0 | 28.2 |
| S13 (`71d48a023862`) | signal_program | signal_program C2 -> program 1, [100, 300) | 1200.0 | 29.7 |
| S14 (`d0e8be551e1f`) | signal_program | signal_program B2 -> program 1, [300, 500) | 1200.0 | 28.6 |
| S15 (`cc9ac622732d`) | signal_program | signal_program D2 -> program 1, [500, 700) | 1200.0 | 29.1 |
| S16 (`295f85d689f0`) | signal_program | signal_program A2 -> program 1, [700, 900) | 1200.0 | 28.3 |
| S17 (`7d032461ddbf`) | demand_scale | demand_scale x1.2 (heavier peak) | 1440.0 | 30.4 |
| S18 (`b82cd51cfac9`) | demand_scale | demand_scale x0.8 (lighter peak) | 960.0 | 26.9 |
| S19 (`7f97cfe8331a`) | demand_scale | demand_scale x1.5 (much heavier peak) | 1799.3 | 32.8 |
