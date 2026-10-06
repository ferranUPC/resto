# Input Parser benchmark — v7-dev

> **Superseded on `intent` by ADR-0038 (2026-10-06): this run scores `intent` against the gold that still had `counterfactual`, a value that no longer exists. Not re-scored: its Parser taught `counterfactual`, so against the new gold the number would measure the removed label, not the Parser. Every other metric is unaffected. The raw run is untouched; current intent figures are in `v8-dev`.**

255 requests, 255 runs (repetitions [1]), models ['deepseek/deepseek-v4.1-flash'], parser ['v7']; estimated $0.3051 · real $0.1941, mean 5291 input / 671 output tokens; stop reasons {'output': 254, 'budget': 1}.

| Metric | Result | 95 % CI by concept | E5.1 threshold | Met |
|---|---|---|---|---|
| schema_validity | 99.6 % (254/255) | 99–100 % (54 concepts) | ≥ 98% | yes |
| intent | 99.5 % (202/203) | 98–100 % (42 concepts) | ≥ 85% | yes |
| interventions | 100.0 % (164/164) | 92–100 % (36 concepts, rule of three) | ≥ 85% | yes |
| topology_changes | 100.0 % (164/164) | 92–100 % (36 concepts, rule of three) | ≥ 85% | yes |
| metrics_of_interest | 100.0 % (164/164) | 92–100 % (36 concepts, rule of three) | ≥ 85% | yes |
| ambiguity_detection | 95.6 % (87/91) | 91–99 % (35 concepts) | ≥ 80% | yes |
| arm_structure | 100.0 % (43/43) | 70–100 % (10 concepts, rule of three) | ≥ 90% | yes |

Met is judged on the point estimate. The interval resamples whole concepts (bootstrap), so it shows how much the result could move with another draw of concepts; when every concept is right it is the rule-of-three bound 1 − 3/n. `intent` also accepts the second reading listed in `concepts.ALSO_ACCEPTED`; `intent_strict` below is against the gold intent alone.

Reported, not graded:

- intent_strict: 99.5 % (202/203)
- arm_structure_single: 100.0 % (121/121)
- required_arms: 100.0 % (43/43)
- spurious_ambiguity: 11.0 % (18/164)
- used_shorthand: 100.0 % (80/80)
- network_ref: 98.2 % (161/164)
- demand_ref: 93.3 % (153/164)
- network_only: 100.0 % (164/164)
- time_window: 84.1 % (138/164)
- consistency across variants: 85.2 % (46/54)

## By category

| category | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| adversarial | 100.0 % (15/15) | 100.0 % (10/10) | 100.0 % (10/10) | 100.0 % (10/10) | 100.0 % (10/10) | 100.0 % (5/5) | — |
| ambiguous | 97.7 % (43/44) | 100.0 % (24/24) | — | — | — | 95.5 % (42/44) | — |
| combined | 100.0 % (18/18) | 100.0 % (18/18) | 100.0 % (18/18) | 100.0 % (18/18) | 100.0 % (18/18) | — | — |
| multi_arm | 100.0 % (49/49) | 97.8 % (45/46) | 100.0 % (43/43) | 100.0 % (43/43) | 100.0 % (43/43) | 66.7 % (4/6) | 100.0 % (43/43) |
| out_of_scope | 100.0 % (12/12) | — | — | — | — | 100.0 % (12/12) | — |
| single | 100.0 % (105/105) | 100.0 % (105/105) | 100.0 % (93/93) | 100.0 % (93/93) | 100.0 % (93/93) | 100.0 % (12/12) | — |
| unintelligible | 100.0 % (12/12) | — | — | — | — | 100.0 % (12/12) | — |

## By split

| split | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| dev | 99.6 % (254/255) | 99.5 % (202/203) | 100.0 % (164/164) | 100.0 % (164/164) | 100.0 % (164/164) | 95.6 % (87/91) | 100.0 % (43/43) |

## By lang

| lang | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| ca | 100.0 % (38/38) | 100.0 % (30/30) | 100.0 % (24/24) | 100.0 % (24/24) | 100.0 % (24/24) | 100.0 % (14/14) | 100.0 % (6/6) |
| de | 100.0 % (36/36) | 100.0 % (30/30) | 100.0 % (25/25) | 100.0 % (25/25) | 100.0 % (25/25) | 90.9 % (10/11) | 100.0 % (7/7) |
| en | 100.0 % (106/106) | 98.8 % (85/86) | 100.0 % (67/67) | 100.0 % (67/67) | 100.0 % (67/67) | 97.4 % (38/39) | 100.0 % (18/18) |
| es | 100.0 % (44/44) | 100.0 % (32/32) | 100.0 % (26/26) | 100.0 % (26/26) | 100.0 % (26/26) | 94.4 % (17/18) | 100.0 % (6/6) |
| zh | 96.8 % (30/31) | 100.0 % (25/25) | 100.0 % (22/22) | 100.0 % (22/22) | 100.0 % (22/22) | 88.9 % (8/9) | 100.0 % (6/6) |

## By style

| style | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| colloquial | 100.0 % (22/22) | 100.0 % (19/19) | 100.0 % (16/16) | 100.0 % (16/16) | 100.0 % (16/16) | 100.0 % (6/6) | 100.0 % (5/5) |
| messy | 100.0 % (16/16) | 100.0 % (14/14) | 100.0 % (11/11) | 100.0 % (11/11) | 100.0 % (11/11) | 80.0 % (4/5) | 100.0 % (3/3) |
| plain | 99.4 % (175/176) | 100.0 % (137/137) | 100.0 % (107/107) | 100.0 % (107/107) | 100.0 % (107/107) | 95.7 % (66/69) | 100.0 % (27/27) |
| technical | 100.0 % (18/18) | 100.0 % (16/16) | 100.0 % (15/15) | 100.0 % (15/15) | 100.0 % (15/15) | 100.0 % (3/3) | 100.0 % (3/3) |
| telegraphic | 100.0 % (10/10) | 85.7 % (6/7) | 100.0 % (7/7) | 100.0 % (7/7) | 100.0 % (7/7) | 100.0 % (3/3) | 100.0 % (3/3) |
| verbose | 100.0 % (13/13) | 100.0 % (10/10) | 100.0 % (8/8) | 100.0 % (8/8) | 100.0 % (8/8) | 100.0 % (5/5) | 100.0 % (2/2) |

## By vague

| vague | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| grouping | 100.0 % (3/3) | — | — | — | — | 33.3 % (1/3) | — |
| none | 99.6 % (236/237) | 99.5 % (187/188) | 100.0 % (164/164) | 100.0 % (164/164) | 100.0 % (164/164) | 97.3 % (71/73) | 100.0 % (43/43) |
| place | 100.0 % (5/5) | 100.0 % (5/5) | — | — | — | 100.0 % (5/5) | — |
| time | 100.0 % (6/6) | 100.0 % (6/6) | — | — | — | 100.0 % (6/6) | — |
| value | 100.0 % (4/4) | 100.0 % (4/4) | — | — | — | 100.0 % (4/4) | — |

## By noise

| noise | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| no_accents | 100.0 % (12/12) | 100.0 % (8/8) | 100.0 % (7/7) | 100.0 % (7/7) | 100.0 % (7/7) | 100.0 % (5/5) | 100.0 % (2/2) |
| none | 99.6 % (225/226) | 99.4 % (179/180) | 100.0 % (143/143) | 100.0 % (143/143) | 100.0 % (143/143) | 95.2 % (79/83) | 100.0 % (39/39) |
| typos | 100.0 % (17/17) | 100.0 % (15/15) | 100.0 % (14/14) | 100.0 % (14/14) | 100.0 % (14/14) | 100.0 % (3/3) | 100.0 % (2/2) |

## Failures (5)

### `R020.de-vague_grouping` rep 1 — ambiguity_detection

> Auf DEV-NET mit der Spitzennachfrage: Kante B2C2 von 08:00 bis 09:00 auf 40 km/h begrenzt, Ampel an Kreuzung C2 in derselben Stunde auf Programm 1, Nachfrage in dieser Stunde 10 % niedriger – was macht das mit der mittleren Reisezeit?

Gold: expect `ambiguities[]` (vague grouping)

Parsed: intent `counterfactual` · network `DEV-NET` · demand `peak demand` · window 08:00–09:00 · metrics mean_travel_time
- arm `treatment`: `speed_limit(B2C2, speed=11.111, 08:00–09:00)` + `signal_program(C2, program_id=1, 08:00–09:00)` + `demand_scale(, factor=0.9, 08:00–09:00)`

### `R024.es-vague_grouping` rep 1 — ambiguity_detection

> En DEV-NET, con el tráfico de una mañana típica de lunes, ¿qué reduce más el tiempo medio de viaje: eliminar el borde B0C0 para siempre o reducirlo permanentemente a un carril?

Gold: expect `ambiguities[]` (vague grouping)

Parsed: intent `compare` · network `DEV-NET` · demand `a typical Monday morning` · metrics mean_travel_time
- arm `remove_edge`: `remove_edge(edge_id=B0C0)`
- arm `one_lane`: `set_lanes(edge_id=B0C0, lanes=1)`
- contrasts: `remove_edge` vs `base`, `one_lane` vs `base`

### `R026.en-telegraphic` rep 1 — intent

> DEV-NET low traffic. Compare mean delay: edge C0D0 closed 08:00-08:30, edge B2C2 limited 30 km/h 08:00-08:30, both together, vs normal.

Gold: intent `counterfactual` · network `DEV-NET` · demand `low traffic` · metrics mean_delay
- arm `closure`: `edge_closure(C0D0, 08:00–08:30)`
- arm `speed_limit`: `speed_limit(B2C2, speed=8.333, 08:00–08:30)`
- arm `both`: `edge_closure(C0D0, 08:00–08:30)` + `speed_limit(B2C2, speed=8.333, 08:00–08:30)`
- contrasts: `closure` vs `base`, `speed_limit` vs `base`, `both` vs `base`

Parsed: intent `compare` · network `DEV-NET` · demand `low traffic` · window 08:00–08:30 · metrics mean_delay
- arm `close_c0d0`: `edge_closure(C0D0, 08:00–08:30)`
- arm `limit_b2c2`: `speed_limit(B2C2, speed=8.333, 08:00–08:30)`
- arm `both`: `edge_closure(C0D0, 08:00–08:30)` + `speed_limit(B2C2, speed=8.333, 08:00–08:30)`
- contrasts: `close_c0d0` vs `base`, `limit_b2c2` vs `base`, `both` vs `base`

### `R041.en-messy` rep 1 — ambiguity_detection

> DEV-NET hurry up switch traffic light at junction C2 to diff program 08:00 to 09:00 report waiting time on edge C2D2

Gold: expect `ambiguities[]` (which program is not given, intent `counterfactual`)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics waiting_time
- arm `treatment`: `signal_program(C2, program_id=diff, 08:00–09:00)`

### `R044.zh` rep 1 — schema_validity, ambiguity_detection

> 在 DEV-NET 上测试平均延误：B0C0 边缘的 1 号车道在 08:00 至 08:30 关闭，08:00 至 09:00 期间需求增加 20%，C2 路口的交通信号灯在 08:00 至 09:00 期间使用方案 1。

Gold: expect `ambiguities[]` (which combinations to simulate)

Parsed: none (budget: no submit_output call)

