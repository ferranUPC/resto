# PROTOTYPE — DAG of pending tasks with the critical path

> Throwaway asset for wayfinder ticket [Prototype: DAG of pending tasks with the critical path](https://github.com/ferranUPC/resto/issues/5)
> (map: [Re-baseline the TFM work plan (v0.3)](https://github.com/ferranUPC/resto/issues/1)). Lives on branch
> `prototype/dag-pending-tasks`, never on `master`. The validated DAG goes into `tfm-work-plan.md` v0.3.
> State as of 2026-09-24. Numbers on nodes are plan hours, read as **story points** (ticket "ADR-0028
> clock-time migration"), not wall-clock time.

Sources: work plan §1/§4, tracker notes, ADR-0023/0025/0026/0027/0028, the resolutions of "Inventory of
pending paid runs", "What does ✅ mean…" and "ADR-0028 clock-time migration". ✅ tasks are left out (all
their edges are satisfied); ⏳ tasks (built, only a measurement missing) appear because they still feed
milestones.

## 1. Build DAG (everything that must be built before Validation 2)

Thick arrows (`==>`) are the critical chains; dotted arrows come from risk nodes.

```mermaid
flowchart LR
  classDef frontier fill:#dff5e1,stroke:#2e7d32,stroke-width:2px,color:#000
  classDef pending fill:#fff,stroke:#555,color:#000
  classDef await fill:#fff4d6,stroke:#b8860b,color:#000
  classDef risk fill:#fde2e2,stroke:#c62828,stroke-dasharray:5 3,color:#000
  classDef ms fill:#1f3b73,stroke:#1f3b73,color:#fff

  ADR27{{"RISK: ADR-0027 still Proposed<br/>(arms & contrasts)"}}:::risk
  XNET{{"RISK: multi-network ExpertTask<br/>(decided inside E5.3)"}}:::risk

  subgraph EXPERT["Expert on DEV-NET"]
    E38["E3.8 clock-time migration · 10"]:::frontier
    E42["E4.2 descriptive (dev sweep) · 14"]:::pending
    E43["E4.3 diagnostic (dev sweep) · 18"]:::pending
    E44["E4.4 counterfactual (dev sweep) · 24"]:::pending
    E45["E4.5 free mode ⏳"]:::await
  end

  subgraph SPINE["Coordinator spine"]
    E37["E3.7 plan bank · 7"]:::pending
    E52["E5.2 Coordinator Min · 12"]:::pending
    E53["E5.3 loop closure · 14"]:::pending
    E54["E5.4 Composer Min · 6"]:::frontier
    E51["E5.1 Input Parser ⏳"]:::await
    E71["E7.1 golden-path fw, GP-1…5 · 10"]:::pending
    E55["E5.5 Coordinator Done (build) · 18"]:::pending
    E57["E5.7 traceability checker · 12"]:::pending
    E56["E5.6 capability neg. + GP-10 · 8"]:::pending
  end

  subgraph RUNNER["Runner online + Builder Done"]
    E25["E2.5 sandbox + online Runner · 24"]:::frontier
    E26["E2.6 Builder scripts · 14"]:::pending
    E27["E2.7 Builder bank (build) · 14"]:::pending
    E72["E7.2 GP-6, GP-7 · 6"]:::pending
    E73["E7.3 failure injection · 10"]:::pending
  end

  subgraph GEN["Generators + REAL-NET"]
    E61["E6.1 Network Author Min · 16"]:::frontier
    E62["E6.2 Demand Generator Min · 10"]:::frontier
    E63["E6.3 REAL-NET clean + freeze · 16"]:::frontier
    E64["E6.4 Network Author Done · 24"]:::pending
    E65["E6.5 Demand Gen Done · 26"]:::pending
    E66["E6.6 REAL-NET profiles · 6"]:::pending
    E35["E3.5 REAL-NET matrix · 8"]:::pending
    E36["E3.6 REAL-NET question bank · 6"]:::pending
    E48["E4.8 Expert on REAL-NET (port+tune) · 24"]:::pending
    E49["E4.9 learning-effect setup · 18"]:::pending
    E67["E6.7 GP-8, GP-11 · 8"]:::pending
  end

  M2(("M2<br/>13 Nov")):::ms
  M3(("M3<br/>11 Dec")):::ms
  M4(("M4<br/>15 Jan")):::ms
  M5(("M5<br/>29 Jan")):::ms
  M6(("M6<br/>5 Feb")):::ms

  %% Expert
  E38 --> E42 & E43 & E44
  E42 & E43 & E44 & E45 --> M2

  %% Coordinator spine (critical for M3, M4, M6)
  E38 ==> E37 ==> E52 ==> E53 ==> E71 ==> E72
  E71 ==> E67 ==> E73
  E52 --> E55
  E37 --> E55
  E45 --> E53
  E51 --> E71
  E54 --> E71
  E54 --> E57
  E71 --> E56
  E62 --> E56

  %% Runner / Builder
  E25 --> E26 --> E27
  E26 --> E72
  E25 --> E73
  E72 --> E73
  E72 & E27 --> M3

  %% Generators + REAL-NET (critical for M5)
  E61 & E62 & E63 --> E64
  E61 & E62 & E63 --> E65
  E61 & E62 --> E67
  E61 --> E73
  E63 ==> E66 ==> E35 ==> E36 ==> E48 ==>|"? network not fixed by DoD"| E49
  E64 & E65 & E35 & E67 --> M4
  E48 & E49 --> M5
  E55 & E56 & E57 & E73 --> M6

  %% risks
  ADR27 -.-> E37 & E52 & E54 & E67
  XNET -.-> E53 & E67
```

Not drawn, no prerequisite and off every chain: **E8.1** outline + SoA (16), **EVB** evaluation-budget
document (~5, dated ~24 Oct, before the funding request), **DLT** trim of `evaluating-resto.md`'s
Decisions log (~2), E8.2/E8.3/E8.4 (rolling chapters).

## 2. Measurement DAG (what turns ⏳ into ✅)

Per "What does ✅ mean…": measurement suites run only inside a validation pass. Costs from "Inventory of
pending paid runs"; $30 cap for both passes.

```mermaid
flowchart LR
  classDef pass fill:#1f3b73,stroke:#1f3b73,color:#fff
  classDef suite fill:#e8eefc,stroke:#1f3b73,color:#000
  classDef task fill:#fff,stroke:#555,color:#000
  classDef risk fill:#fde2e2,stroke:#c62828,stroke-dasharray:5 3,color:#000

  M3(("M3 · 11 Dec")):::pass
  BUILT(("all built<br/>(end of §1 DAG)")):::pass
  V1{{"Validation 1 · mid-Dec<br/>dev splits, interim, turns nothing ✅"}}:::pass
  V2{{"Validation 2 · before E8.5<br/>definitive, each suite once"}}:::pass
  FRZ{{"CONFLICT: code freeze E7.6 is 10 Feb,<br/>after V2 — V2 would measure unfrozen code"}}:::risk

  S1(["EXP-01 forced×3 + free abstention · $3.9–5.8"]):::suite
  S2(["N4 Parser held-out, 2nd use · ≈ $0.4"]):::suite
  S3(["Builder bank ×3 · $0.5–1.2"]):::suite
  S4(["Plan bank routing ×3 · $0.3–4.5"]):::suite
  S5(["Author GEN-LOCATIONS + derivation ×3 · $0.6–3"]):::suite
  S6(["Demand calibration · $0.2–1"]):::suite
  S7(["REAL-NET Expert ×3 · $1–2.5"]):::suite
  S8(["Learning effect 0/5/15/25 · $2–4"]):::suite
  S9(["Golden paths 11×3 · $1–3"]):::suite

  M3 --> V1
  BUILT --> V2
  FRZ -.-> V2
  V1 -.->|"reduced checkpoint"| S1 & S3 & S4
  V2 --> S1 & S2 & S3 & S4 & S5 & S6 & S7 & S8 & S9

  S1 --> T1["✅ E4.2 E4.3 E4.4 E4.5 · E4.7 report · 8"]:::task
  S2 --> T2["✅ E5.1 · Parser half of E5.8"]:::task
  S3 --> T3["✅ E2.7"]:::task
  S4 --> T4["✅ E5.5 · E5.8 · 8"]:::task
  S5 --> T5["✅ E6.4"]:::task
  S6 --> T6["✅ E6.5"]:::task
  S7 --> T7["✅ E4.8"]:::task
  S8 --> T8["✅ E4.9"]:::task
  S9 --> T9["✅ E7.5 · 10 · E7.4 · 6 · E5.7 rubric · GP-2 repro"]:::task

  S1 & S8 --> E410["E4.10 calibration + ablation · 8"]:::task
  T1 & T7 & T8 & E410 --> E85["E8.5 results · 20 · due 8 Feb"]:::task
  E85 --> E86["E8.6 discussion · 12"]:::task --> E87["E8.7 draft + revision · 20"]:::task --> E88(("M7 · 18 Feb")):::pass
  T9 --> E76["E7.6 code freeze · 12 · 10 Feb"]:::task --> E88
```

## 3. Critical paths (longest chain of pending build points to each milestone)

| Target | Points | Chain |
|---|---|---|
| M2 (build) | 34 | E3.8 → E4.4 |
| M3 (build) | 59 | E3.8 → E3.7 → E5.2 → E5.3 → E7.1 → E7.2 |
| M4 (build) | 61 | E3.8 → E3.7 → E5.2 → E5.3 → E7.1 → E6.7 |
| M5 (build) | 78 | E6.3 → E6.6 → E3.5 → E3.6 → E4.8 → E4.9 |
| M6 (build) | 71 | E3.8 → E3.7 → E5.2 → E5.3 → E7.1 → E6.7 → E7.3 |
| Validation 2 (all built) | 78 | = M5 chain |
| *Total pending build points* | *383* | |

After V2: E4.10 (8) → E8.5 (20) → E8.6 (12) → E8.7 (20) → E8.8 (8) = 68 points of tail, plus the V2
runs themselves.

## 4. What the DAG says (for the maintainer to react to)

1. **The plan is capacity-bound, not dependency-bound.** The longest chain is 78 of 383 pending build
   points (≈ 20 %). Order is mostly free; dates are set by how much fits per week, not by who waits for
   whom.
2. **One spine carries three milestones.** E3.8 → E3.7 → E5.2 → E5.3 → E7.1 is on the critical path of
   M3, M4 *and* M6: GP-8 and GP-11 (E6.7) need the Coordinator and the golden-path framework, so M4 is
   not only an E6 milestone.
3. **ADR-0027 (Proposed) sits at the root of that spine** (E3.7, E5.2, E5.4, E6.7 build on arms). It
   should be Accepted — or changed — before E3.7 starts, i.e. right after E3.8.
4. **E6.3 has no prerequisite.** The whole M5 chain (REAL-NET) can start any week; it is on the
   Christmas break only by calendar. Pulling E6.3 forward decouples M5 from the break.
5. **E4.9's network is not fixed by the DoD** (§4.7 says "held-out interventions at store sizes
   0/5/15/25", no network). On DEV-NET it leaves the REAL-NET chain: the M5 chain drops to 60 points and
   the learning-effect experiment can be set up as soon as E4.2–E4.4 are tuned.
6. **Frontier (no pending prerequisite):** E3.8, E2.5, E5.4, E6.1, E6.2, E6.3, E8.1, EVB, DLT.
7. **GP-9 (ambiguous request → `awaiting_user`) has no owning task.** Natural home: E7.1 (it starts at
   the Input Parser).
8. **Code freeze vs Validation 2.** V2 must finish before E8.5 (8 Feb) but E7.6 freezes code on 10 Feb,
   so the definitive measurements would run on code that can still change. Either a feature freeze
   before V2 or V2 counts as the freeze.
9. **Measurement-only tasks** (E4.7 report, E4.10, E5.8, E7.4, E7.5, E5.7's rubric half ≈ 50 points)
   all sit after V2 and before E8.5: that window is the real crunch of the calendar.
