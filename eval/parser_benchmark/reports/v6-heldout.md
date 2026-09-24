# Input Parser benchmark — v6-heldout

114 requests, 342 runs (repetitions [1, 2, 3]), models ['deepseek/deepseek-v4.1-flash'], parser ['v6']; $0.3760, mean 5118 input / 553 output tokens; stop reasons {'output': 342}.

| Metric | Result | 95 % CI by concept | E5.1 threshold | Met |
|---|---|---|---|---|
| schema_validity | 100.0 % (342/342) | 88–100 % (24 concepts, rule of three) | ≥ 98% | yes |
| intent | 95.7 % (244/255) | 89–100 % (18 concepts) | ≥ 85% | yes |
| interventions | 99.5 % (212/213) | 99–100 % (16 concepts) | ≥ 85% | yes |
| topology_changes | 100.0 % (213/213) | 81–100 % (16 concepts, rule of three) | ≥ 85% | yes |
| metrics_of_interest | 100.0 % (213/213) | 81–100 % (16 concepts, rule of three) | ≥ 85% | yes |
| ambiguity_detection | 82.2 % (106/129) | 63–97 % (18 concepts) | ≥ 80% | yes |
| arm_structure | 94.4 % (51/54) | 89–100 % (4 concepts) | ≥ 90% | yes |
| intent_agreement | 93.9 % (107/114) | — | ≥ 95% | **no** |

Met is judged on the point estimate. The interval resamples whole concepts (bootstrap), so it shows how much the result could move with another draw of concepts; when every concept is right it is the rule-of-three bound 1 − 3/n. `intent` also accepts the second reading listed in `concepts.ALSO_ACCEPTED`; `intent_strict` below is against the gold intent alone.

Reported, not graded:

- intent_strict: 95.7 % (244/255)
- arm_structure_single: 99.4 % (158/159)
- required_arms: 94.4 % (51/54)
- spurious_ambiguity: 0.0 % (0/213)
- used_shorthand: 100.0 % (117/117)
- network_ref: 100.0 % (213/213)
- demand_ref: 98.6 % (210/213)
- time_window: 100.0 % (213/213)
- consistency across variants: 83.3 % (20/24)

## By category

| category | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| adversarial | 100.0 % (15/15) | 100.0 % (15/15) | 100.0 % (15/15) | 100.0 % (15/15) | 100.0 % (15/15) | — | — |
| ambiguous | 100.0 % (48/48) | 100.0 % (24/24) | — | — | — | 64.6 % (31/48) | — |
| combined | 100.0 % (30/30) | 100.0 % (24/24) | 95.8 % (23/24) | 100.0 % (24/24) | 100.0 % (24/24) | 83.3 % (5/6) | — |
| multi_arm | 100.0 % (60/60) | 85.2 % (46/54) | 100.0 % (54/54) | 100.0 % (54/54) | 100.0 % (54/54) | 16.7 % (1/6) | 94.4 % (51/54) |
| out_of_scope | 100.0 % (27/27) | — | — | — | — | 100.0 % (27/27) | — |
| single | 100.0 % (138/138) | 97.8 % (135/138) | 100.0 % (120/120) | 100.0 % (120/120) | 100.0 % (120/120) | 100.0 % (18/18) | — |
| unintelligible | 100.0 % (24/24) | — | — | — | — | 100.0 % (24/24) | — |

## By split

| split | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| held_out | 100.0 % (342/342) | 95.7 % (244/255) | 99.5 % (212/213) | 100.0 % (213/213) | 100.0 % (213/213) | 82.2 % (106/129) | 94.4 % (51/54) |

## By lang

| lang | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| ca | 100.0 % (45/45) | 88.9 % (32/36) | 100.0 % (30/30) | 100.0 % (30/30) | 100.0 % (30/30) | 60.0 % (9/15) | 83.3 % (5/6) |
| de | 100.0 % (57/57) | 92.9 % (39/42) | 100.0 % (36/36) | 100.0 % (36/36) | 100.0 % (36/36) | 90.5 % (19/21) | 100.0 % (9/9) |
| en | 100.0 % (141/141) | 97.1 % (99/102) | 100.0 % (81/81) | 100.0 % (81/81) | 100.0 % (81/81) | 83.3 % (50/60) | 100.0 % (24/24) |
| es | 100.0 % (54/54) | 97.6 % (41/42) | 97.2 % (35/36) | 100.0 % (36/36) | 100.0 % (36/36) | 88.9 % (16/18) | 100.0 % (9/9) |
| zh | 100.0 % (45/45) | 100.0 % (33/33) | 100.0 % (30/30) | 100.0 % (30/30) | 100.0 % (30/30) | 80.0 % (12/15) | 66.7 % (4/6) |

## By style

| style | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| colloquial | 100.0 % (36/36) | 93.3 % (28/30) | 100.0 % (27/27) | 100.0 % (27/27) | 100.0 % (27/27) | 44.4 % (4/9) | 100.0 % (3/3) |
| messy | 100.0 % (9/9) | 100.0 % (9/9) | 100.0 % (6/6) | 100.0 % (6/6) | 100.0 % (6/6) | 100.0 % (3/3) | — |
| plain | 100.0 % (231/231) | 96.2 % (153/159) | 99.2 % (128/129) | 100.0 % (129/129) | 100.0 % (129/129) | 84.3 % (86/102) | 90.9 % (30/33) |
| technical | 100.0 % (21/21) | 85.7 % (18/21) | 100.0 % (18/18) | 100.0 % (18/18) | 100.0 % (18/18) | 33.3 % (1/3) | 100.0 % (9/9) |
| telegraphic | 100.0 % (27/27) | 100.0 % (18/18) | 100.0 % (15/15) | 100.0 % (15/15) | 100.0 % (15/15) | 100.0 % (12/12) | — |
| verbose | 100.0 % (18/18) | 100.0 % (18/18) | 100.0 % (18/18) | 100.0 % (18/18) | 100.0 % (18/18) | — | 100.0 % (9/9) |

## By vague

| vague | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| grouping | 100.0 % (12/12) | — | — | — | — | 50.0 % (6/12) | — |
| none | 100.0 % (312/312) | 95.4 % (226/237) | 99.5 % (212/213) | 100.0 % (213/213) | 100.0 % (213/213) | 82.8 % (82/99) | 94.4 % (51/54) |
| place | 100.0 % (3/3) | 100.0 % (3/3) | — | — | — | 100.0 % (3/3) | — |
| time | 100.0 % (9/9) | 100.0 % (9/9) | — | — | — | 100.0 % (9/9) | — |
| value | 100.0 % (6/6) | 100.0 % (6/6) | — | — | — | 100.0 % (6/6) | — |

## By noise

| noise | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| no_accents | 100.0 % (18/18) | 94.4 % (17/18) | 100.0 % (18/18) | 100.0 % (18/18) | 100.0 % (18/18) | — | 100.0 % (3/3) |
| none | 100.0 % (312/312) | 95.7 % (224/234) | 99.5 % (191/192) | 100.0 % (192/192) | 100.0 % (192/192) | 82.5 % (99/120) | 94.1 % (48/51) |
| typos | 100.0 % (12/12) | 100.0 % (3/3) | 100.0 % (3/3) | 100.0 % (3/3) | 100.0 % (3/3) | 77.8 % (7/9) | — |

## Failures (38)

### `R003.ca` rep 2 — arm_structure

> A DEV-NET, què redueix més el retard mitjà: tancar l'aresta C0D0 de 08:00 a 08:30, o limitar l'aresta B2C2 a 30 km/h durant el mateix període?

Gold: intent `compare` · network `DEV-NET` · metrics mean_delay
- arm `closure`: `edge_closure(C0D0, 08:00–08:30)`
- arm `speed_limit`: `speed_limit(B2C2, speed=8.333, 08:00–08:30)`
- contrasts: `closure` vs `base`, `speed_limit` vs `base`

Parsed: intent `compare` · network `DEV-NET` · metrics mean_delay
- arm `closure`: `edge_closure(C0D0, 08:00–08:30)`
- arm `speed_limit`: `speed_limit(B2C2, speed=8.333, 08:00–08:30)`
- contrasts: `closure` vs `speed_limit`

### `R003.en-vague_grouping` rep 1 — ambiguity_detection

> On DEV-NET, closing edge C0D0 from 08:00 to 08:30, limiting edge B2C2 to 30 km/h over the same period: what does that do to the mean delay?

Gold: expect `ambiguities[]` (vague grouping)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_delay
- arm `treatment`: `edge_closure(C0D0, 08:00–08:30)` + `speed_limit(B2C2, speed=8.333, 08:00–08:30)`

### `R003.en-vague_grouping` rep 3 — ambiguity_detection

> On DEV-NET, closing edge C0D0 from 08:00 to 08:30, limiting edge B2C2 to 30 km/h over the same period: what does that do to the mean delay?

Gold: expect `ambiguities[]` (vague grouping)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_delay
- arm `treatment`: `edge_closure(C0D0, 08:00–08:30)` + `speed_limit(B2C2, speed=8.333, 08:00–08:30)`

### `R003.zh` rep 3 — arm_structure

> 在 DEV-NET 上，从 08:00 到 08:30 关闭边 C0D0，与在同一时段内将边 B2C2 限速至 30 km/h，哪一种更能降低平均延迟？

Gold: intent `compare` · network `DEV-NET` · metrics mean_delay
- arm `closure`: `edge_closure(C0D0, 08:00–08:30)`
- arm `speed_limit`: `speed_limit(B2C2, speed=8.333, 08:00–08:30)`
- contrasts: `closure` vs `base`, `speed_limit` vs `base`

Parsed: intent `compare` · network `DEV-NET` · metrics mean_delay
- arm `closure_c0d0`: `edge_closure(C0D0, 08:00–08:30)`
- arm `speed_limit_b2c2`: `speed_limit(B2C2, speed=8.333, 08:00–08:30)`
- contrasts: `closure_c0d0` vs `speed_limit_b2c2`

### `R016.en-colloquial` rep 2 — intent

> Can you compare the average delay on DEV-NET when lane 0 of edge B0C0 is closed from 08:15 to 08:45 versus when it's open?

Gold: intent `counterfactual` · network `DEV-NET` · metrics mean_delay
- arm `treatment`: `lane_closure(B0C0/0, 08:15–08:45)`

Parsed: intent `compare` · network `DEV-NET` · metrics mean_delay
- arm `treatment`: `lane_closure(B0C0/0, 08:15–08:45)`

### `R022.ca-vague_grouping` rep 1 — ambiguity_detection

> A DEV-NET, quant reduiria el retard mitjà la construcció d'un tram nou d'un sol carril des del nus C1 fins al nus D2, amb un límit de 50 km/h? I quant canviaria el retard mitjà si el tram C2D2 es tanqués entre les 08:00 i les 08:30?

Gold: expect `ambiguities[]` (vague grouping)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_delay
- arm `new_edge_C1_D2`: `add_edge(from_junction=C1, to_junction=D2, lanes=1, speed=13.889)`
- arm `close_C2D2`: `edge_closure(C2D2, 08:00–08:30)`
- contrasts: `new_edge_C1_D2` vs `base`, `close_C2D2` vs `base`

### `R022.ca-vague_grouping` rep 2 — ambiguity_detection

> A DEV-NET, quant reduiria el retard mitjà la construcció d'un tram nou d'un sol carril des del nus C1 fins al nus D2, amb un límit de 50 km/h? I quant canviaria el retard mitjà si el tram C2D2 es tanqués entre les 08:00 i les 08:30?

Gold: expect `ambiguities[]` (vague grouping)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_delay
- arm `new_edge`: `add_edge(from_junction=C1, to_junction=D2, lanes=1, speed=13.889)`
- arm `edge_closure`: `edge_closure(C2D2, 08:00–08:30)`
- contrasts: `new_edge` vs `base`, `edge_closure` vs `base`

### `R022.ca-vague_grouping` rep 3 — ambiguity_detection

> A DEV-NET, quant reduiria el retard mitjà la construcció d'un tram nou d'un sol carril des del nus C1 fins al nus D2, amb un límit de 50 km/h? I quant canviaria el retard mitjà si el tram C2D2 es tanqués entre les 08:00 i les 08:30?

Gold: expect `ambiguities[]` (vague grouping)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_delay
- arm `new_edge_c1_d2`: `add_edge(from_junction=C1, to_junction=D2, lanes=1, speed=13.889)`
- arm `close_c2d2`: `edge_closure(C2D2, 08:00–08:30)`
- contrasts: `new_edge_c1_d2` vs `base`, `close_c2d2` vs `base`

### `R022.zh` rep 3 — arm_structure

> 在 DEV-NET 上，如果从路口 C1 到路口 D2 新建一条限速 50 km/h 的单车道边，平均延误会减少多少？并且，在该边建成后，如果再将边 C2D2 在 08:00 至 08:30 期间关闭，平均延误还会再变化多少？

Gold: intent `counterfactual` · network `DEV-NET` · metrics mean_delay
- arm `new_edge`: `add_edge(from_junction=C1, to_junction=D2, lanes=1, speed=13.889)`
- arm `new_edge_closure`: `add_edge(from_junction=C1, to_junction=D2, lanes=1, speed=13.889)` + `edge_closure(C2D2, 08:00–08:30)`
- contrasts: `new_edge` vs `base`, `new_edge_closure` vs `new_edge`

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_delay
- arm `new_edge`: `add_edge(from_junction=C1, to_junction=D2, lanes=1, speed=13.889)`
- arm `new_edge_and_closure`: `add_edge(from_junction=C1, to_junction=D2, lanes=1, speed=13.889)` + `edge_closure(C2D2, 08:00–08:30)`
- contrasts: `new_edge_and_closure` vs `new_edge`

### `R023.ca-technical` rep 1 — intent

> DEV-NET: simular nova aresta NEW1 (de B3 a C2, 50 km/h, 2 carrils). Comparar el temps mitjà de viatge amb el carril 0 de NEW1 tancat (08:00-08:30) vs. NEW1 oberta.

Gold: intent `counterfactual` · network `DEV-NET` · metrics mean_travel_time
- arm `new_edge`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)`
- arm `new_edge_closure`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)` + `lane_closure(NEW1/0, 08:00–08:30)`
- contrasts: `new_edge_closure` vs `new_edge`

Parsed: intent `compare` · network `DEV-NET` · metrics mean_travel_time
- arm `lane_0_closed`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)` + `lane_closure(NEW1/0, 08:00–08:30)`
- arm `new_edge_open`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)`
- contrasts: `lane_0_closed` vs `new_edge_open`

### `R023.ca-technical` rep 2 — intent

> DEV-NET: simular nova aresta NEW1 (de B3 a C2, 50 km/h, 2 carrils). Comparar el temps mitjà de viatge amb el carril 0 de NEW1 tancat (08:00-08:30) vs. NEW1 oberta.

Gold: intent `counterfactual` · network `DEV-NET` · metrics mean_travel_time
- arm `new_edge`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)`
- arm `new_edge_closure`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)` + `lane_closure(NEW1/0, 08:00–08:30)`
- contrasts: `new_edge_closure` vs `new_edge`

Parsed: intent `compare` · network `DEV-NET` · metrics mean_travel_time
- arm `lane0_closed`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)` + `lane_closure(NEW1/0, 08:00–08:30)`
- arm `open`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)`
- contrasts: `lane0_closed` vs `open`

### `R023.ca-technical` rep 3 — intent

> DEV-NET: simular nova aresta NEW1 (de B3 a C2, 50 km/h, 2 carrils). Comparar el temps mitjà de viatge amb el carril 0 de NEW1 tancat (08:00-08:30) vs. NEW1 oberta.

Gold: intent `counterfactual` · network `DEV-NET` · metrics mean_travel_time
- arm `new_edge`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)`
- arm `new_edge_closure`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)` + `lane_closure(NEW1/0, 08:00–08:30)`
- contrasts: `new_edge_closure` vs `new_edge`

Parsed: intent `compare` · network `DEV-NET` · metrics mean_travel_time
- arm `lane0_closed`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)` + `lane_closure(NEW1/0, 08:00–08:30)`
- arm `new1_open`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)`
- contrasts: `lane0_closed` vs `new1_open`

### `R023.de` rep 1 — intent

> Angenommen, auf DEV-NET wird eine zweispurige Kante namens NEW1 von Knoten B3 nach Knoten C2 mit einer Geschwindigkeitsbegrenzung von 50 km/h gebaut. Was würde es, sobald NEW1 in Betrieb ist, für die mittlere Fahrzeit bedeuten, Spur 0 von NEW1 von 08:00 bis 08:30 zu sperren, im Vergleich dazu, dass NEW1 vollständig offen ist?

Gold: intent `counterfactual` · network `DEV-NET` · metrics mean_travel_time
- arm `new_edge`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)`
- arm `new_edge_closure`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)` + `lane_closure(NEW1/0, 08:00–08:30)`
- contrasts: `new_edge_closure` vs `new_edge`

Parsed: intent `compare` · network `DEV-NET` · metrics mean_travel_time
- arm `lane0_closed`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)` + `lane_closure(NEW1/0, 08:00–08:30)`
- arm `fully_open`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)`
- contrasts: `lane0_closed` vs `fully_open`

### `R023.de` rep 2 — intent

> Angenommen, auf DEV-NET wird eine zweispurige Kante namens NEW1 von Knoten B3 nach Knoten C2 mit einer Geschwindigkeitsbegrenzung von 50 km/h gebaut. Was würde es, sobald NEW1 in Betrieb ist, für die mittlere Fahrzeit bedeuten, Spur 0 von NEW1 von 08:00 bis 08:30 zu sperren, im Vergleich dazu, dass NEW1 vollständig offen ist?

Gold: intent `counterfactual` · network `DEV-NET` · metrics mean_travel_time
- arm `new_edge`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)`
- arm `new_edge_closure`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)` + `lane_closure(NEW1/0, 08:00–08:30)`
- contrasts: `new_edge_closure` vs `new_edge`

Parsed: intent `compare` · network `DEV-NET` · metrics mean_travel_time
- arm `lane_closed`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)` + `lane_closure(NEW1/0, 08:00–08:30)`
- arm `fully_open`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)`
- contrasts: `lane_closed` vs `fully_open`

### `R023.de` rep 3 — intent

> Angenommen, auf DEV-NET wird eine zweispurige Kante namens NEW1 von Knoten B3 nach Knoten C2 mit einer Geschwindigkeitsbegrenzung von 50 km/h gebaut. Was würde es, sobald NEW1 in Betrieb ist, für die mittlere Fahrzeit bedeuten, Spur 0 von NEW1 von 08:00 bis 08:30 zu sperren, im Vergleich dazu, dass NEW1 vollständig offen ist?

Gold: intent `counterfactual` · network `DEV-NET` · metrics mean_travel_time
- arm `new_edge`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)`
- arm `new_edge_closure`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)` + `lane_closure(NEW1/0, 08:00–08:30)`
- contrasts: `new_edge_closure` vs `new_edge`

Parsed: intent `compare` · network `DEV-NET` · metrics mean_travel_time
- arm `lane_closed`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)` + `lane_closure(NEW1/0, 08:00–08:30)`
- arm `fully_open`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)`
- contrasts: `lane_closed` vs `fully_open`

### `R023.en-colloquial` rep 2 — intent

> Hey, on DEV-NET, imagine we build a two-lane edge named NEW1 going from junction B3 to C2 with a 50 km/h speed limit. If we then close lane 0 of NEW1 between 8:00 and 8:30, how does that affect the mean travel time compared to when NEW1 is fully open?

Gold: intent `counterfactual` · network `DEV-NET` · metrics mean_travel_time
- arm `new_edge`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)`
- arm `new_edge_closure`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)` + `lane_closure(NEW1/0, 08:00–08:30)`
- contrasts: `new_edge_closure` vs `new_edge`

Parsed: intent `compare` · network `DEV-NET` · metrics mean_travel_time
- arm `new_edge_lane0_closed`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)` + `lane_closure(NEW1/0, 08:00–08:30)`
- arm `new_edge_open`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)`
- contrasts: `new_edge_lane0_closed` vs `new_edge_open`

### `R023.es-no_accents` rep 2 — intent

> En DEV-NET, supongamos que se construye un tramo de dos carriles llamado NEW1 desde la interseccion B3 hasta la interseccion C2 con un limite de 50 km/h. Una vez que NEW1 este en funcionamiento, ¿que efecto tendria cerrar su carril 0 de 08:00 a 08:30 sobre el tiempo medio de viaje, en comparacion con NEW1 completamente abierto?

Gold: intent `counterfactual` · network `DEV-NET` · metrics mean_travel_time
- arm `new_edge`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)`
- arm `new_edge_closure`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)` + `lane_closure(NEW1/0, 08:00–08:30)`
- contrasts: `new_edge_closure` vs `new_edge`

Parsed: intent `compare` · network `DEV-NET` · metrics mean_travel_time
- arm `new_edge_open`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)`
- arm `new_edge_lane_0_closed`: `add_edge(from_junction=B3, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW1)` + `lane_closure(NEW1/0, 08:00–08:30)`
- contrasts: `new_edge_lane_0_closed` vs `new_edge_open`

### `R032.es-vague_grouping` rep 2 — ambiguity_detection

> En DEV-NET: el borde B1C1 eliminado de la red, la demanda un 15 % más alta de 08:00 a 09:00. ¿Cómo queda el retraso medio?

Gold: expect `ambiguities[]` (vague grouping)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_delay
- arm `treatment`: `remove_edge(edge_id=B1C1)` + `demand_scale(, factor=1.15, 08:00–09:00)`

### `R033.es` rep 2 — interventions

> En DEV-NET, ¿qué ocurriría con el tiempo medio de viaje si se cerraran simultáneamente las aristas C1C2 y C2C3 desde las 08:00 hasta las 08:30?

Gold: intent `counterfactual` · network `DEV-NET` · metrics mean_travel_time
- arm `treatment`: `edge_closure(C1C2, 08:00–08:30)` + `edge_closure(C2C3, 08:00–08:30)`

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_travel_time
- arm `treatment`: `edge_closure(C1C2, 08:00–08:15)` + `edge_closure(C2C3, 08:00–08:15)`

### `R042` rep 1 — ambiguity_detection

> On DEV-NET, closing lane 0 of edge B0C0 from 08:00 to 08:30 and limiting edge C0D0 to 30 km/h over the same period: how does the mean delay look?

Gold: expect `ambiguities[]` (together or compared)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_delay
- arm `treatment`: `lane_closure(B0C0/0, 08:00–08:30)` + `speed_limit(C0D0, speed=8.333, 08:00–08:30)`

### `R042` rep 3 — ambiguity_detection

> On DEV-NET, closing lane 0 of edge B0C0 from 08:00 to 08:30 and limiting edge C0D0 to 30 km/h over the same period: how does the mean delay look?

Gold: expect `ambiguities[]` (together or compared)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_delay
- arm `treatment`: `lane_closure(B0C0/0, 08:00–08:30)` + `speed_limit(C0D0, speed=8.333, 08:00–08:30)`

### `R042.en-typos` rep 2 — ambiguity_detection

> On DEV-NET, closing lane 0 of edge B0C0 frmo 08:00 to 08:30 and limiting edge C0D0 to 30 km/h over the same peirod: how does the mean dellay look?

Gold: expect `ambiguities[]` (together or compared)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_delay
- arm `treatment`: `lane_closure(B0C0/0, 08:00–08:30)` + `speed_limit(C0D0, speed=8.333, 08:00–08:30)`

### `R042.en-typos` rep 3 — ambiguity_detection

> On DEV-NET, closing lane 0 of edge B0C0 frmo 08:00 to 08:30 and limiting edge C0D0 to 30 km/h over the same peirod: how does the mean dellay look?

Gold: expect `ambiguities[]` (together or compared)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_delay
- arm `treatment`: `lane_closure(B0C0/0, 08:00–08:30)` + `speed_limit(C0D0, speed=8.333, 08:00–08:30)`

### `R042.es` rep 2 — ambiguity_detection

> En DEV-NET, cierra el carril 0 de la arista B0C0 desde las 08:00 hasta las 08:30 y limita la arista C0D0 a 30 km/h durante el mismo periodo: ¿cómo se ve el retraso medio?

Gold: expect `ambiguities[]` (together or compared)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_delay
- arm `treatment`: `lane_closure(B0C0/0, 08:00–08:30)` + `speed_limit(C0D0, speed=8.333, 08:00–08:30)`

### `R042.zh-colloquial` rep 1 — ambiguity_detection

> 在 DEV-NET 上，早上 8 点到 8 点半把 B0C0 边的 0 号车道关掉，同一时段把 C0D0 边限速 30 公里/小时，平均延误会怎么样？

Gold: expect `ambiguities[]` (together or compared)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_delay
- arm `treatment`: `lane_closure(B0C0/0, 08:00–08:30)` + `speed_limit(C0D0, speed=8.333, 08:00–08:30)`

### `R042.zh-colloquial` rep 2 — ambiguity_detection

> 在 DEV-NET 上，早上 8 点到 8 点半把 B0C0 边的 0 号车道关掉，同一时段把 C0D0 边限速 30 公里/小时，平均延误会怎么样？

Gold: expect `ambiguities[]` (together or compared)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_delay
- arm `treatment`: `lane_closure(B0C0/0, 08:00–08:30)` + `speed_limit(C0D0, speed=8.333, 08:00–08:30)`

### `R042.zh-colloquial` rep 3 — ambiguity_detection

> 在 DEV-NET 上，早上 8 点到 8 点半把 B0C0 边的 0 号车道关掉，同一时段把 C0D0 边限速 30 公里/小时，平均延误会怎么样？

Gold: expect `ambiguities[]` (together or compared)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_delay
- arm `treatment`: `lane_closure(B0C0/0, 08:00–08:30)` + `speed_limit(C0D0, speed=8.333, 08:00–08:30)`

### `R043` rep 1 — ambiguity_detection

> Simulate DEV-NET with edge A2B2 removed and with edge B0C0 reduced to one lane, and report the mean travel time.

Gold: expect `ambiguities[]` (one run with both changes or one run each, intent `counterfactual`)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_travel_time
- arm `treatment`: `remove_edge(edge_id=A2B2)` + `set_lanes(edge_id=B0C0, lanes=1)`

### `R043` rep 2 — ambiguity_detection

> Simulate DEV-NET with edge A2B2 removed and with edge B0C0 reduced to one lane, and report the mean travel time.

Gold: expect `ambiguities[]` (one run with both changes or one run each, intent `counterfactual`)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_travel_time
- arm `treatment`: `remove_edge(edge_id=A2B2)` + `set_lanes(edge_id=B0C0, lanes=1)`

### `R043.ca` rep 1 — ambiguity_detection

> Simuleu DEV-NET amb l'aresta A2B2 eliminada i amb l'aresta B0C0 reduïda a una sola carril, i informeu el temps de viatge mitjà.

Gold: expect `ambiguities[]` (one run with both changes or one run each, intent `counterfactual`)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_travel_time
- arm `treatment`: `remove_edge(edge_id=A2B2)` + `set_lanes(edge_id=B0C0, lanes=1)`

### `R043.ca` rep 2 — ambiguity_detection

> Simuleu DEV-NET amb l'aresta A2B2 eliminada i amb l'aresta B0C0 reduïda a una sola carril, i informeu el temps de viatge mitjà.

Gold: expect `ambiguities[]` (one run with both changes or one run each, intent `counterfactual`)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_travel_time
- arm `treatment`: `remove_edge(edge_id=A2B2)` + `set_lanes(edge_id=B0C0, lanes=1)`

### `R043.ca` rep 3 — ambiguity_detection

> Simuleu DEV-NET amb l'aresta A2B2 eliminada i amb l'aresta B0C0 reduïda a una sola carril, i informeu el temps de viatge mitjà.

Gold: expect `ambiguities[]` (one run with both changes or one run each, intent `counterfactual`)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_travel_time
- arm `treatment`: `remove_edge(edge_id=A2B2)` + `set_lanes(edge_id=B0C0, lanes=1)`

### `R043.de-technical` rep 2 — ambiguity_detection

> Simuliere DEV-NET ohne Kante A2B2 und mit Kante B0C0 auf einer Fahrspur; gib die mittlere Reisezeit an.

Gold: expect `ambiguities[]` (one run with both changes or one run each, intent `counterfactual`)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_travel_time
- arm `treatment`: `remove_edge(edge_id=A2B2)` + `set_lanes(edge_id=B0C0, lanes=1)`

### `R043.de-technical` rep 3 — ambiguity_detection

> Simuliere DEV-NET ohne Kante A2B2 und mit Kante B0C0 auf einer Fahrspur; gib die mittlere Reisezeit an.

Gold: expect `ambiguities[]` (one run with both changes or one run each, intent `counterfactual`)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_travel_time
- arm `treatment`: `remove_edge(edge_id=A2B2)` + `set_lanes(edge_id=B0C0, lanes=1)`

### `R043.en-colloquial` rep 1 — ambiguity_detection

> Hey, can you simulate DEV-NET with edge A2B2 removed and with edge B0C0 cut down to just one lane? I need the mean travel time.

Gold: expect `ambiguities[]` (one run with both changes or one run each, intent `counterfactual`)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_travel_time
- arm `treatment`: `remove_edge(edge_id=A2B2)` + `set_lanes(edge_id=B0C0, lanes=1)`

### `R043.en-colloquial` rep 3 — ambiguity_detection

> Hey, can you simulate DEV-NET with edge A2B2 removed and with edge B0C0 cut down to just one lane? I need the mean travel time.

Gold: expect `ambiguities[]` (one run with both changes or one run each, intent `counterfactual`)

Parsed: intent `counterfactual` · network `DEV-NET` · metrics mean_travel_time
- arm `treatment`: `remove_edge(edge_id=A2B2)` + `set_lanes(edge_id=B0C0, lanes=1)`

### `R073` rep 2 — intent

> With the peak demand on DEV-NET, where do the teleports come from?

Gold: intent `diagnose` · network `DEV-NET` · demand `peak` · metrics teleports

Parsed: intent `describe` · network `DEV-NET` · demand `peak` · metrics teleports

### `R073.ca` rep 2 — intent

> Amb la demanda de l'hora punta a DEV-NET, d'on provenen els teleports?

Gold: intent `diagnose` · network `DEV-NET` · demand `peak` · metrics teleports

Parsed: intent `describe` · network `DEV-NET` · demand `peak` · metrics teleports

