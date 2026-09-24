# Input Parser benchmark — v6-dev

232 requests, 232 runs (repetitions [1]), models ['deepseek/deepseek-v4.1-flash'], parser ['v6']; $0.2633, mean 5497 input / 517 output tokens; stop reasons {'output': 232}.

| Metric | Result | 95 % CI by concept | E5.1 threshold | Met |
|---|---|---|---|---|
| schema_validity | 100.0 % (232/232) | 94–100 % (49 concepts, rule of three) | ≥ 98% | yes |
| intent | 99.4 % (178/179) | 98–100 % (37 concepts) | ≥ 85% | yes |
| interventions | 100.0 % (141/141) | 90–100 % (31 concepts, rule of three) | ≥ 85% | yes |
| topology_changes | 100.0 % (141/141) | 90–100 % (31 concepts, rule of three) | ≥ 85% | yes |
| metrics_of_interest | 100.0 % (141/141) | 90–100 % (31 concepts, rule of three) | ≥ 85% | yes |
| ambiguity_detection | 97.8 % (89/91) | 94–100 % (35 concepts) | ≥ 80% | yes |
| arm_structure | 95.3 % (41/43) | 86–100 % (10 concepts) | ≥ 90% | yes |

Met is judged on the point estimate. The interval resamples whole concepts (bootstrap), so it shows how much the result could move with another draw of concepts; when every concept is right it is the rule-of-three bound 1 − 3/n. `intent` also accepts the second reading listed in `concepts.ALSO_ACCEPTED`; `intent_strict` below is against the gold intent alone.

Reported, not graded:

- intent_strict: 99.4 % (178/179)
- arm_structure_single: 100.0 % (98/98)
- required_arms: 97.7 % (42/43)
- spurious_ambiguity: 0.0 % (0/141)
- used_shorthand: 100.0 % (80/80)
- network_ref: 100.0 % (141/141)
- demand_ref: 100.0 % (141/141)
- time_window: 100.0 % (141/141)
- consistency across variants: 89.8 % (44/49)

## By category

| category | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| adversarial | 100.0 % (15/15) | 100.0 % (10/10) | 100.0 % (10/10) | 100.0 % (10/10) | 100.0 % (10/10) | 100.0 % (5/5) | — |
| ambiguous | 100.0 % (44/44) | 100.0 % (24/24) | — | — | — | 97.7 % (43/44) | — |
| combined | 100.0 % (19/19) | 94.4 % (17/18) | 100.0 % (18/18) | 100.0 % (18/18) | 100.0 % (18/18) | 100.0 % (1/1) | — |
| multi_arm | 100.0 % (49/49) | 100.0 % (46/46) | 100.0 % (43/43) | 100.0 % (43/43) | 100.0 % (43/43) | 83.3 % (5/6) | 95.3 % (41/43) |
| out_of_scope | 100.0 % (12/12) | — | — | — | — | 100.0 % (12/12) | — |
| single | 100.0 % (81/81) | 100.0 % (81/81) | 100.0 % (70/70) | 100.0 % (70/70) | 100.0 % (70/70) | 100.0 % (11/11) | — |
| unintelligible | 100.0 % (12/12) | — | — | — | — | 100.0 % (12/12) | — |

## By split

| split | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| dev | 100.0 % (232/232) | 99.4 % (178/179) | 100.0 % (141/141) | 100.0 % (141/141) | 100.0 % (141/141) | 97.8 % (89/91) | 95.3 % (41/43) |

## By lang

| lang | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| ca | 100.0 % (34/34) | 100.0 % (26/26) | 100.0 % (20/20) | 100.0 % (20/20) | 100.0 % (20/20) | 100.0 % (14/14) | 100.0 % (6/6) |
| de | 100.0 % (32/32) | 100.0 % (26/26) | 100.0 % (21/21) | 100.0 % (21/21) | 100.0 % (21/21) | 90.9 % (10/11) | 100.0 % (7/7) |
| en | 100.0 % (97/97) | 100.0 % (76/76) | 100.0 % (58/58) | 100.0 % (58/58) | 100.0 % (58/58) | 100.0 % (39/39) | 94.4 % (17/18) |
| es | 100.0 % (41/41) | 100.0 % (29/29) | 100.0 % (23/23) | 100.0 % (23/23) | 100.0 % (23/23) | 100.0 % (18/18) | 100.0 % (6/6) |
| zh | 100.0 % (28/28) | 95.5 % (21/22) | 100.0 % (19/19) | 100.0 % (19/19) | 100.0 % (19/19) | 88.9 % (8/9) | 83.3 % (5/6) |

## By style

| style | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| colloquial | 100.0 % (19/19) | 100.0 % (16/16) | 100.0 % (13/13) | 100.0 % (13/13) | 100.0 % (13/13) | 100.0 % (6/6) | 100.0 % (5/5) |
| messy | 100.0 % (15/15) | 100.0 % (13/13) | 100.0 % (10/10) | 100.0 % (10/10) | 100.0 % (10/10) | 100.0 % (5/5) | 100.0 % (3/3) |
| plain | 100.0 % (161/161) | 99.2 % (120/121) | 100.0 % (92/92) | 100.0 % (92/92) | 100.0 % (92/92) | 97.1 % (67/69) | 92.6 % (25/27) |
| technical | 100.0 % (16/16) | 100.0 % (14/14) | 100.0 % (13/13) | 100.0 % (13/13) | 100.0 % (13/13) | 100.0 % (3/3) | 100.0 % (3/3) |
| telegraphic | 100.0 % (10/10) | 100.0 % (7/7) | 100.0 % (7/7) | 100.0 % (7/7) | 100.0 % (7/7) | 100.0 % (3/3) | 100.0 % (3/3) |
| verbose | 100.0 % (11/11) | 100.0 % (8/8) | 100.0 % (6/6) | 100.0 % (6/6) | 100.0 % (6/6) | 100.0 % (5/5) | 100.0 % (2/2) |

## By vague

| vague | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| grouping | 100.0 % (4/4) | — | — | — | — | 75.0 % (3/4) | — |
| none | 100.0 % (214/214) | 99.4 % (164/165) | 100.0 % (141/141) | 100.0 % (141/141) | 100.0 % (141/141) | 98.6 % (72/73) | 95.3 % (41/43) |
| place | 100.0 % (5/5) | 100.0 % (5/5) | — | — | — | 100.0 % (5/5) | — |
| time | 100.0 % (5/5) | 100.0 % (5/5) | — | — | — | 100.0 % (5/5) | — |
| value | 100.0 % (4/4) | 100.0 % (4/4) | — | — | — | 100.0 % (4/4) | — |

## By noise

| noise | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| no_accents | 100.0 % (11/11) | 100.0 % (7/7) | 100.0 % (6/6) | 100.0 % (6/6) | 100.0 % (6/6) | 100.0 % (5/5) | 100.0 % (2/2) |
| none | 100.0 % (206/206) | 99.4 % (158/159) | 100.0 % (123/123) | 100.0 % (123/123) | 100.0 % (123/123) | 97.6 % (81/83) | 94.9 % (37/39) |
| typos | 100.0 % (15/15) | 100.0 % (13/13) | 100.0 % (12/12) | 100.0 % (12/12) | 100.0 % (12/12) | 100.0 % (3/3) | 100.0 % (2/2) |

## Failures (5)

### `R020.de-vague_grouping` rep 1 — ambiguity_detection

> Auf DEV-NET mit der Spitzennachfrage: Kante B2C2 von 08:00 bis 09:00 auf 40 km/h begrenzt, Ampel an Kreuzung C2 in derselben Stunde auf Programm 1, Nachfrage in dieser Stunde 10 % niedriger – was macht das mit der mittleren Reisezeit?

Gold: expect `ambiguities[]` (vague grouping)

Parsed: intent `counterfactual` · network `DEV-NET` · demand `peak` · metrics mean_travel_time
- arm `treatment`: `speed_limit(B2C2, speed=11.111, 08:00–09:00)` + `signal_program(C2, program_id=1, 08:00–09:00)` + `demand_scale(, factor=0.9, 08:00–09:00)`

### `R035.zh` rep 1 — intent

> 请将当前 DEV-NET 与一个版本进行比较，在该版本中，边 A1B1 限速为 30 公里/小时，且 B2 路口的交通信号灯运行程序 1，这两项措施同时从 08:00 至 09:00 生效，比较指标为平均延误。

Gold: intent `counterfactual` · network `DEV-NET` · metrics mean_delay
- arm `treatment`: `speed_limit(A1B1, speed=8.333, 08:00–09:00)` + `signal_program(B2, program_id=1, 08:00–09:00)`

Parsed: intent `compare` · network `DEV-NET` · metrics mean_delay
- arm `treatment`: `speed_limit(A1B1, speed=8.333, 08:00–09:00)` + `signal_program(B2, program_id=1, 08:00–09:00)`

### `R044.zh` rep 1 — ambiguity_detection

> 在 DEV-NET 上测试平均延误：B0C0 边缘的 1 号车道在 08:00 至 08:30 关闭，08:00 至 09:00 期间需求增加 20%，C2 路口的交通信号灯在 08:00 至 09:00 期间使用方案 1。

Gold: expect `ambiguities[]` (which combinations to simulate)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_delay
- arm `treatment`: `lane_closure(B0C0/1, 08:00–08:30)` + `demand_scale(, factor=1.2, 08:00–09:00)` + `signal_program(C2, program_id=1, 08:00–09:00)`

### `R065` rep 1 — arm_structure

> On DEV-NET I have four measures and three network changes, and I do not want every combination, only the ones below, all by mean travel time. The measures: A, closing lane 1 of edge B0C0 from 08:00 to 08:30; B, limiting edge B2C2 to 30 km/h from 08:00 to 09:00; C, switching the traffic light at junction C2 to program 1 from 08:00 to 09:00; D, limiting the new edge NEW3 to 30 km/h from 08:00 to 09:00. The changes: 1, widening edge C0D0 to three lanes; 2, removing edge B1C1 for good; 3, building a two-lane edge NEW3 from junction B1 to junction C2 with a 50 km/h limit. First, which is faster, A or B? Compare those two with each other only. With change 1 we can still do A but not B, although we can do C: with change 1 in place, which is faster, A or C? With change 2, does B work as well as it does on today's network? Finally, does change 3 on its own help compared with today, and does adding D to change 3 improve on change 3 alone?

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
- arm `c_signal`: `signal_program(C2, program_id=1, 08:00–09:00)`
- arm `change1_a`: `set_lanes(edge_id=C0D0, lanes=3)` + `lane_closure(B0C0/1, 08:00–08:30)`
- arm `change1_c`: `set_lanes(edge_id=C0D0, lanes=3)` + `signal_program(C2, program_id=1, 08:00–09:00)`
- arm `change2_b`: `remove_edge(edge_id=B1C1)` + `speed_limit(B2C2, speed=8.333, 08:00–09:00)`
- arm `change3`: `add_edge(from_junction=B1, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW3)`
- arm `change3_d`: `add_edge(from_junction=B1, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW3)` + `speed_limit(NEW3, speed=8.333, 08:00–09:00)`
- contrasts: `a_closure` vs `b_speed`, `change1_a` vs `change1_c`, `change2_b` vs `b_speed`, `change3` vs `base`, `change3_d` vs `change3`

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

