# Input Parser benchmark — v4-dev

212 requests, 212 runs (repetitions [1]), models ['deepseek/deepseek-v4.1-flash'], parser ['v4']; $0.2270, mean 4991 input / 537 output tokens; stop reasons {'output': 212}.

| Metric | Result | E5.1 threshold | Met |
|---|---|---|---|
| schema_validity | 100.0 % (212/212) | ≥ 98% | yes |
| intent | 100.0 % (159/159) | ≥ 85% | yes |
| interventions | 100.0 % (124/124) | ≥ 85% | yes |
| topology_changes | 100.0 % (124/124) | ≥ 85% | yes |
| metrics_of_interest | 100.0 % (124/124) | ≥ 85% | yes |
| ambiguity_detection | 98.9 % (87/88) | ≥ 80% | yes |
| arm_structure | 95.3 % (41/43) | ≥ 90% | yes |

Reported, not graded:

- arm_structure_single: 100.0 % (81/81)
- required_arms: 97.7 % (42/43)
- spurious_ambiguity: 0.0 % (0/124)
- used_shorthand: 100.0 % (63/63)
- network_ref: 100.0 % (124/124)
- demand_ref: 100.0 % (124/124)
- time_window: 100.0 % (124/124)
- consistency across variants: 91.1 % (41/45)

## By category

| category | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| adversarial | 100.0 % (15/15) | 100.0 % (10/10) | 100.0 % (10/10) | 100.0 % (10/10) | 100.0 % (10/10) | 100.0 % (5/5) | — |
| ambiguous | 100.0 % (44/44) | 100.0 % (24/24) | — | — | — | 100.0 % (44/44) | — |
| combined | 100.0 % (19/19) | 100.0 % (18/18) | 100.0 % (18/18) | 100.0 % (18/18) | 100.0 % (18/18) | 100.0 % (1/1) | — |
| multi_arm | 100.0 % (49/49) | 100.0 % (46/46) | 100.0 % (43/43) | 100.0 % (43/43) | 100.0 % (43/43) | 83.3 % (5/6) | 95.3 % (41/43) |
| out_of_scope | 100.0 % (12/12) | — | — | — | — | 100.0 % (12/12) | — |
| single | 100.0 % (61/61) | 100.0 % (61/61) | 100.0 % (53/53) | 100.0 % (53/53) | 100.0 % (53/53) | 100.0 % (8/8) | — |
| unintelligible | 100.0 % (12/12) | — | — | — | — | 100.0 % (12/12) | — |

## By split

| split | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| dev | 100.0 % (212/212) | 100.0 % (159/159) | 100.0 % (124/124) | 100.0 % (124/124) | 100.0 % (124/124) | 98.9 % (87/88) | 95.3 % (41/43) |

## By lang

| lang | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| ca | 100.0 % (31/31) | 100.0 % (23/23) | 100.0 % (18/18) | 100.0 % (18/18) | 100.0 % (18/18) | 100.0 % (13/13) | 100.0 % (6/6) |
| de | 100.0 % (28/28) | 100.0 % (22/22) | 100.0 % (17/17) | 100.0 % (17/17) | 100.0 % (17/17) | 90.9 % (10/11) | 85.7 % (6/7) |
| en | 100.0 % (91/91) | 100.0 % (70/70) | 100.0 % (53/53) | 100.0 % (53/53) | 100.0 % (53/53) | 100.0 % (38/38) | 100.0 % (18/18) |
| es | 100.0 % (37/37) | 100.0 % (25/25) | 100.0 % (20/20) | 100.0 % (20/20) | 100.0 % (20/20) | 100.0 % (17/17) | 100.0 % (6/6) |
| zh | 100.0 % (25/25) | 100.0 % (19/19) | 100.0 % (16/16) | 100.0 % (16/16) | 100.0 % (16/16) | 100.0 % (9/9) | 83.3 % (5/6) |

## By style

| style | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| colloquial | 100.0 % (17/17) | 100.0 % (14/14) | 100.0 % (11/11) | 100.0 % (11/11) | 100.0 % (11/11) | 100.0 % (6/6) | 100.0 % (5/5) |
| messy | 100.0 % (14/14) | 100.0 % (12/12) | 100.0 % (9/9) | 100.0 % (9/9) | 100.0 % (9/9) | 100.0 % (5/5) | 100.0 % (3/3) |
| plain | 100.0 % (147/147) | 100.0 % (107/107) | 100.0 % (81/81) | 100.0 % (81/81) | 100.0 % (81/81) | 98.5 % (65/66) | 92.6 % (25/27) |
| technical | 100.0 % (15/15) | 100.0 % (13/13) | 100.0 % (12/12) | 100.0 % (12/12) | 100.0 % (12/12) | 100.0 % (3/3) | 100.0 % (3/3) |
| telegraphic | 100.0 % (9/9) | 100.0 % (6/6) | 100.0 % (6/6) | 100.0 % (6/6) | 100.0 % (6/6) | 100.0 % (3/3) | 100.0 % (3/3) |
| verbose | 100.0 % (10/10) | 100.0 % (7/7) | 100.0 % (5/5) | 100.0 % (5/5) | 100.0 % (5/5) | 100.0 % (5/5) | 100.0 % (2/2) |

## By vague

| vague | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| grouping | 100.0 % (4/4) | — | — | — | — | 75.0 % (3/4) | — |
| none | 100.0 % (197/197) | 100.0 % (148/148) | 100.0 % (124/124) | 100.0 % (124/124) | 100.0 % (124/124) | 100.0 % (73/73) | 95.3 % (41/43) |
| place | 100.0 % (4/4) | 100.0 % (4/4) | — | — | — | 100.0 % (4/4) | — |
| time | 100.0 % (3/3) | 100.0 % (3/3) | — | — | — | 100.0 % (3/3) | — |
| value | 100.0 % (4/4) | 100.0 % (4/4) | — | — | — | 100.0 % (4/4) | — |

## By noise

| noise | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| no_accents | 100.0 % (11/11) | 100.0 % (7/7) | 100.0 % (6/6) | 100.0 % (6/6) | 100.0 % (6/6) | 100.0 % (5/5) | 100.0 % (2/2) |
| none | 100.0 % (188/188) | 100.0 % (141/141) | 100.0 % (108/108) | 100.0 % (108/108) | 100.0 % (108/108) | 98.8 % (79/80) | 94.9 % (37/39) |
| typos | 100.0 % (13/13) | 100.0 % (11/11) | 100.0 % (10/10) | 100.0 % (10/10) | 100.0 % (10/10) | 100.0 % (3/3) | 100.0 % (2/2) |

## Failures (3)

### `R020.de-vague_grouping` rep 1 — ambiguity_detection

> Auf DEV-NET mit der Spitzennachfrage: Kante B2C2 von 08:00 bis 09:00 auf 40 km/h begrenzt, Ampel an Kreuzung C2 in derselben Stunde auf Programm 1, Nachfrage in dieser Stunde 10 % niedriger – was macht das mit der mittleren Reisezeit?

Gold: expect `ambiguities[]` (vague grouping)

Parsed: intent `counterfactual` · network `DEV-NET` · demand `peak` · metrics mean_travel_time
- arm `treatment`: `speed_limit(B2C2, speed=11.111, 08:00–09:00)` + `signal_program(C2, program_id=1, 08:00–09:00)` + `demand_scale(, factor=0.9, 08:00–09:00)`

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
- arm `A`: `lane_closure(B0C0/1, 08:00–08:30)`
- arm `B`: `speed_limit(B2C2, speed=8.333, 08:00–09:00)`
- arm `C`: `signal_program(C2, program_id=1, 08:00–09:00)`
- arm `change1_A`: `set_lanes(edge_id=C0D0, lanes=3)` + `lane_closure(B0C0/1, 08:00–08:30)`
- arm `change1_C`: `set_lanes(edge_id=C0D0, lanes=3)` + `signal_program(C2, program_id=1, 08:00–09:00)`
- arm `change2_B`: `remove_edge(edge_id=B1C1)` + `speed_limit(B2C2, speed=8.333, 08:00–09:00)`
- arm `change3`: `add_edge(from_junction=B1, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW3)`
- arm `change3_D`: `add_edge(from_junction=B1, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW3)` + `speed_limit(NEW3, speed=8.333, 08:00–09:00)`
- contrasts: `A` vs `B`, `change1_A` vs `change1_C`, `change2_B` vs `B`, `change3` vs `base`, `change3_D` vs `change3`

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
- arm `measure_a`: `lane_closure(B0C0/1, 08:00–08:30)`
- arm `measure_b`: `speed_limit(B2C2, speed=8.333, 08:00–09:00)`
- arm `change1_a`: `set_lanes(edge_id=C0D0, lanes=3)` + `lane_closure(B0C0/1, 08:00–08:30)`
- arm `change1_c`: `set_lanes(edge_id=C0D0, lanes=3)` + `signal_program(C2, program_id=1, 08:00–09:00)`
- arm `change2_b`: `remove_edge(edge_id=B1C1)` + `speed_limit(B2C2, speed=8.333, 08:00–09:00)`
- arm `change3`: `add_edge(from_junction=B1, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW3)`
- arm `change3_d`: `add_edge(from_junction=B1, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW3)` + `speed_limit(NEW3, speed=8.333, 08:00–09:00)`
- contrasts: `measure_a` vs `measure_b`, `change1_a` vs `change1_c`, `change2_b` vs `base`, `change3` vs `base`, `change3_d` vs `change3`

