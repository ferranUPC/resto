# Output Composer tuning log

- Status: living document, started 2026-10-07
- Purpose: record each real run of the Output Composer with the prompt version it used, its cost and
  the maintainer's reading of the prose. Same role as the [Expert's log](expert-tuning-log.md).
- Related: E5.4 ticket 05 (`.scratch/e5-4-composer-minimal/issues/05-manual-run-cheap-model.md`).

Running total spent: **about $0.10** (first run $0.0019, DEV-NET runs below, `v3` run $0.018).

## 2026-10-07, composer `v1`, first manual run

- **Script:** `scripts/manual_composer_run.py --run` on branch `e5-4-composer-minimal` (not merged
  into `master` at the time of the run). Not part of the suite.
- **Model and budget:** `deepseek/deepseek-v4.1-flash`, 6 steps, 2048 output tokens, 120 s.
- **Estimate before the run:** at most $0.011 (6 steps at 4000 input tokens, 2048 output tokens each).
  Development run, below the $1 limit in `docs/llm-cost-policy.md`.
- **Study:** built in the same process from invented numbers (baseline and closure of lane 1 of E12,
  mean delay 37.5 s versus 42.0 s). The Expert's answer is hand-written, so this run tests how the
  model writes up a given answer, not what a real Expert produces.
- **Result:** 4 model steps (`get_study`, `get_result` twice, `submit_output`), stop reason `output`,
  7802 input and 1248 output tokens. Cost $0.0019 by `estimate_cost_usd`; `usage.cost_usd` reports
  $0.0012 (see follow-up 5). `compose_report` accepted the draft.
- **Maintainer's reading of the prose:** see the closing note at the end of this log.

### Rendered report

```markdown
# Study st-1: report

> what if we close lane 1 of E12 at peak?

## Summary

Closing lane 1 of E12 for the 07:00-10:00 peak makes the corridor noticeably slower but does not break it. Mean delay rises from 37.5 s to 42.0 s, about a 12 % increase, and mean travel time rises from 281 s to 300 s. Neither run produced teleports, and 497 of 500 vehicles arrived in the baseline against 498 of 500 with the lane closed, so the closure moves delay around rather than causing gridlock. The largest time loss shifts onto E12 itself.

### What was compared

The study ran one baseline scenario on the network as obtained and one treatment scenario that closes lane 1 of edge E12 for the peak window, with the same demand in both. Each scenario was run with a single seed, so the comparison is a like-for-like pairing of a baseline run and a closure run rather than an average over many replications.

### What the numbers mean

Mean delay per vehicle grows from 37.5 s to 42.0 s, a relative increase of about 12 %, and mean travel time grows from 281 s to 300 s. Both measures move in the same direction, which is the expected signature of a lost lane: vehicles spend more time waiting and take longer to complete their trips. The magnitude is moderate rather than dramatic, so the corridor absorbs the closure without collapsing.

### Whether the network coped

The network-level health indicators stay clean. Teleports are zero in both runs, meaning no vehicle had to be removed from the simulation because it was stuck. Arrivals are 497 of 500 departed in the baseline and 498 of 500 with the lane closed, so essentially the same share of demand clears the network in both cases. Together these indicate the closure redistributes delay instead of producing gridlock.

### Where the delay lands

With lane 1 closed, the largest time loss shifts to E12 itself. In other words the delay is concentrated on the edge that lost capacity rather than being pushed out into the surrounding network as a whole.

## Claims

- Mean delay rises from 37.5 s in the baseline to 42.0 s with lane 1 of E12 closed. (value: 37.5 s -> 42.0 s; evidence: `res0`, `res1`)
- The increase in delay is about 12 % relative to the baseline. (value: 12%; evidence: `res0`, `res1`)
- Mean travel time rises from 281 s in the baseline to 300 s with the lane closed. (value: 281 s -> 300 s; evidence: `res0`, `res1`)
- No vehicle teleported in either the baseline or the closure run. (value: 0; evidence: `res0`, `res1`)
- 497 of 500 vehicles arrived in the baseline and 498 of 500 arrived with the lane closed, so the closure does not cause gridlock. (value: 497/500 vs 498/500; evidence: `res0`, `res1`)
- The largest time loss moves to E12 itself when the lane is closed. (value: E12; evidence: `res1`)

## Evidence

| Ref | Kind | Description |
| --- | --- | --- |
| `res0` | artifact | baseline: mean_delay 37.5 s, travel time 281 s |
| `res1` | artifact | closure: mean_delay 42.0 s, travel time 300 s |

## Experiments

| Phase | Arm | Role | Scenario | Results | Origin |
| --- | --- | --- | --- | --- | --- |
| 0 | base | baseline | s0 | 1 | reused |
| 0 | treatment | treatment | s1 | 1 | run now |

## Mode and basis

Mode: free. Basis: observed.

## Limitations

None stated.
```

### Follow-ups the run exposed (not fixed)

1. **The prompt's "no reasoning of your own" is only partly followed.** The sections add interpretation
   the Expert did not state: "the expected signature of a lost lane", "the corridor absorbs the closure
   without collapsing", "the delay is concentrated on the edge that lost capacity rather than being
   pushed out into the surrounding network". The last one contradicts nothing in the evidence but is not
   in it either.
2. **The same content appears three times.** The summary, the "What the numbers mean" and "Whether the
   network coped" sections, and the claims repeat the same figures.
3. **Heading levels in the renderer.** The model's sections render as `###` right under `## Summary`,
   so they read as a subsection of the summary.
4. **One claim cites a single result for a comparison.** "The largest time loss moves to E12" cites only
   `res1`, and the invented evidence has no per-edge data that backs it. E5.7 (numbers in claims against
   the artifact) is the check that would catch this class.
5. **Cost figures disagree.** `usage.cost_usd` is $0.0012 and `estimate_cost_usd` on the same token
   counts gives $0.0019. Which one the tuning logs should quote is undecided.
6. **Input size.** 7802 input tokens over 4 steps for a one-phase study, mostly from `get_study` being
   resent at each step. A study with several phases will grow this quickly.

## 2026-10-07, composer `v1` and `v2`, DEV-NET end to end

- **Script:** `scripts/manual_study_run.py --run` (saved in `.scratch/e5-4-composer-minimal/manual-run-scripts.patch`).
  The Network Author and the Demand Generator are stubs that answer `Found` with DEV-NET and its `peak`
  demand; Parser, planner, Builder, SUMO, Expert, note writer and Composer are real.
- **Question:** "on dev-net, how does the mean delay change at peak if we close edge B1C1 between 08:00
  and 09:00?". Earlier phrasings stopped at the Parser (asked for the window), at the planner (no
  network named) or at the Expert's budget ("what happens at peak ...", 6 steps and 2048 tokens).
- **Model and budget:** `deepseek/deepseek-v4.1-flash`, per-call budget 6 steps and 2048 tokens, study
  cap 200k tokens. Estimate before the runs: at most $0.05 each.
- **Cost (sum of `usage` in the study traces):** `v1` run $0.016, the failed run before it $0.029, `v2`
  run $0.035 (the Expert varies between runs). Parser-only attempts cost a fraction of a cent.
- **Maintainer's reading:** `v1`, too much text: four sections that repeat the same figures, and the
  report is too separated. `v2`, much shorter, and the maintainer wants it shorter still and readable in
  a plain terminal (ticket 06). The reading of the content itself is in the closing note.

### `v1` report

```markdown
# Study 9b3054af14e84df88e809f571f4a9402: report

> on dev-net, how does the mean delay change at peak if we close edge B1C1 between 08:00 and 09:00?

## Summary

Closing edge B1C1 on dev-net between 08:00 and 09:00 (the peak) makes mean delay much worse. Baseline mean delay over 3 seeds is 28.23 s (std 0.20 s); with the closure in place it rises to 92.87 s (std 4.57 s). That is an increase of +64.64 s, or +229 % relative to the baseline. The network also loses throughput and starts producing teleports, so the closure causes severe queuing and spillback rather than merely rerouting traffic.

### What was compared

The study ran a baseline arm in which the dev-net network and its peak demand are left unchanged, with no interventions at all, and a treatment arm in which the single change is an edge closure on edge B1C1 applied over the window from 08:00 to 09:00 (seconds 28800 to 32400). Both arms use the same network and the same peak demand, so the only difference between them is the closure. Each arm was run over 3 seeds, and the metric of interest is the network mean delay.

### How the numbers were produced

The two arms' results were aggregated across their 3 seeds and compared. The reported baseline and treatment figures are the means of the per-seed mean delay, and the spread around each mean is given as a standard deviation. The change is reported both as an absolute difference in seconds and as a relative percentage change against the baseline mean.

### What the delay numbers show

Mean delay rises from 28.23 s at baseline to 92.87 s under the closure, a delta of +64.64 s, which is +229 % relative to baseline. The closure arm is also noticeably more variable across seeds (std 4.57 s versus 0.20 s at baseline), reflecting that the network is operating under stressed conditions where small seed-to-seed differences matter more.

### Throughput and teleports

The delay increase is not the whole story. The number of vehicles that arrived falls by 142.3 (-12.2 %) and the number that departed by 40.0 (-3.3 %) relative to the baseline. In addition, the closure runs generate 34 teleports per run, whereas baseline runs generate none. Teleports typically indicate vehicles that cannot be accommodated and are effectively removed from the network, which together with the loss of arrivals points to heavy queuing and spillback rather than smooth rerouting around the closed edge.

## Claims

- The treatment changed exactly one thing: an edge closure on edge B1C1 over the window 08:00-09:00, i.e. seconds 28800 to 32400. (evidence: `q8`)
- The baseline arm has no interventions, so it is the unchanged network and demand and serves as the reference for the comparison. (evidence: `q7`)
- Baseline network mean delay is 28.227 s, averaged over 3 seeds with a standard deviation of 0.2 s. (value: 28.227 s; evidence: `q9`)
- With edge B1C1 closed during 08:00-09:00, network mean delay is 92.87 s, averaged over 3 seeds with a standard deviation of 4.574 s. (value: 92.87 s; evidence: `q9`)
- Closing B1C1 increases mean delay by 64.643 s, a relative change of +229.0 % against baseline. (value: +229.0 %; evidence: `q9`)
- The closure reduces arrived vehicles by 142.333 (-12.2 %) relative to baseline. (value: -12.2 %; evidence: `q9`)
- The closure reduces departed vehicles by 40.0 (-3.3 %) relative to baseline. (value: -3.3 %; evidence: `q9`)
- Treatment runs produce 34 teleports per run, whereas baseline runs produce none (0.0). (value: 34 teleports per run; evidence: `q9`)

## Evidence

| Ref | Kind | Description |
| --- | --- | --- |
| `q8` | query | edge_closure target B1C1 window {start 28800, end 32400} |
| `q7` | query | baseline scenario, interventions [] |
| `q9` | query | arrived delta -142.333 (-12.2%), departed delta -40.0 (-3.3%), teleports baseline 0.0 treatment 34.0 |

## Experiments

| Phase | Arm | Role | Scenario | Results | Origin |
| --- | --- | --- | --- | --- | --- |
| 0 | base | baseline | 2b6cb38a606d234d0443efd54844dbb98baf3ca3044ec5ed26e53f0ac30af23c | 3 | reused |
| 0 | treatment | treatment | 6b06b10a4f53cce948924adac6aa1e88e9a0a9d2d540da31761a06ca9ac69dfa | 3 | reused |

## Mode and basis

Mode: free. Basis: observed.

## Limitations

None stated.
```

### `v2` report

```markdown
# Study 6210f069eca740f3b94a56d03ab2d569: report

> on dev-net, how does the mean delay change at peak if we close edge B1C1 between 08:00 and 09:00?

## Summary

On dev-net, closing edge B1C1 between 08:00 and 09:00 (the peak hour) raises the network-wide mean delay sharply: from 28.227 s (std 0.20) without the closure to 92.87 s (std 4.57) with it, a mean increase of 64.643 s, or +229.0%.

### Comparison basis

Each arm's mean delay is the average of three simulation runs (seeds 1-3) on the same dev-net demand: the baseline arm with no interventions, and the treatment arm with the B1C1 closure applied over the 08:00-09:00 window.

## Claims

- The reported mean-delay figures are averages over three runs per arm (seeds 1-3). (evidence: `q9`, `q7`)
- The treatment arm applies an edge closure on edge B1C1 over the window 28800-32400 s (08:00-09:00). (evidence: `q8`)
- The baseline arm has no interventions. (evidence: `q7`)
- With the closure, arrivals fall from 1168 to 1025.7, a decrease of 12.2%. (evidence: `q9`)
- With the closure, 34 teleports occur, against 0 in the baseline. (evidence: `q9`)
- With the closure, departures fall from 1200 to 1160. (evidence: `q9`)

## Evidence

| Ref | Kind | Description |
| --- | --- | --- |
| `q9` | query | mean_delay: baseline mean 28.227 std 0.2, treatment mean 92.87 std 4.574, delta 64.643, relative_change_pct 229.0 |
| `q7` | query | baseline scenario 2b6cb38a... interventions: [] |
| `q8` | query | interventions: edge_closure target B1C1 window 28800-32400 |

## Experiments

| Phase | Arm | Role | Scenario | Results | Origin |
| --- | --- | --- | --- | --- | --- |
| 0 | base | baseline | 2b6cb38a606d234d0443efd54844dbb98baf3ca3044ec5ed26e53f0ac30af23c | 3 | reused |
| 0 | treatment | treatment | 6b06b10a4f53cce948924adac6aa1e88e9a0a9d2d540da31761a06ca9ac69dfa | 3 | reused |

## Mode and basis

Mode: free. Basis: observed.

## Limitations

None stated.
```

### Follow-ups (ticket 06 covers them)

1. Too much text: the prompt lets the model write sections that describe the method and repeat the
   summary.
2. The answer's headline figure (+229 %) is in the summary but in no claim, so nothing checks it (E5.7).
3. Method statements appear as claims ("the baseline arm has no interventions").
4. The model's sections render as `###` under `## Summary`.
5. The experiments table has 64-character scenario ids: unreadable in an 80-column terminal.
6. A plain terminal gets raw Markdown: a plain-text renderer, `--format` and `report.md` are ticket 06.

## 2026-10-07, composer `v3`, DEV-NET end to end (ticket 06)

- **Script:** `scripts/manual_study_run.py --run`, same as the `v1` and `v2` runs, now printing the
  plain-text render first and the Markdown after it.
- **Question:** the same as before ("on dev-net, how does the mean delay change at peak if we close
  edge B1C1 between 08:00 and 09:00?").
- **Model and budget:** `deepseek/deepseek-v4.1-flash`, per-call budget 6 steps and 2048 tokens, study
  cap 200k tokens. Estimate before the run: at most $0.052 (script worst case), expected $0.02 to
  $0.04. Development run, below the $1 limit in `docs/llm-cost-policy.md`.
- **Cost (sum of `usage` in the traces):** $0.0164 for the completed study (8 model calls, 119007
  input and 7296 output tokens; `estimate_cost_usd` gives $0.0222). A first attempt stopped at the
  Parser, which asked what "at peak" means, and cost $0.0014. Total $0.018.
- **Maintainer's reading:** pending.

### `v3` report (plain text, as printed on a terminal)

```text
STUDY e109fa96  (completed)
Question: on dev-net, how does the mean delay change at peak if we close edge B1C1 between 08:00 and 09:00?

SUMMARY
Closing edge B1C1 on dev-net for the 08:00–09:00 peak raises network mean delay sharply, from 28.23 s (±0.20) without the closure to 92.87 s (±4.57) with it: a +64.6 s increase, about +229 %. Mean travel time rises from 94.36 s to 158.35 s (+67.8 %) and arrivals drop from 1168 to 1026 (−12.2 %). Teleports appear under the closure (0 → 34 veh), so the traffic does not divert cleanly and queues build up at the peak.

CLAIMS
  - Baseline mean delay on dev-net is 28.23 s (±0.20) and rises to 92.87 s (±4.57) when edge B1C1 is closed for the 08:00–09:00 peak. [value: 28.23 s to 92.87 s] [evidence: q9]
  - The mean delay change from closing B1C1 is an increase of 64.6 s, about +229 %. [value: +64.6 s (+229 %)] [evidence: q9]
  - Mean travel time rises from 94.36 s to 158.35 s with the closure, a change of +67.8 %. [value: +67.8 %] [evidence: q9]
  - Arrivals drop from 1168 to 1026 with the closure, a change of −12.2 %. [value: −12.2 %] [evidence: q9]
  - Teleports appear under the closure, going from 0 to 34 veh. [value: 0 → 34 veh] [evidence: q9]

EVIDENCE
  q9  query  mean_delay baseline 28.227 (±0.2, 3 runs) vs treatment 92.87 (±4.574, 3 runs), delta 64.643, relative_change_pct 229.0; mean_travel_time 94.363 -> 158.347; teleports 0 -> 34

EXPERIMENTS
  phase 0  base       baseline   scenario 2b6cb38a  3 results  run now
  phase 0  treatment  treatment  scenario 6b06b10a  3 results  run now

MODE AND BASIS
  free, observed

LIMITATIONS
  None stated.
```

### What the run shows against ticket 06

1. No sections, no method claims and no Markdown in the prose: the first three points hold.
2. The answer to the question (+64.6 s, +229 %) is now a claim with `q9`. Every figure of the summary
   has a claim.
3. Figures keep one precision in the report (28.23 s, 92.87 s, +64.6 s). The evidence line keeps the
   Expert's own digits (28.227), which the Composer does not write.
4. Not fully met: the last sentence of the summary ("so the traffic does not divert cleanly and queues
   build up at the peak") states a mechanism. The traces of the run do not contain the word "queue", so the Expert did not state it: the prompt
   point "no causes or mechanisms" is only partly followed by this model.
5. Scenario ids are 8 characters, columns line up, and the experiments show `run now` (the stores were
   fresh, unlike the `v1` and `v2` runs).

## Closing note, 2026-10-07

The maintainer ran what was needed for now (the three runs above, then `v3` with the plain-text renderer
from ticket 06) and closed E5.4's tickets 05 and 06. The prose is judged good enough to move on, not
final: the Composer gets its real evaluation with the golden paths (E9.1), on real Expert answers
instead of the hand-written one of the first run. Open for then: the traceability checker and the
faithfulness rubric (E5.7), and a `v3` run on DEV-NET, which was not repeated here.
