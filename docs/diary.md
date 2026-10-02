# Diary

A short summary of what happened on each working day. The most recent entry comes first, and days with no activity have no entry. `progress-review` adds the new entries.

## 01.10.2026

ADR-0035 (described demand) is complete: DEV-NET's demands are now described, `Question.network_only` is scored, the request bank adds networks outside the database, and the Parser's v7 contract (a demand phrase, a time window, the network-only rule) meets every dev threshold. ADR-0037 removes the Coordinator's four database tools; a plan now carries `obtain_network`/`obtain_demand` steps, and the Network Author and Demand Generator resolve the actual reference themselves, returning `NeedsUser` with candidates when one is missing. ADR-0036 adds a `RawDemandData` aggregate and an `od_matrix` content type, replacing the unbuilt `historical_demand` DatabaseMCP group; both ADRs add new tasks to the work plan (E3.12, E5.14, E6.8 to E6.11), none built yet. The task-tree progress page gains a search box, critical-path and next-task navigation, a markdown viewer, and an English-translated interface.

## 30.09.2026

The Expert now sees a scope of networks instead of one fixed id, so it can answer about an edge a derivation added, and a note's network is derived from its scenario instead of chosen by hand (ADR-0032). A tool contract change, treating an unknown traffic-light id as an answer instead of a failure, lifts diagnostic Jaccard from 0.60 to 0.95 in a one-repetition sweep. Opening the plan bank (E3.7) surfaced a missing rule for choosing between demands on the same network. A demand now carries a required description and labels, and the Coordinator asks instead of defaulting to random traffic when none fits (ADR-0035). SUMO and `duarouter` launches move behind one shared module, and the Scenario Builder's tools join the Network and Expert tools under a single declaration.

## 29.09.2026

Work focused on refactors and design decisions. A failed SUMO run can now be retried without a conflict, and only an ok result is stored (ADR-0031). The in-memory repositories now answer like SQLite, checked by one shared contract suite. The DatabaseMCP server starts on either backend, in-memory or SQLite (ADR-0034), and the trace has typed events that only the study recorder emits. The Expert's network scope (ADR-0032) and the single declaration of tools (ADR-0033) are recorded, and the network, Scenario Builder and Expert tools are now declared with a decorator.

## 28.09.2026

Executor refactor. It moves into its own package, with modules that classify failures, check a plan without running a study, write the Study and control the budget. Model prices now live in one manifest (`config/prices.toml`) and any model without a price is rejected. `Usage` also records the real cost OpenRouter returns next to the estimate. The Expert and Parser benchmarks and the hygiene probes share one paid-run loop, with a mandatory cap, a $1 limit and a per-worker cost reservation. The DEV-NET demand verification is repeated with 19 seeds and the conclusion does not change.

## 25.09.2026

The DEV-NET assets move to clock time (08:00 to 09:00, ADR-0028) and the verification results come out identical. ADR-0027 is accepted, so the contrast between two nested arms is always oriented from the code. Expert v2 meets every DoD threshold on the clock-time bank. With ADR-0029, the "why" of a diagnosis is graded as one typed cause per congested edge, and Expert v4 beats both E4.3 targets (Jaccard 0.60 and cause precision 0.89) in one repetition.

## 24.09.2026

The work plan is reorganized into version 0.3, with capacity measured in story points, slack, milestones with a target and a deadline, and a new cut order. A graph of pending tasks with its critical path is tried out, and the maintainer's decisions are noted, such as doing E4.9 on DEV-NET and freezing features before Validation 2. The progress page now reads the new plan format and shows tasks awaiting measurement separately. Work also continues on annotating Parser requests, and the progress-review skill is updated.

## 23.09.2026

Work focused on the Executor and the Input Parser. The phased Study with a typed plan and typed errors (E5.9), the deterministic Executor with its per-agent ports (E5.10), the CLI render of failed or pending user studies (E5.11) and 0 to 3 Expert notes per study (E4.11) are implemented, with ADR-0025 to 0028 as their base. The request bank (E3.4) is complete, with 65 concepts and 241 hand-reviewed variants, and the Input Parser (E5.1) meets every dev threshold with prompt v4 at $0.227 per pass, though the held-out run is still missing. A progress site on GitHub Pages also goes up, and the plan estimate is readjusted to 935 points.

## 22.09.2026

Work focused on architecture decisions and Expert evaluation. ADR-0023 splits the Coordinator into an Input Parser, a single-call Coordinator and a deterministic Executor, and the Study gets phases. The Expert benchmark can now run in free mode and measures abstention (E4.5). The Expert now writes notes from a finished round, they are confirmed or refuted deterministically against the KPIs, and 20 knowledge-hygiene probes come out with 0 violations (E4.6). The pending paid experiments are noted in a single plan, EXP-01, so no sweep is paid for twice.

## 18.09.2026

No code changes. The automatic progress review found no new commits and PyPI was not responding, so that result was reverted. The second pass marks E3.2 and E4.1 as done and E3.3 as partial. The progress-review skill is also fixed so that it audits every tracker row against evidence and not only the latest diffs, because two rows had gone stale.

## 17.09.2026

Work focused on Network Expert development. The DEV-NET/peak question bank now exists, with 117 questions and reference answers computed by program (E3.2), and the Expert runs on the ToolAgent port with evidence checked against the ledger (E4.1). There is also a benchmark harness (E3.3), with per-step traces and ADR-0019 to ADR-0022 on typed answers, vehicle-second units, NoValue answers and aggregation tools. Version v1 gets 110 of 117 questions right for $0.98, and v2 batches the topology tools and solves 4 of the 7 questions that ran out of budget. The full three-repetition sweep costs about $2.9 and is postponed, so E4.7 becomes blocked on funding.

## 16.09.2026

No code changes. The day's progress review verifies tasks E2.3, E2.4 and E3.1 as done, and milestone M1 is met.

## 15.09.2026

The Scenario Builder now works in its minimal version and supports street closures, traffic light program changes and demand scaling. The ToolAgent now talks to OpenRouter and there is a smoke-test script. A harness checks with real SUMO that each intervention produces its effect (E2.4). With it, a matrix of 20 scenarios on DEV-NET with 3 seeds is built through DatabaseMCP (E3.1), and the two edgedata parsers are unified. Domain diagrams are also added.

## 14.09.2026

The contracts are closed: domain, drafts, JSON schemas and the v1.0 DatabaseMCP contract, with 14 ADRs recording the decisions taken. DEV-NET is created with its three demand profiles, and JSONL tracing, the network and TraCI MCP servers, and the SQLite DatabaseMCP backend with its conformance suite are implemented. CI also runs mypy and fails if the SUMO on PATH is not 1.27.1, backend latency is measured, and SUMO simulations can be launched from config files.

## 13.09.2026

No code commits. The progress review confirms that CI is green and that E0.1 is closed. It warns that the drafts, schemas and DatabaseMCP contract work was still uncommitted locally.

## 11.09.2026

SUMO is pinned to version 1.27.1 and CI uses that version. The architecture (v0.3), the work plan and the tracker are updated with the new domain model. The code is reorganized into the hexagonal layout, with ports, domain aggregates and one module per agent.

## 10.09.2026

First commit of the project. The repository skeleton is created with the hexagonal architecture as folders, the CI workflow, the work plan and the architecture and DoD document. The progress-review skill is also added, and it runs the first progress review of the day.
