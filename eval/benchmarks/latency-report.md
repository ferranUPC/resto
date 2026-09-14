# MCP tool latency benchmark — DEV-NET

Work-plan E1.6 · DoD §4.9 threshold: single call < 1 s on DEV-NET (< 5 s on REAL-NET — REAL-NET does not exist yet, see work-plan E6).

Generated 2026-09-14T12:54:43+00:00 · 50 reps/tool · SUMO 1.27.1 · `eval/dev-net/dev-net.net.xml`

## NetworkMCP

| Tool | mean (ms) | median (ms) | max (ms) | < 1 s |
|---|---|---|---|---|
| `get_edge` | 0.18 | 0.08 | 4.84 | ✅ |
| `get_lanes` | 0.08 | 0.07 | 0.13 | ✅ |
| `get_neighbours` | 0.07 | 0.07 | 0.20 | ✅ |
| `shortest_path` | 0.08 | 0.08 | 0.15 | ✅ |
| `edges_in_bbox` | 0.13 | 0.13 | 0.23 | ✅ |
| `capacity_estimate` | 0.07 | 0.07 | 0.08 | ✅ |
| `get_tls` | 0.07 | 0.07 | 0.09 | ✅ |

## DatabaseMCP

| Tool | mean (ms) | median (ms) | max (ms) | < 1 s |
|---|---|---|---|---|
| `store_network` | 0.09 | 0.08 | 0.19 | ✅ |
| `get_network` | 0.09 | 0.09 | 0.15 | ✅ |
| `list_networks` | 0.09 | 0.09 | 0.17 | ✅ |
| `find_network` | 0.10 | 0.10 | 0.15 | ✅ |
| `store_demand` | 0.09 | 0.09 | 0.14 | ✅ |
| `get_demand` | 0.09 | 0.09 | 0.12 | ✅ |
| `list_demands` | 0.10 | 0.09 | 0.14 | ✅ |
| `store_scenario` | 0.10 | 0.10 | 0.16 | ✅ |
| `get_scenario` | 0.12 | 0.11 | 0.32 | ✅ |
| `find_similar_scenario` | 0.15 | 0.14 | 0.28 | ✅ |
| `store_result` | 0.08 | 0.08 | 0.14 | ✅ |
| `get_result` | 0.08 | 0.08 | 0.10 | ✅ |
| `list_results` | 0.09 | 0.09 | 0.15 | ✅ |
| `query_edgedata` | 0.42 | 0.39 | 1.37 | ✅ |
| `store_note` | 0.11 | 0.10 | 0.19 | ✅ |
| `search_notes` | 0.12 | 0.12 | 0.16 | ✅ |
| `update_note_status` | 0.09 | 0.08 | 0.12 | ✅ |

## TraciMCP

| Tool | mean (ms) | median (ms) | max (ms) | < 1 s |
|---|---|---|---|---|
| `get_edge_occupancy` | 0.15 | 0.14 | 0.41 | ✅ |
| `get_edge_speed` | 0.14 | 0.14 | 0.17 | ✅ |
| `get_vehicle_count` | 0.13 | 0.13 | 0.14 | ✅ |
| `close_lane` | 0.18 | 0.17 | 0.36 | ✅ |
| `open_lane` | 0.13 | 0.13 | 0.17 | ✅ |
| `set_speed` | 0.12 | 0.12 | 0.14 | ✅ |
| `set_tls_program` | 0.13 | 0.13 | 0.16 | ✅ |
| `step` | 0.11 | 0.11 | 0.18 | ✅ |

## Summary

All 32 tools stayed under the 1 s DEV-NET threshold across 50 reps each (slowest: `NetworkMCP.get_edge`, 4.84 ms max).
