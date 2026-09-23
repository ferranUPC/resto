# Input Parser benchmark — smoke-v2

9 requests, 9 runs (repetitions [1]), models ['deepseek/deepseek-v4.1-flash'], parser ['v2']; $0.0100, mean 4736 input / 662 output tokens; stop reasons {'output': 9}.

| Metric | Result | E5.1 threshold | Met |
|---|---|---|---|
| schema_validity | 100.0 % (9/9) | ≥ 98% | yes |
| intent | 85.7 % (6/7) | ≥ 85% | yes |
| interventions | 100.0 % (7/7) | ≥ 85% | yes |
| topology_changes | 100.0 % (7/7) | ≥ 85% | yes |
| metrics_of_interest | 100.0 % (7/7) | ≥ 85% | yes |
| ambiguity_detection | 100.0 % (2/2) | ≥ 80% | yes |
| arm_structure | 100.0 % (3/3) | ≥ 90% | yes |

Reported, not graded:

- arm_structure_single: 100.0 % (4/4)
- required_arms: 100.0 % (3/3)
- spurious_ambiguity: 0.0 % (0/7)
- used_shorthand: 100.0 % (4/4)
- network_ref: 100.0 % (7/7)
- demand_ref: 100.0 % (7/7)
- time_window: 100.0 % (7/7)
- consistency across variants: —

## By category

| category | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| adversarial | 100.0 % (1/1) | 100.0 % (1/1) | 100.0 % (1/1) | 100.0 % (1/1) | 100.0 % (1/1) | — | — |
| ambiguous | 100.0 % (1/1) | — | — | — | — | 100.0 % (1/1) | — |
| combined | 100.0 % (1/1) | 100.0 % (1/1) | 100.0 % (1/1) | 100.0 % (1/1) | 100.0 % (1/1) | — | — |
| multi_arm | 100.0 % (3/3) | 66.7 % (2/3) | 100.0 % (3/3) | 100.0 % (3/3) | 100.0 % (3/3) | — | 100.0 % (3/3) |
| out_of_scope | 100.0 % (1/1) | — | — | — | — | 100.0 % (1/1) | — |
| single | 100.0 % (2/2) | 100.0 % (2/2) | 100.0 % (2/2) | 100.0 % (2/2) | 100.0 % (2/2) | — | — |

## By split

| split | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| dev | 100.0 % (9/9) | 85.7 % (6/7) | 100.0 % (7/7) | 100.0 % (7/7) | 100.0 % (7/7) | 100.0 % (2/2) | 100.0 % (3/3) |

## By lang

| lang | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| en | 100.0 % (9/9) | 85.7 % (6/7) | 100.0 % (7/7) | 100.0 % (7/7) | 100.0 % (7/7) | 100.0 % (2/2) | 100.0 % (3/3) |

## By style

| style | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| plain | 100.0 % (9/9) | 85.7 % (6/7) | 100.0 % (7/7) | 100.0 % (7/7) | 100.0 % (7/7) | 100.0 % (2/2) | 100.0 % (3/3) |

## By vague

| vague | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| none | 100.0 % (9/9) | 85.7 % (6/7) | 100.0 % (7/7) | 100.0 % (7/7) | 100.0 % (7/7) | 100.0 % (2/2) | 100.0 % (3/3) |

## By noise

| noise | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| none | 100.0 % (9/9) | 85.7 % (6/7) | 100.0 % (7/7) | 100.0 % (7/7) | 100.0 % (7/7) | 100.0 % (2/2) | 100.0 % (3/3) |

## Failures (1)

### `R026` rep 1 — intent

> On DEV-NET, what would happen to the mean delay if edge C0D0 were closed from 08:00 to 08:30, if edge B2C2 were limited to 30 km/h over the same period, and if both were done together? Measure each against the normal situation.

Gold: intent `counterfactual` · network `DEV-NET` · metrics mean_delay
- arm `closure`: `edge_closure(C0D0, 08:00–08:30)`
- arm `speed_limit`: `speed_limit(B2C2, speed=8.333, 08:00–08:30)`
- arm `both`: `edge_closure(C0D0, 08:00–08:30)` + `speed_limit(B2C2, speed=8.333, 08:00–08:30)`
- contrasts: `closure` vs `base`, `speed_limit` vs `base`, `both` vs `base`

Parsed: intent `compare` · network `DEV-NET` · metrics mean_delay
- arm `closure`: `edge_closure(C0D0, 08:00–08:30)`
- arm `speed_limit`: `speed_limit(B2C2, speed=8.333, 08:00–08:30)`
- arm `closure_and_speed_limit`: `edge_closure(C0D0, 08:00–08:30)` + `speed_limit(B2C2, speed=8.333, 08:00–08:30)`
- contrasts: `closure` vs `base`, `speed_limit` vs `base`, `closure_and_speed_limit` vs `base`

