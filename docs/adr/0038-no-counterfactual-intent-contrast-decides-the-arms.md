# ADR-0038: No `counterfactual` intent; a contrast decides which arms are simulated

- Status: Accepted (2026-10-05, E3.7 review of the Coordinator gold). Replaces the `counterfactual` row of
  [ADR-0025](0025-executor-plan-shape-intent-rules-and-failures.md) §2 and the `counterfactual` rule in
  [ADR-0027](0027-experiment-arms-and-contrasts.md) §2 (`reference_arms`); replaces the `intent` definitions
  of 2026-09-24 in `eval/decisions-log.md`. Where it says "the Coordinator", read "the planner", a deterministic function
  ([ADR-0039](0039-deterministic-planner-replaces-the-coordinator.md), proposed). Built by refactors r9 (planning rule), r10 (request bank
  gold) and r11 (Parser, then the enum), and by E3.7 and E5.2 on top of them
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.3 (`Question`),
  §2.4 (Coordinator, Network Expert), §4.1, §4.2; ADR-0023 decision 3, ADR-0025, ADR-0027

## Context

`counterfactual` meant three things:

1. An `Intent` value: "the effect of a change, against today or against another setup" (2026-09-24).
2. A planning rule: in phase 0 plan only the reference side of the contrasts, and let the Expert ask for
   the treatment with `needs_simulation` (ADR-0025 §2).
3. A family of Expert benchmark questions (`-cf-dir`, `-cf-topk`, `-cf-band`) answered in forced mode from
   stored results. That one is a family of evaluation questions, not an intent.

The planning rule has no use. A question that names a change always needs the treatment simulated, so the
Expert always asks for it, and the round trip through phase 0 only delays what the plan already knows.
Predicting from stored results without simulating is what forced mode is for. The intent also had no stable
boundary: the same annotator labelled the same requests differently in two rounds (72 % strict agreement
on 2026-09-24). Its only effect on code was `reference_arms`; `run` and `compare` already plan the same arms.

## Decision

**1. Intents are `describe`, `diagnose`, `compare` and `run`.** `counterfactual` is removed.

- `compare`: the answer is a contrast between arms, the base included. "What happens to the mean delay if
  C1C2 is closed" and "which is better, the closure or the retiming" are both `compare`.
- `run`: the figures of one setup, with nothing to compare them against. "What is the mean speed on B1C1
  if C1C2 is closed" is `run`.
- When in doubt, `compare`. A needless base is almost free: the base is usually stored and identical
  scenarios deduplicate by `scenario_id`. A missing base costs the Expert a round.

**2. A contrast decides which arms are planned.** The default contrast of each arm against the base
(`effective_contrasts`) applies to `compare` only. A `run` has no contrast: its arms are the declared ones
and the base is not planned unless the question lists it as an arm. `describe` and `diagnose` still plan the
base arm.

**3. Phase 0 plans every arm the question needs.** The treatment is never held back for the Expert to
request. Phases >= 1 are for what the Expert asks for after reading the results: another demand, window or
arm. ADR-0023 decision 3 (the loop, `max_rounds`) is unchanged.

**4. Forced mode only forbids abstaining.** The Expert answers and `basis` follows what the data covers:
`observed` when a stored simulation matches the situation exactly, `extrapolated` only when none does. Forced
mode does not imply `extrapolated`; the v1.0 sentence that says so is imprecise and the code never enforced it.

**5. The `-cf-*` benchmark family keeps its name.** It is a family of evaluation questions answered in
forced mode, not an intent, and its sweep (E4.4) is closed. Documentation says so; nothing is renamed.

## Consequences

- `Intent.COUNTERFACTUAL`, `reference_arms` and the `counterfactual` branch of `needed_arms` are deleted;
  `needed_arms` keeps its other branches. The `Question` docstring ("a hypothesis is `counterfactual`/
  `compare`") changes.
- `effective_contrasts` needs the intent: no default contrast for `run`. A `run` with the shorthand has one
  arm, `treatment`, and no base. R067 and R071 in the plan bank are `run` and lost their base arm for this
  reason.
- The orientation rule of ADR-0027 §1 (the contained arm is the reference) stays, because the Expert's
  `Change` values and the Composer's claims need a known reference. Its stated motivation (phase 0 plans the
  reference side) no longer applies.
- The Input Parser prompt (v7) and its contract lose one intent and gain the `run`/`compare` boundary above.
  Stored Parser runs score intent against the old gold and must be re-scored or marked superseded.
- The request bank (E3.4): concepts with gold `counterfactual` move to `compare` or `run`; `ALSO_ACCEPTED`
  for the "simulate X and report Y" concepts is revisited. The plan bank (E3.7): gold plans are regenerated,
  the 24 phase-1 cases and `eval/plan_bank/phase1.*` are dropped or reduced to cases where the Expert
  really asks for more, and the review page is rebuilt. The Coordinator spec (E5.2) and E5.5 follow.
- Abstention recall (free mode) is measured on questions whose forced answer is wrong, not on withheld
  treatments. The bank needs enough of those.

## Alternatives considered

- **Keep `counterfactual` and plan the treatment in phase 0.** Then it differs from `compare` only in the
  word, and the intent boundary stays unstable for nothing.
- **Fold "what if X" into `run`.** Rejected: `run` would then include a contrast with the base and stop
  meaning "the figures of a setup".
- **Let the Coordinator decide per request whether to simulate the treatment.** Rejected in ADR-0025 and
  still rejected: gold plans become a matter of taste.
