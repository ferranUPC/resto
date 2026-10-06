# Input Parser benchmark — v8-dev

255 requests, 255 runs (repetitions [1]), models ['deepseek/deepseek-v4.1-flash'], parser ['v8']; estimated $0.3323 · real $0.2112, mean 5381 input / 827 output tokens; stop reasons {'output': 251, 'budget': 4}.

| Metric | Result | 95 % CI by concept | E5.1 threshold | Met |
|---|---|---|---|---|
| schema_validity | 98.4 % (251/255) | 96–100 % (54 concepts) | ≥ 98% | yes |
| intent | 95.6 % (194/203) | 90–99 % (42 concepts) | ≥ 85% | yes |
| interventions | 97.0 % (159/164) | 94–99 % (36 concepts) | ≥ 85% | yes |
| topology_changes | 98.8 % (162/164) | 96–100 % (36 concepts) | ≥ 85% | yes |
| metrics_of_interest | 98.8 % (162/164) | 96–100 % (36 concepts) | ≥ 85% | yes |
| ambiguity_detection | 94.5 % (86/91) | 90–99 % (35 concepts) | ≥ 80% | yes |
| arm_structure | 90.7 % (39/43) | 77–100 % (10 concepts) | ≥ 90% | yes |

Met is judged on the point estimate. The interval resamples whole concepts (bootstrap), so it shows how much the result could move with another draw of concepts; when every concept is right it is the rule-of-three bound 1 − 3/n. `intent` also accepts the second reading listed in `concepts.ALSO_ACCEPTED`; `intent_strict` below is against the gold intent alone.

Reported, not graded:

- intent_strict: 95.6 % (194/203)
- arm_structure_single: 96.7 % (117/121)
- required_arms: 93.0 % (40/43)
- spurious_ambiguity: 10.5 % (17/162)
- used_shorthand: 100.0 % (80/80)
- network_ref: 97.5 % (158/162)
- demand_ref: 93.2 % (151/162)
- network_only: 100.0 % (162/162)
- time_window: 88.3 % (143/162)
- consistency across variants: 72.2 % (39/54)

## By category

| category | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| adversarial | 100.0 % (15/15) | 100.0 % (10/10) | 100.0 % (10/10) | 100.0 % (10/10) | 100.0 % (10/10) | 100.0 % (5/5) | — |
| ambiguous | 95.5 % (42/44) | 100.0 % (24/24) | — | — | — | 93.2 % (41/44) | — |
| combined | 100.0 % (18/18) | 100.0 % (18/18) | 100.0 % (18/18) | 100.0 % (18/18) | 100.0 % (18/18) | — | — |
| multi_arm | 95.9 % (47/49) | 95.7 % (44/46) | 93.0 % (40/43) | 95.3 % (41/43) | 95.3 % (41/43) | 66.7 % (4/6) | 90.7 % (39/43) |
| out_of_scope | 100.0 % (12/12) | — | — | — | — | 100.0 % (12/12) | — |
| single | 100.0 % (105/105) | 93.3 % (98/105) | 97.8 % (91/93) | 100.0 % (93/93) | 100.0 % (93/93) | 100.0 % (12/12) | — |
| unintelligible | 100.0 % (12/12) | — | — | — | — | 100.0 % (12/12) | — |

## By split

| split | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| dev | 98.4 % (251/255) | 95.6 % (194/203) | 97.0 % (159/164) | 98.8 % (162/164) | 98.8 % (162/164) | 94.5 % (86/91) | 90.7 % (39/43) |

## By lang

| lang | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| ca | 100.0 % (38/38) | 96.7 % (29/30) | 95.8 % (23/24) | 100.0 % (24/24) | 100.0 % (24/24) | 100.0 % (14/14) | 83.3 % (5/6) |
| de | 100.0 % (36/36) | 96.7 % (29/30) | 96.0 % (24/25) | 100.0 % (25/25) | 100.0 % (25/25) | 90.9 % (10/11) | 100.0 % (7/7) |
| en | 99.1 % (105/106) | 96.5 % (83/86) | 100.0 % (67/67) | 100.0 % (67/67) | 100.0 % (67/67) | 94.9 % (37/39) | 94.4 % (17/18) |
| es | 97.7 % (43/44) | 93.8 % (30/32) | 96.2 % (25/26) | 96.2 % (25/26) | 96.2 % (25/26) | 94.4 % (17/18) | 83.3 % (5/6) |
| zh | 93.5 % (29/31) | 92.0 % (23/25) | 90.9 % (20/22) | 95.5 % (21/22) | 95.5 % (21/22) | 88.9 % (8/9) | 83.3 % (5/6) |

## By style

| style | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| colloquial | 100.0 % (22/22) | 100.0 % (19/19) | 93.8 % (15/16) | 100.0 % (16/16) | 100.0 % (16/16) | 100.0 % (6/6) | 100.0 % (5/5) |
| messy | 100.0 % (16/16) | 100.0 % (14/14) | 100.0 % (11/11) | 100.0 % (11/11) | 100.0 % (11/11) | 80.0 % (4/5) | 100.0 % (3/3) |
| plain | 98.3 % (173/176) | 95.6 % (131/137) | 96.3 % (103/107) | 98.1 % (105/107) | 98.1 % (105/107) | 95.7 % (66/69) | 85.2 % (23/27) |
| technical | 100.0 % (18/18) | 87.5 % (14/16) | 100.0 % (15/15) | 100.0 % (15/15) | 100.0 % (15/15) | 100.0 % (3/3) | 100.0 % (3/3) |
| telegraphic | 100.0 % (10/10) | 85.7 % (6/7) | 100.0 % (7/7) | 100.0 % (7/7) | 100.0 % (7/7) | 100.0 % (3/3) | 100.0 % (3/3) |
| verbose | 92.3 % (12/13) | 100.0 % (10/10) | 100.0 % (8/8) | 100.0 % (8/8) | 100.0 % (8/8) | 80.0 % (4/5) | 100.0 % (2/2) |

## By vague

| vague | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| grouping | 100.0 % (3/3) | — | — | — | — | 33.3 % (1/3) | — |
| none | 98.3 % (233/237) | 95.2 % (179/188) | 97.0 % (159/164) | 98.8 % (162/164) | 98.8 % (162/164) | 95.9 % (70/73) | 90.7 % (39/43) |
| place | 100.0 % (5/5) | 100.0 % (5/5) | — | — | — | 100.0 % (5/5) | — |
| time | 100.0 % (6/6) | 100.0 % (6/6) | — | — | — | 100.0 % (6/6) | — |
| value | 100.0 % (4/4) | 100.0 % (4/4) | — | — | — | 100.0 % (4/4) | — |

## By noise

| noise | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| no_accents | 100.0 % (12/12) | 100.0 % (8/8) | 100.0 % (7/7) | 100.0 % (7/7) | 100.0 % (7/7) | 100.0 % (5/5) | 100.0 % (2/2) |
| none | 98.2 % (222/226) | 95.6 % (172/180) | 97.2 % (139/143) | 98.6 % (141/143) | 98.6 % (141/143) | 94.0 % (78/83) | 92.3 % (36/39) |
| typos | 100.0 % (17/17) | 93.3 % (14/15) | 92.9 % (13/14) | 100.0 % (14/14) | 100.0 % (14/14) | 100.0 % (3/3) | 50.0 % (1/2) |

## Failures (18)

### `R001.en-telegraphic` rep 1 — intent

> DEV-NET, Monday morning traffic. Close lane 1, edge B0C0, 08:00–08:30. What is mean travel time?

Gold: intent `compare` · network `DEV-NET` · demand `typical Monday morning traffic` · metrics mean_travel_time
- arm `treatment`: `lane_closure(B0C0/1, 08:00–08:30)`

Parsed: intent `run` · network `DEV-NET` · demand `Monday morning traffic` · metrics mean_travel_time
- arm `treatment`: `lane_closure(B0C0/1, 08:00–08:30)`

### `R001.zh` rep 1 — interventions

> 在 DEV-NET 网络上，针对典型周一早高峰的交通状况，如果将边 B0C0 的第 1 车道在 08:00 至 08:30 期间封闭，平均行程时间会发生什么变化？

Gold: intent `compare` · network `DEV-NET` · demand `typical Monday morning traffic` · metrics mean_travel_time
- arm `treatment`: `lane_closure(B0C0/1, 08:00–08:30)`

Parsed: intent `compare` · network `DEV-NET` · demand `typical Monday morning peak` · metrics mean_travel_time
- arm `treatment`: `lane_closure(B0C0/0, 08:00–08:30)`

### `R006.de-technical` rep 1 — intent

> Berechne auf DEV-NET die mittlere Fahrzeit für die Kante C1C2 im Zeitfenster 08:00–09:00.

Gold: intent `describe` · network `DEV-NET` · window 08:00–09:00 · metrics travel_time

Parsed: intent `run` · network `DEV-NET` · window 08:00–09:00 · metrics travel_time

### `R011.en-technical` rep 1 — intent

> Simulate DEV-NET with random traffic. Apply a 30% demand increase between 08:00 and 09:00. Report the resulting teleport count.

Gold: intent `compare` · network `DEV-NET` · demand `random traffic` · metrics teleports
- arm `treatment`: `demand_scale(, factor=1.3, 08:00–09:00)`

Parsed: intent `run` · network `DEV-NET` · demand `random traffic` · metrics teleports
- arm `treatment`: `demand_scale(, factor=1.3, 08:00–09:00)`

### `R020.de-vague_grouping` rep 1 — ambiguity_detection

> Auf DEV-NET mit der Spitzennachfrage: Kante B2C2 von 08:00 bis 09:00 auf 40 km/h begrenzt, Ampel an Kreuzung C2 in derselben Stunde auf Programm 1, Nachfrage in dieser Stunde 10 % niedriger – was macht das mit der mittleren Reisezeit?

Gold: expect `ambiguities[]` (vague grouping)

Parsed: intent `compare` · network `DEV-NET` · demand `peak demand` · window 08:00–09:00 · metrics mean_travel_time
- arm `treatment`: `speed_limit(B2C2, speed=11.111, 08:00–09:00)` + `signal_program(C2, program_id=1, 08:00–09:00)` + `demand_scale(, factor=0.9, 08:00–09:00)`

### `R024.es-vague_grouping` rep 1 — ambiguity_detection

> En DEV-NET, con el tráfico de una mañana típica de lunes, ¿qué reduce más el tiempo medio de viaje: eliminar el borde B0C0 para siempre o reducirlo permanentemente a un carril?

Gold: expect `ambiguities[]` (vague grouping)

Parsed: intent `compare` · network `DEV-NET` · demand `a typical Monday morning` · metrics mean_travel_time
- arm `remove_edge`: `remove_edge(edge_id=B0C0)`
- arm `reduce_to_one_lane`: `set_lanes(edge_id=B0C0, lanes=1)`
- contrasts: `remove_edge` vs `base`, `reduce_to_one_lane` vs `base`

### `R025.ca-typos` rep 1 — interventions, arm_structure

> A DEV-NET en hora punta, compara tres oppcions amb la situació actual mitjançant el retard mitjà: tancar el carril 1 de l'aresta B0C0 de 08:00 a 08:30; limitar l'aresta A0B0 a 30 km/h durant el mateix període; i fer ambdós accions juntes.

Gold: intent `compare` · network `DEV-NET` · demand `peak` · metrics mean_delay
- arm `closure`: `lane_closure(B0C0/1, 08:00–08:30)`
- arm `speed_limit`: `speed_limit(A0B0, speed=8.333, 08:00–08:30)`
- arm `both`: `lane_closure(B0C0/1, 08:00–08:30)` + `speed_limit(A0B0, speed=8.333, 08:00–08:30)`
- contrasts: `closure` vs `base`, `speed_limit` vs `base`, `both` vs `base`

Parsed: intent `compare` · network `DEV-NET` · demand `rush-hour traffic` · window 08:00–09:00 · metrics mean_delay
- arm `close_lane_B0C0`: `lane_closure(B0C0/1, 08:00–09:00)`
- arm `speed_limit_A0B0`: `speed_limit(A0B0, speed=8.333, 08:00–09:00)`
- arm `both_together`: `lane_closure(B0C0/1, 08:00–09:00)` + `speed_limit(A0B0, speed=8.333, 08:00–09:00)`
- contrasts: `close_lane_B0C0` vs `base`, `speed_limit_A0B0` vs `base`, `both_together` vs `base`

### `R041.en-messy` rep 1 — ambiguity_detection

> DEV-NET hurry up switch traffic light at junction C2 to diff program 08:00 to 09:00 report waiting time on edge C2D2

Gold: expect `ambiguities[]` (which program is not given, intent `run`)

Parsed: intent `run` · network `DEV-NET` · metrics waiting_time
- arm `treatment`: `signal_program(C2, program_id=diff, 08:00–09:00)`

### `R044.zh` rep 1 — schema_validity, ambiguity_detection

> 在 DEV-NET 上测试平均延误：B0C0 边缘的 1 号车道在 08:00 至 08:30 关闭，08:00 至 09:00 期间需求增加 20%，C2 路口的交通信号灯在 08:00 至 09:00 期间使用方案 1。

Gold: expect `ambiguities[]` (which combinations to simulate)

Parsed: none (budget: no submit_output call)

### `R050.en-verbose` rep 1 — schema_validity, ambiguity_detection

> Hey there, I'm a traffic engineer currently working on optimizing the flow for the DEV-NET simulation environment, and I've been reviewing the current lane configurations for the morning peak hour. I'm specifically looking at the segment connecting node B0 to node C0, and I need your expert opinion on a potential adjustment. Could you evaluate whether it would be beneficial to close lane 0 of edge B0C0 on the DEV-NET network starting at 08:00 and keeping it closed until 08:30? If you determine that this specific closure isn't the best strategy for managing the traffic during that window, please let me know what alternative actions I should consider instead.

Gold: expect `ambiguities[]` (the alternative is not given)

Parsed: none (budget: validation failed: 2 validation errors for Question
text
  Field required [type=missing, input_value={'arguments': '{"text": "..."network_only": false}'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
intent
  Field required [type=missing, input_value={'arguments': '{"text": "..."network_only": false}'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing)

### `R065` rep 1 — arm_structure

> On DEV-NET at peak I have four measures and three network changes, and I do not want every combination, only the ones below, all by mean travel time. The measures: A, closing lane 1 of edge B0C0 from 08:00 to 08:30; B, limiting edge B2C2 to 30 km/h from 08:00 to 09:00; C, switching the traffic light at junction C2 to program 1 from 08:00 to 09:00; D, limiting the new edge NEW3 to 30 km/h from 08:00 to 09:00. The changes: 1, widening edge C0D0 to three lanes; 2, removing edge B1C1 for good; 3, building a two-lane edge NEW3 from junction B1 to junction C2 with a 50 km/h limit. First, which is faster, A or B? Compare those two with each other only. With change 1 we can still do A but not B, although we can do C: with change 1 in place, which is faster, A or C? With change 2, does B work as well as it does on today's network? Finally, does change 3 on its own help compared with today, and does adding D to change 3 improve on change 3 alone?

Gold: intent `compare` · network `DEV-NET` · demand `peak` · metrics mean_travel_time
- arm `a`: `lane_closure(B0C0/1, 08:00–08:30)`
- arm `b`: `speed_limit(B2C2, speed=8.333, 08:00–09:00)`
- arm `widened_a`: `set_lanes(edge_id=C0D0, lanes=3)` + `lane_closure(B0C0/1, 08:00–08:30)`
- arm `widened_c`: `set_lanes(edge_id=C0D0, lanes=3)` + `signal_program(C2, program_id=1, 08:00–09:00)`
- arm `removed_b`: `remove_edge(edge_id=B1C1)` + `speed_limit(B2C2, speed=8.333, 08:00–09:00)`
- arm `new_edge`: `add_edge(from_junction=B1, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW3)`
- arm `new_edge_d`: `add_edge(from_junction=B1, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW3)` + `speed_limit(NEW3, speed=8.333, 08:00–09:00)`
- contrasts: `a` vs `b`, `widened_a` vs `widened_c`, `removed_b` vs `b`, `new_edge` vs `base`, `new_edge_d` vs `new_edge`

Parsed: intent `compare` · network `DEV-NET` · demand `peak traffic` · metrics mean_travel_time
- arm `a`: `lane_closure(B0C0/1, 08:00–08:30)`
- arm `b`: `speed_limit(B2C2, speed=8.333, 08:00–09:00)`
- arm `change1_a`: `set_lanes(edge_id=C0D0, lanes=3)` + `lane_closure(B0C0/1, 08:00–08:30)`
- arm `change1_c`: `set_lanes(edge_id=C0D0, lanes=3)` + `signal_program(C2, program_id=1, 08:00–09:00)`
- arm `change2_b`: `remove_edge(edge_id=B1C1)` + `speed_limit(B2C2, speed=8.333, 08:00–09:00)`
- arm `change3`: `add_edge(from_junction=B1, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW3)`
- arm `change3_d`: `add_edge(from_junction=B1, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW3)` + `speed_limit(NEW3, speed=8.333, 08:00–09:00)`
- contrasts: `a` vs `b`, `change1_a` vs `change1_c`, `change2_b` vs `base`, `change3` vs `base`, `change3_d` vs `change3`

### `R065.es` rep 1 — schema_validity, intent, interventions, topology_changes, metrics_of_interest, arm_structure

> En DEV-NET en horario punta tengo cuatro medidas y tres cambios de red, y no quiero todas las combinaciones, solo las siguientes, todas expresadas en tiempo medio de viaje. Las medidas: A, cerrar el carril 1 del borde B0C0 de 08:00 a 08:30; B, limitar el borde B2C2 a 30 km/h de 08:00 a 09:00; C, cambiar el semáforo en la intersección C2 al programa 1 de 08:00 a 09:00; D, limitar el nuevo borde NEW3 a 30 km/h de 08:00 a 09:00. Los cambios: 1, ensanchar el borde C0D0 a tres carriles; 2, eliminar el borde B1C1 de forma permanente; 3, construir un borde de dos carriles NEW3 desde la intersección B1 hasta la intersección C2 con un límite de 50 km/h. Primero, ¿cuál es más rápido, A o B? Compara solo esos dos entre sí. Con el cambio 1 podemos seguir haciendo A pero no B, aunque sí podemos hacer C: con el cambio 1 aplicado, ¿cuál es más rápido, A o C? Con el cambio 2, ¿funciona B igual que en la red de hoy? Finalmente, ¿el cambio 3 por sí solo ayuda comparado con hoy, y ¿añadir D al cambio 3 mejora respecto al cambio 3 solo?

Gold: intent `compare` · network `DEV-NET` · demand `peak` · metrics mean_travel_time
- arm `a`: `lane_closure(B0C0/1, 08:00–08:30)`
- arm `b`: `speed_limit(B2C2, speed=8.333, 08:00–09:00)`
- arm `widened_a`: `set_lanes(edge_id=C0D0, lanes=3)` + `lane_closure(B0C0/1, 08:00–08:30)`
- arm `widened_c`: `set_lanes(edge_id=C0D0, lanes=3)` + `signal_program(C2, program_id=1, 08:00–09:00)`
- arm `removed_b`: `remove_edge(edge_id=B1C1)` + `speed_limit(B2C2, speed=8.333, 08:00–09:00)`
- arm `new_edge`: `add_edge(from_junction=B1, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW3)`
- arm `new_edge_d`: `add_edge(from_junction=B1, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW3)` + `speed_limit(NEW3, speed=8.333, 08:00–09:00)`
- contrasts: `a` vs `b`, `widened_a` vs `widened_c`, `removed_b` vs `b`, `new_edge` vs `base`, `new_edge_d` vs `new_edge`

Parsed: none (budget: no submit_output call)

### `R065.zh` rep 1 — schema_validity, intent, interventions, topology_changes, metrics_of_interest, arm_structure

> 在 DEV-NET 的高峰时段，我有四项措施和三项网络变更，且仅关注以下组合，所有指标均以平均行程时间衡量。措施包括：A，在 08:00 至 08:30 期间关闭边 B0C0 的第 1 车道；B，在 08:00 至 09:00 期间将边 B2C2 限速至 30 km/h；C，在 08:00 至 09:00 期间将路口 C2 的交通信号灯切换为方案 1；D，在 08:00 至 09:00 期间将新边 NEW3 限速至 30 km/h。网络变更包括：1，将边 C0D0 拓宽为三条车道；2，永久移除边 B1C1；3，在路口 B1 至 C2 之间新建一条限速 50 km/h 的双车道边 NEW3。首先，仅比较 A 和 B，哪一项更快？仅比较这两项。在变更 1 实施的情况下，可以执行 A 但不能执行 B，但可以执行 C，此时 A 和 C 哪一项更快？在变更 2 实施的情况下，B 的效果是否与当前网络相同？最后，变更 3 单独实施是否比当前网络有所改善？将 D 与变更 3 结合实施，是否比仅实施变更 3 有所改善？

Gold: intent `compare` · network `DEV-NET` · demand `peak` · metrics mean_travel_time
- arm `a`: `lane_closure(B0C0/1, 08:00–08:30)`
- arm `b`: `speed_limit(B2C2, speed=8.333, 08:00–09:00)`
- arm `widened_a`: `set_lanes(edge_id=C0D0, lanes=3)` + `lane_closure(B0C0/1, 08:00–08:30)`
- arm `widened_c`: `set_lanes(edge_id=C0D0, lanes=3)` + `signal_program(C2, program_id=1, 08:00–09:00)`
- arm `removed_b`: `remove_edge(edge_id=B1C1)` + `speed_limit(B2C2, speed=8.333, 08:00–09:00)`
- arm `new_edge`: `add_edge(from_junction=B1, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW3)`
- arm `new_edge_d`: `add_edge(from_junction=B1, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW3)` + `speed_limit(NEW3, speed=8.333, 08:00–09:00)`
- contrasts: `a` vs `b`, `widened_a` vs `widened_c`, `removed_b` vs `b`, `new_edge` vs `base`, `new_edge_d` vs `new_edge`

Parsed: none (budget: no submit_output call)

### `R067.de-colloquial` rep 1 — interventions

> Richte mir auf DEV-NET ein Szenario mit der Peak-Nachfrage ein, bei dem Spur 1 der Kante B0C0 von 07:30 bis 08:00 gesperrt ist, damit ich es später nutzen kann.

Gold: intent `run` · network `DEV-NET` · demand `peak`
- arm `treatment`: `lane_closure(B0C0/1, 07:30–08:00)`

Parsed: intent `run` · network `DEV-NET` · demand `peak demand`
- arm `treatment`: `lane_closure(B0C0/0, 07:30–08:00)`

### `R080` rep 1 — intent

> On a 4x4 grid, what is the mean delay with low traffic?

Gold: intent `describe` · network `4x4 grid` · demand `low traffic` · metrics mean_delay

Parsed: intent `run` · network `a 4x4 grid` · demand `low traffic` · metrics mean_delay

### `R080.ca-typos` rep 1 — intent

> En una graella de 4x4, quina és la mitjana de retard amb tràànsit baix?

Gold: intent `describe` · network `4x4 grid` · demand `low traffic` · metrics mean_delay

Parsed: intent `run` · network `a 4x4 grid` · demand `low traffic` · metrics mean_delay

### `R080.es` rep 1 — intent

> En una cuadrícula de 4x4, ¿cuál es el retraso medio con tráfico bajo?

Gold: intent `describe` · network `4x4 grid` · demand `low traffic` · metrics mean_delay

Parsed: intent `run` · network `4x4 grid` · demand `low traffic` · metrics mean_delay

### `R080.zh` rep 1 — intent

> 在 4x4 网格中，低流量下的平均延迟是多少？

Gold: intent `describe` · network `4x4 grid` · demand `low traffic` · metrics mean_delay

Parsed: intent `run` · network `4x4 grid` · demand `low traffic` · metrics mean_delay

