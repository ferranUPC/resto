# Held-out blind annotation — agreement with the bank's gold

Each annotation is scored with the Parser benchmark's `score_request`, so the rates below read like a Parser report: how often a person, reading the request without the bank's wording conventions, lands on the gold.

## Ferran González García

24 of 24 held-out concepts marked done.

| Metric | Agreement with gold |
|---|---|
| intent | 89 % (16/18) |
| interventions | 100 % (16/16) |
| topology_changes | 100 % (16/16) |
| metrics_of_interest | 75 % (12/16) |
| ambiguity_detection | 88 % (7/8) |
| arm_structure | 75 % (3/4) |
| intent_strict | 72 % (13/18) |
| spurious_ambiguity | 6 % (1/16) |
| network_ref | 100 % (16/16) |
| demand_ref | 94 % (15/16) |
| time_window | 100 % (16/16) |

`intent` also accepts the second reading listed in `concepts.ALSO_ACCEPTED`; `intent_strict` is against the gold intent alone. `spurious_ambiguity` is the share of clear requests the annotator still asked about (lower means closer to gold); the other rows are agreement.

| Concept | Category | intent | ambiguity | interventions | topology | metrics | arms |
|---|---|---|---|---|---|---|---|
| R013 | single | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| R053 | unintelligible | — | ✓ | — | — | — | — |
| R022 | multi_arm | ✗ | ✓ | ✓ | ✓ | ✓ | ✗ |
| R012 | single | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| R073 | single | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| R057 | out_of_scope | — | ✓ | — | — | — | — |
| R062 | adversarial | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| R037 | ambiguous | ✓ | ✓ | — | — | — | — |
| R032 | combined | ✓ | ✓ | ✓ | ✓ | ✗ | — |
| R046 | ambiguous | — | ✓ | — | — | — | — |
| R052 | unintelligible | — | ✓ | — | — | — | — |
| R023 | multi_arm | ✓ | ✗ | ✓ | ✓ | ✗ | ✓ |
| R033 | combined | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| R042 | ambiguous | — | ✓ | — | — | — | — |
| R017 | single | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| R027 | multi_arm | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ |
| R043 | ambiguous | ✓ | ✗ | — | — | — | — |
| R007 | single | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| R072 | single | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| R016 | single | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| R068 | single | ✓ | ✓ | ✓ | ✓ | ✗ | — |
| R056 | out_of_scope | — | ✓ | — | — | — | — |
| R069 | single | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| R003 | multi_arm | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |

### Disagreements

**R022** (multi_arm) — differs on intent, arm_structure

> On DEV-NET, how much would building a new one-lane edge from junction C1 to junction D2, with a 50 km/h limit, reduce the mean delay? And once that edge is built, how much more would the mean delay change if edge C2D2 were also closed from 08:00 to 08:30?

Gold:
    intent `counterfactual` · network `DEV-NET` · metrics mean_delay
    - arm `new_edge`: `add_edge(from_junction=C1, to_junction=D2, lanes=1, speed=13.889)`
    - arm `new_edge_closure`: `add_edge(from_junction=C1, to_junction=D2, lanes=1, speed=13.889)` + `edge_closure(C2D2, 08:00–08:30)`
    - contrasts: `new_edge` vs `base`, `new_edge_closure` vs `new_edge`

Annotator:
    intent `compare` · network `DEV-NET` · metrics mean_delay
    - arm `new_edge`: `add_edge(from_junction=C1, to_junction=D2, lanes=1, speed=13.889)`
    - arm `edge_and_closure`: `add_edge(from_junction=C1, to_junction=D2, lanes=1, speed=13.889)` + `edge_closure(C2D2, 08:00–08:30)`
    - contrasts: `new_edge` vs `base`, `edge_and_closure` vs `base`

**R032** (combined) — differs on metrics_of_interest

> Simulate DEV-NET with edge B1C1 removed from the network and, in the same run, demand raised by 15 % from 08:00 to 09:00; report the mean delay.

Gold:
    intent `counterfactual` · network `DEV-NET` · metrics mean_delay
    - arm `treatment`: `remove_edge(edge_id=B1C1)` + `demand_scale(, factor=1.15, 08:00–09:00)`

Annotator:
    intent `run` · network `DEV-NET`
    - arm `treatment`: `remove_edge(edge_id=B1C1)` + `demand_scale(, factor=1.15, 08:00–09:00)`

Notes: I understand all of them together

**R023** (multi_arm) — differs on metrics_of_interest, spurious_ambiguity

> On DEV-NET, suppose a two-lane edge called NEW1 is built from junction B3 to junction C2 with a 50 km/h limit. Once NEW1 is in place, what would closing its lane 0 from 08:00 to 08:30 do to the mean travel time, compared with NEW1 fully open?

Gold:
    intent `counterfactual` · network `DEV-NET` · metrics mean_travel_time
    - arm `new_edge`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)`
    - arm `new_edge_closure`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)` + `lane_closure(NEW1/0, 08:00–08:30)`
    - contrasts: `new_edge_closure` vs `new_edge`

Annotator:
    intent `counterfactual` · network `DEV-NET`
    - arm `new_edge`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)`
    - arm `edge_and_close`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)` + `lane_closure(NEW1/0, 08:00–08:30)`
    - contrasts: `edge_and_close` vs `new_edge`
    - ambiguities: Would you want to compare also against the base case?

**R027** (multi_arm) — differs on intent

> Suppose edge C3D3 on DEV-NET is widened to three lanes. Is it then better to close lane 2 of C3D3 from 08:00 to 08:30, or to limit C3D3 to 30 km/h over the same period? Compare each option with the widened network alone, by mean travel time.

Gold:
    intent `compare` · network `DEV-NET` · metrics mean_travel_time
    - arm `widened`: `set_lanes(edge_id=C3D3, lanes=3)`
    - arm `widened_closure`: `set_lanes(edge_id=C3D3, lanes=3)` + `lane_closure(C3D3/2, 08:00–08:30)`
    - arm `widened_limit`: `set_lanes(edge_id=C3D3, lanes=3)` + `speed_limit(C3D3, speed=8.333, 08:00–08:30)`
    - contrasts: `widened_closure` vs `widened`, `widened_limit` vs `widened`

Annotator:
    intent `counterfactual` · network `DEV-NET` · metrics mean_travel_time
    - arm `close_lane`: `set_lanes(edge_id=C3D3, lanes=3)` + `lane_closure(C3D3/2, 08:00–08:30)`
    - arm `limit_speed`: `set_lanes(edge_id=C3D3, lanes=3)` + `speed_limit(C3D3, speed=8.333, 08:00–08:30)`
    - arm `widened`: `set_lanes(edge_id=C3D3, lanes=3)`
    - contrasts: `close_lane` vs `widened`, `limit_speed` vs `widened`

**R043** (ambiguous) — differs on ambiguity_detection

> Simulate DEV-NET with edge A2B2 removed and with edge B0C0 reduced to one lane, and report the mean travel time.

Gold:
    expect `ambiguities[]` (one run with both changes or one run each, intent `counterfactual`)

Annotator:
    intent `run` · network `DEV-NET` · metrics mean_travel_time
    - arm `treatment`: `remove_edge(edge_id=A2B2)` + `set_lanes(edge_id=B0C0, lanes=2)`

**R068** (single) — differs on metrics_of_interest

> Remove edge D3E3 from DEV-NET for good and keep the resulting network.

Gold:
    intent `run` · network `DEV-NET`
    - arm `treatment`: `remove_edge(edge_id=D3E3)`

Annotator:
    intent `run` · network `DEV-NET` · metrics waiting_time
    - arm `treatment`: `remove_edge(edge_id=D3E3)`

**R003** (multi_arm) — differs on metrics_of_interest

> On DEV-NET, which reduces the mean delay more: closing edge C0D0 from 08:00 to 08:30, or limiting edge B2C2 to 30 km/h over the same period?

Gold:
    intent `compare` · network `DEV-NET` · metrics mean_delay
    - arm `closure`: `edge_closure(C0D0, 08:00–08:30)`
    - arm `speed_limit`: `speed_limit(B2C2, speed=8.333, 08:00–08:30)`
    - contrasts: `closure` vs `base`, `speed_limit` vs `base`

Annotator:
    intent `compare` · network `DEV-NET`
    - arm `closing`: `edge_closure(C0D0, 08:00–08:30)`
    - arm `limiting`: `speed_limit(B2C2, speed=8.333, 08:00–08:30)`
    - contrasts: `closing` vs `base`, `limiting` vs `base`

