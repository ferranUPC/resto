# RESTO — Study flow

Flow diagram (Mermaid) of how the Coordinator takes a `Question` from arrival to a closed
`Report`, including the branches for: an ambiguous question, dedup before calling an agent, a
failed step (with the single retry that `docs/tfm-architecture-and-dod.md` §8 lists as an open
question), and the Expert↔Simulation loop when the Network Expert asks for a simulation that
does not exist yet.

**Deliberate level of abstraction:** it does not try to enumerate every specialist or task type —
"call the specialist's use case" covers Network Author, Demand Generator, Scenario Builder and
Runner alike, because from the Coordinator's point of view they are the same shape of step (a
tool call that produces a `StepRecord`). See `docs/class_diagram.md` for the exact shape of every
type mentioned here (`Study`, `StepRecord`, `ExpertRound`, `Experiment`...).

```mermaid
flowchart TD

A(["A Question arrives"]) --> B{"Question.is_ambiguous?"}
B -- "yes" --> C["Study.status = AWAITING_USER<br/>(no steps yet)"]
C --> Z1(["End: waiting on user clarification"])

B -- "no" --> D["Coordinator writes the StudyPlan<br/>(mandatory before the first step)"]
D --> E["Take the next pending PlanStep<br/>(respecting depends_on)"]

subgraph STEP ["Run one step → one StepRecord"]
  F{"Does a result already exist<br/>for that id? (hash-based dedup)"}
  F -- "yes" --> G["Reuse the existing one —<br/>the agent is not called"]
  F -- "no" --> H["Call the specialist's use case<br/>(Network Author / Demand Gen /<br/>Scenario Builder / Runner)"]
  H --> I{"Result ok?"}
  I -- "failed" --> J{"Has this step already<br/>been retried once?"}
  J -- "no" --> K["Retry once<br/>with the corrected task"]
  K --> H
  J -- "yes" --> L["Study.status = FAILED<br/>(names the step that failed)"]
  I -- "ok" --> M["Store the StepRecord (ok)<br/>produced_ids added to the Study"]
  G --> M
end

E --> F
L --> Z2(["End: study failed"])
M --> N{"Any PlanSteps<br/>still pending?"}
N -- "yes" --> E
N -- "no" --> O["Coordinator calls ask_expert<br/>(Network Expert)"]

O --> P["Network Expert answers:<br/>ExpertAnswer (basis + evidence)"]
P --> Q{"needs_simulation?"}
Q -- "no" --> R["This ExpertRound closes"]
Q -- "yes" --> T{"rounds_left > 0?<br/>(Study.max_rounds)"}
T -- "yes" --> U["Coordinator launches the Expert's<br/>proposed_experiment<br/>(new Experiment + Runner)"]
U --> O
T -- "no" --> V["Round budget exhausted:<br/>answers with what it has,<br/>flags the limitation in the Report"]
V --> R

R --> S{"Anything in the Study<br/>still unresolved?"}
S -- "yes" --> O
S -- "no" --> W["Output Composer: compose_report"]
W --> X["Study.status = COMPLETED"]
X --> Z3(["End: Report delivered"])
```

## Reading notes

- **The dedup diamond (`F`)** is the same logic seen in `build_scenario`/`run_simulation`: before
  spending an agent call or a simulation, the framework checks whether something with that
  request's id already exists (content hash or request hash, depending on the aggregate). This is
  what makes "zero redundant simulations" a fact of construction rather than a separate
  optimisation.
- **The retry diamond (`J`)** encodes a decision the architecture document itself leaves open
  (§8: *"whether the Coordinator should be allowed to re-ask a specialist with a corrected task
  more than once before failing the step (currently: once)"*) — the diagram fixes the **current**
  behaviour (a single retry), not a final design guarantee.
- **The loop `O → P → Q → T → U → O`** is the `ExpertRound` drawn as flow: every full pass through
  that loop is one new entry in `Study.rounds`, and `T` is exactly `Study.rounds_left` evaluated
  in code, not a decision the agent makes itself.
- The terminal branches (`Z1`, `Z2`, `Z3`) correspond to the three real terminal states of
  `StudyStatus`: `AWAITING_USER`, `FAILED`, `COMPLETED`.
