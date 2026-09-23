# Input Parser benchmark — v3-dev

212 requests, 212 runs (repetitions [1]), models ['deepseek/deepseek-v4.1-flash'], parser ['v3']; $0.2260, mean 4867 input / 560 output tokens; stop reasons {'output': 211, 'budget': 1}.

| Metric | Result | E5.1 threshold | Met |
|---|---|---|---|
| schema_validity | 99.5 % (211/212) | ≥ 98% | yes |
| intent | 95.6 % (152/159) | ≥ 85% | yes |
| interventions | 99.2 % (123/124) | ≥ 85% | yes |
| topology_changes | 100.0 % (124/124) | ≥ 85% | yes |
| metrics_of_interest | 99.2 % (123/124) | ≥ 85% | yes |
| ambiguity_detection | 92.0 % (81/88) | ≥ 80% | yes |
| arm_structure | 93.0 % (40/43) | ≥ 90% | yes |

Reported, not graded:

- arm_structure_single: 98.8 % (80/81)
- required_arms: 97.7 % (42/43)
- spurious_ambiguity: 2.4 % (3/124)
- used_shorthand: 100.0 % (63/63)
- network_ref: 100.0 % (124/124)
- demand_ref: 100.0 % (124/124)
- time_window: 100.0 % (124/124)
- consistency across variants: 73.3 % (33/45)

## By category

| category | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| adversarial | 100.0 % (15/15) | 100.0 % (10/10) | 100.0 % (10/10) | 100.0 % (10/10) | 100.0 % (10/10) | 100.0 % (5/5) | — |
| ambiguous | 100.0 % (44/44) | 79.2 % (19/24) | — | — | — | 90.9 % (40/44) | — |
| combined | 100.0 % (19/19) | 94.4 % (17/18) | 94.4 % (17/18) | 100.0 % (18/18) | 100.0 % (18/18) | 100.0 % (1/1) | — |
| multi_arm | 98.0 % (48/49) | 97.8 % (45/46) | 100.0 % (43/43) | 100.0 % (43/43) | 100.0 % (43/43) | 66.7 % (4/6) | 93.0 % (40/43) |
| out_of_scope | 100.0 % (12/12) | — | — | — | — | 100.0 % (12/12) | — |
| single | 100.0 % (61/61) | 100.0 % (61/61) | 100.0 % (53/53) | 100.0 % (53/53) | 98.1 % (52/53) | 100.0 % (8/8) | — |
| unintelligible | 100.0 % (12/12) | — | — | — | — | 91.7 % (11/12) | — |

## By split

| split | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| dev | 99.5 % (211/212) | 95.6 % (152/159) | 99.2 % (123/124) | 100.0 % (124/124) | 99.2 % (123/124) | 92.0 % (81/88) | 93.0 % (40/43) |

## By lang

| lang | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| ca | 100.0 % (31/31) | 95.7 % (22/23) | 100.0 % (18/18) | 100.0 % (18/18) | 100.0 % (18/18) | 92.3 % (12/13) | 100.0 % (6/6) |
| de | 100.0 % (28/28) | 95.5 % (21/22) | 100.0 % (17/17) | 100.0 % (17/17) | 100.0 % (17/17) | 90.9 % (10/11) | 85.7 % (6/7) |
| en | 98.9 % (90/91) | 94.3 % (66/70) | 98.1 % (52/53) | 100.0 % (53/53) | 98.1 % (52/53) | 94.7 % (36/38) | 94.4 % (17/18) |
| es | 100.0 % (37/37) | 100.0 % (25/25) | 100.0 % (20/20) | 100.0 % (20/20) | 100.0 % (20/20) | 88.2 % (15/17) | 100.0 % (6/6) |
| zh | 100.0 % (25/25) | 94.7 % (18/19) | 100.0 % (16/16) | 100.0 % (16/16) | 100.0 % (16/16) | 88.9 % (8/9) | 83.3 % (5/6) |

## By style

| style | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| colloquial | 100.0 % (17/17) | 100.0 % (14/14) | 100.0 % (11/11) | 100.0 % (11/11) | 100.0 % (11/11) | 100.0 % (6/6) | 100.0 % (5/5) |
| messy | 100.0 % (14/14) | 91.7 % (11/12) | 100.0 % (9/9) | 100.0 % (9/9) | 88.9 % (8/9) | 80.0 % (4/5) | 100.0 % (3/3) |
| plain | 99.3 % (146/147) | 95.3 % (102/107) | 100.0 % (81/81) | 100.0 % (81/81) | 100.0 % (81/81) | 92.4 % (61/66) | 92.6 % (25/27) |
| technical | 100.0 % (15/15) | 100.0 % (13/13) | 100.0 % (12/12) | 100.0 % (12/12) | 100.0 % (12/12) | 100.0 % (3/3) | 100.0 % (3/3) |
| telegraphic | 100.0 % (9/9) | 83.3 % (5/6) | 83.3 % (5/6) | 100.0 % (6/6) | 100.0 % (6/6) | 66.7 % (2/3) | 66.7 % (2/3) |
| verbose | 100.0 % (10/10) | 100.0 % (7/7) | 100.0 % (5/5) | 100.0 % (5/5) | 100.0 % (5/5) | 100.0 % (5/5) | 100.0 % (2/2) |

## By vague

| vague | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| grouping | 100.0 % (4/4) | — | — | — | — | 75.0 % (3/4) | — |
| none | 100.0 % (197/197) | 95.9 % (142/148) | 99.2 % (123/124) | 100.0 % (124/124) | 99.2 % (123/124) | 93.2 % (68/73) | 93.0 % (40/43) |
| place | 100.0 % (4/4) | 100.0 % (4/4) | — | — | — | 100.0 % (4/4) | — |
| time | 66.7 % (2/3) | 66.7 % (2/3) | — | — | — | 66.7 % (2/3) | — |
| value | 100.0 % (4/4) | 100.0 % (4/4) | — | — | — | 100.0 % (4/4) | — |

## By noise

| noise | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| no_accents | 100.0 % (11/11) | 100.0 % (7/7) | 100.0 % (6/6) | 100.0 % (6/6) | 100.0 % (6/6) | 100.0 % (5/5) | 100.0 % (2/2) |
| none | 99.5 % (187/188) | 95.0 % (134/141) | 99.1 % (107/108) | 100.0 % (108/108) | 99.1 % (107/108) | 91.2 % (73/80) | 92.3 % (36/39) |
| typos | 100.0 % (13/13) | 100.0 % (11/11) | 100.0 % (10/10) | 100.0 % (10/10) | 100.0 % (10/10) | 100.0 % (3/3) | 100.0 % (2/2) |

## Failures (17)

### `R004.en-telegraphic` rep 1 — intent, interventions

> DEV-NET sim: B0C0 lane 1 closed, B2C2 edge 30 km/h, 08:00–08:30. Report mean delay.

Gold: intent `run` · network `DEV-NET` · metrics mean_delay
- arm `treatment`: `lane_closure(B0C0/1, 08:00–08:30)` + `speed_limit(B2C2, speed=8.333, 08:00–08:30)`

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_delay
- ambiguities: Should the closure of lane 1 on B0C0 and the 30 km/h limit on B2C2 be applied together, or compared with each other?

### `R009.en-messy` rep 1 — metrics_of_interest

> DEV-NET, why are edges B2C2 & C2D2 so backed up 07:30-08:30??

Gold: intent `diagnose` · network `DEV-NET` · window 07:30–08:30 · metrics waiting_time

Parsed: intent `diagnose` · network `DEV-NET` · window 07:30–08:30

### `R020.de-vague_grouping` rep 1 — ambiguity_detection

> Auf DEV-NET mit der Spitzennachfrage: Kante B2C2 von 08:00 bis 09:00 auf 40 km/h begrenzt, Ampel an Kreuzung C2 in derselben Stunde auf Programm 1, Nachfrage in dieser Stunde 10 % niedriger – was macht das mit der mittleren Reisezeit?

Gold: expect `ambiguities[]` (vague grouping)

Parsed: intent `counterfactual` · network `DEV-NET` · demand `peak` · metrics mean_travel_time
- arm `treatment`: `speed_limit(B2C2, speed=11.111, 08:00–09:00)` + `signal_program(C2, program_id=1, 08:00–09:00)` + `demand_scale(, factor=0.9, 08:00–09:00)`

### `R026.en-telegraphic` rep 1 — arm_structure

> DEV-NET: mean delay vs normal. Edge C0D0 closed 08:00–08:30. Edge B2C2 limited 30 km/h 08:00–08:30. Both together.

Gold: intent `counterfactual` · network `DEV-NET` · metrics mean_delay
- arm `closure`: `edge_closure(C0D0, 08:00–08:30)`
- arm `speed_limit`: `speed_limit(B2C2, speed=8.333, 08:00–08:30)`
- arm `both`: `edge_closure(C0D0, 08:00–08:30)` + `speed_limit(B2C2, speed=8.333, 08:00–08:30)`
- contrasts: `closure` vs `base`, `speed_limit` vs `base`, `both` vs `base`

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_delay
- arm `treatment`: `edge_closure(C0D0, 08:00–08:30)` + `speed_limit(B2C2, speed=8.333, 08:00–08:30)`

### `R029.en-vague_time` rep 1 — schema_validity, intent, ambiguity_detection

> On DEV-NET, is it less harmful to close edge B1C1 early in the morning for a short while or later in the morning for a similar duration? Compare each against no closure, by mean delay.

Gold: expect `ambiguities[]` (vague time, intent `compare`)

Parsed: none (budget: validation failed: 1 validation error for Question
  Value error, contrasts compare named arms: give the arms [type=value_error, input_value={'ambiguities': ['When do... 'DEV-NET', 'text': '.'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/value_error)

### `R040.zh` rep 1 — intent

> 在 08:00 至 09:00 期间，在 DEV-NET 中增加交通流量，并报告瞬移（teleport）次数。

Gold: expect `ambiguities[]` (how much more demand is not given, intent `run`)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics teleports
- ambiguities: By what factor should the traffic demand be increased during 08:00 to 09:00?

### `R041` rep 1 — intent

> On DEV-NET, switch the traffic light at junction C2 to a different program from 08:00 to 09:00 and report the waiting time on edge C2D2.

Gold: expect `ambiguities[]` (which program is not given, intent `run`)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics waiting_time
- ambiguities: Which traffic light program id should junction C2 be switched to from 08:00 to 09:00?

### `R041.ca` rep 1 — intent

> A DEV-NET, canvia el semàfor de la intersecció C2 a un programa diferent entre les 08:00 i les 09:00 i informa del temps d'espera a l'aresta C2D2.

Gold: expect `ambiguities[]` (which program is not given, intent `run`)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics waiting_time
- ambiguities: Which signal program id should junction C2 be switched to between 08:00 and 09:00?

### `R041.de` rep 1 — intent

> Stelle auf DEV-NET das Ampelsignal an Kreuzung C2 von 08:00 bis 09:00 auf ein anderes Programm um und gib die Wartezeit auf Kante C2D2 aus.

Gold: expect `ambiguities[]` (which program is not given, intent `run`)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics waiting_time
- ambiguities: Which signal program should junction C2 be switched to?

### `R041.en-messy` rep 1 — intent

> DEV-NET hurry up switch traffic light at junction C2 to diff program 08:00 to 09:00 report waiting time on edge C2D2

Gold: expect `ambiguities[]` (which program is not given, intent `run`)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics waiting_time
- ambiguities: Which signal program id should junction C2 be switched to from 08:00 to 09:00?

### `R044.es-telegraphic` rep 1 — ambiguity_detection

> Prueba DEV-NET: retardo medio. Carril 1 borde B0C0 cerrado 08:00-08:30. Demanda +20% 08:00-09:00. Semáforo C2 programa 1 08:00-09:00.

Gold: expect `ambiguities[]` (which combinations to simulate)

Parsed: intent `run` · network `DEV-NET` · metrics mean_delay
- arm `treatment`: `lane_closure(B0C0/1, 08:00–08:30)` + `demand_scale(, factor=1.2, 08:00–09:00)` + `signal_program(C2, program_id=1, 08:00–09:00)`

### `R044.zh` rep 1 — ambiguity_detection

> 在 DEV-NET 上测试平均延误：B0C0 边缘的 1 号车道在 08:00 至 08:30 关闭，08:00 至 09:00 期间需求增加 20%，C2 路口的交通信号灯在 08:00 至 09:00 期间使用方案 1。

Gold: expect `ambiguities[]` (which combinations to simulate)

Parsed: intent `run` · network `DEV-NET` · metrics mean_delay
- arm `treatment`: `lane_closure(B0C0/1, 08:00–08:30)` + `demand_scale(, factor=1.2, 08:00–09:00)` + `signal_program(C2, program_id=1, 08:00–09:00)`

### `R050` rep 1 — ambiguity_detection

> Is closing lane 0 of edge B0C0 on DEV-NET from 08:00 to 08:30 a good idea, or should I do something else?

Gold: expect `ambiguities[]` (the alternative is not given)

Parsed: intent `counterfactual` · network `DEV-NET`
- arm `treatment`: `lane_closure(B0C0/0, 08:00–08:30)`

### `R050.es-messy` rep 1 — ambiguity_detection

> ¿cierra carril 0 de borde B0C0 en DEV-NET de 08:00 a 08:30 es buena idea o hago otra cosa?

Gold: expect `ambiguities[]` (the alternative is not given)

Parsed: intent `counterfactual` · network `DEV-NET`
- arm `treatment`: `lane_closure(B0C0/0, 08:00–08:30)`

### `R054.ca` rep 1 — ambiguity_detection

> Simula el trànsit a la xarxa xx 0800 zz.

Gold: expect `ambiguities[]` (unintelligible)

Parsed: intent `run` · network `xx 0800 zz`

### `R065.de` rep 1 — arm_structure

> Auf DEV-NET habe ich vier Maßnahmen und drei Netzänderungen; ich möchte nicht alle Kombinationen, sondern nur die unten genannten, alle gemessen an der mittleren Reisezeit. Die Maßnahmen: A, Spur 1 der Kante B0C0 von 08:00 bis 08:30 schließen; B, Kante B2C2 von 08:00 bis 09:00 auf 30 km/h begrenzen; C, Ampel an Knoten C2 von 08:00 bis 09:00 auf Programm 1 umstellen; D, die neue Kante NEW3 von 08:00 bis 09:00 auf 30 km/h begrenzen. Die Änderungen: 1, Kante C0D0 auf drei Spuren verbreitern; 2, Kante B1C1 dauerhaft entfernen; 3, eine zweispurige Kante NEW3 von Knoten B1 zu Knoten C2 mit 50 km/h Höchstgeschwindigkeit bauen. Erstens: Was ist schneller, A oder B? Vergleichen Sie diese beiden nur miteinander. Mit Änderung 1 kann man A noch durchführen, aber nicht B, wohl aber C: Was ist mit Änderung 1 schneller, A oder C? Funktioniert B mit Änderung 2 genauso gut wie auf dem heutigen Netz? Und schließlich: Hilft Änderung 3 allein im Vergleich zu heute, und verbessert D zusätzlich zu Änderung 3 das Ergebnis gegenüber Änderung 3 allein?

Gold: intent `compare` · network `DEV-NET` · metrics mean_travel_time
- arm `a`: `lane_closure(B0C0/1, 08:00–08:30)`
- arm `b`: `speed_limit(B2C2, speed=8.333, 08:00–09:00)`
- arm `widened_a`: `set_lanes(edge_id=C0D0, lanes=3)` + `lane_closure(B0C0/1, 08:00–08:30)`
- arm `widened_c`: `set_lanes(edge_id=C0D0, lanes=3)` + `signal_program(C2, program_id=1, 08:00–09:00)`
- arm `removed_b`: `remove_edge(edge_id=B1C1)` + `speed_limit(B2C2, speed=8.333, 08:00–09:00)`
- arm `new_edge`: `add_edge(from_junction=B1, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW3)`
- arm `new_edge_d`: `add_edge(from_junction=B1, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW3)` + `speed_limit(NEW3, speed=8.333, 08:00–09:00)`
- contrasts: `a` vs `b`, `widened_a` vs `widened_c`, `removed_b` vs `b`, `new_edge` vs `base`, `new_edge_d` vs `new_edge`

Parsed: intent `compare` · network `DEV-NET` · metrics mean_travel_time
- arm `a_closure`: `lane_closure(B0C0/1, 08:00–08:30)`
- arm `b_speed`: `speed_limit(B2C2, speed=8.333, 08:00–09:00)`
- arm `chg1_a`: `set_lanes(edge_id=C0D0, lanes=3)` + `lane_closure(B0C0/1, 08:00–08:30)`
- arm `chg1_c`: `set_lanes(edge_id=C0D0, lanes=3)` + `signal_program(C2, program_id=1, 08:00–09:00)`
- arm `chg2_b`: `remove_edge(edge_id=B1C1)` + `speed_limit(B2C2, speed=8.333, 08:00–09:00)`
- arm `chg3`: `add_edge(from_junction=B1, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW3)`
- arm `chg3_d`: `add_edge(from_junction=B1, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW3)` + `speed_limit(NEW3, speed=8.333, 08:00–09:00)`
- contrasts: `a_closure` vs `b_speed`, `chg1_a` vs `chg1_c`, `chg2_b` vs `base`, `chg3` vs `base`, `chg3_d` vs `chg3`

### `R065.zh` rep 1 — arm_structure

> 在 DEV-NET 网络中，我有四项措施和三项网络变更，且仅关注以下特定组合，所有比较均基于平均行程时间。措施包括：A（08:00 至 08:30 关闭边 B0C0 的第 1 车道）、B（08:00 至 09:00 将边 B2C2 限速至 30 km/h）、C（08:00 至 09:00 将路口 C2 的交通信号灯切换至方案 1）、D（08:00 至 09:00 将新边 NEW3 限速至 30 km/h）。网络变更包括：1（将边 C0D0 拓宽为三条车道）、2（永久移除边 B1C1）、3（从路口 B1 到路口 C2 新建一条限速 50 km/h 的双车道边 NEW3）。首先，仅比较措施 A 和 B，哪一项更快？在应用变更 1 的情况下，措施 A 仍可实施但措施 B 无法实施，而措施 C 可以实施，此时在变更 1 生效的前提下，比较措施 A 和 C，哪一项更快？在应用变更 2 的情况下，措施 B 的表现是否与当前网络相同？最后，仅应用变更 3 相比当前网络是否有改善？若将措施 D 与变更 3 结合，其效果是否优于仅应用变更 3？

Gold: intent `compare` · network `DEV-NET` · metrics mean_travel_time
- arm `a`: `lane_closure(B0C0/1, 08:00–08:30)`
- arm `b`: `speed_limit(B2C2, speed=8.333, 08:00–09:00)`
- arm `widened_a`: `set_lanes(edge_id=C0D0, lanes=3)` + `lane_closure(B0C0/1, 08:00–08:30)`
- arm `widened_c`: `set_lanes(edge_id=C0D0, lanes=3)` + `signal_program(C2, program_id=1, 08:00–09:00)`
- arm `removed_b`: `remove_edge(edge_id=B1C1)` + `speed_limit(B2C2, speed=8.333, 08:00–09:00)`
- arm `new_edge`: `add_edge(from_junction=B1, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW3)`
- arm `new_edge_d`: `add_edge(from_junction=B1, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW3)` + `speed_limit(NEW3, speed=8.333, 08:00–09:00)`
- contrasts: `a` vs `b`, `widened_a` vs `widened_c`, `removed_b` vs `b`, `new_edge` vs `base`, `new_edge_d` vs `new_edge`

Parsed: intent `compare` · network `DEV-NET` · metrics mean_travel_time
- arm `a`: `lane_closure(B0C0/1, 08:00–08:30)`
- arm `b`: `speed_limit(B2C2, speed=8.333, 08:00–09:00)`
- arm `change1_a`: `set_lanes(edge_id=C0D0, lanes=3)` + `lane_closure(B0C0/1, 08:00–08:30)`
- arm `change1_c`: `set_lanes(edge_id=C0D0, lanes=3)` + `signal_program(C2, program_id=1, 08:00–09:00)`
- arm `change2_b`: `remove_edge(edge_id=B1C1)` + `speed_limit(B2C2, speed=8.333, 08:00–09:00)`
- arm `change3`: `add_edge(from_junction=B1, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW3)`
- arm `change3_d`: `add_edge(from_junction=B1, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW3)` + `speed_limit(NEW3, speed=8.333, 08:00–09:00)`
- contrasts: `a` vs `b`, `change1_a` vs `change1_c`, `change2_b` vs `base`, `change3` vs `base`, `change3_d` vs `change3`

