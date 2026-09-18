---
name: progress-review
description: Reviews docs/tfm-work-plan.md against the real state of the repo, updates docs/progress-tracker.md, and writes a dated subjective feasibility analysis to docs/feasability-analisis/{yyyy-mm-dd}.md. Designed to run unattended on a schedule — commits and pushes its own output.
---

# Progress review

Runs a check of real progress on the RESTO TFM against the plan, and records an honest, evidence-based status update. This is meant to run unattended (via a scheduled cron, possibly in a fresh environment with no one watching) — leave the repo in a clean, committed and pushed state when done, and never fabricate progress that isn't backed by evidence.

## 1. Gather evidence

- Read `docs/tfm-work-plan.md` (epics, hours, due dates, milestones), `docs/tfm-architecture-and-dod.md` (per-module DoD, §4.x — the real acceptance bar, not "code exists"), and the current `docs/progress-tracker.md`.
- Inspect the actual repo state: `git log --oneline -20`, `git status`, `git diff` since the tracker's last "Last updated" date, and the `src/resto/` tree.
- Try to run the test suite: `conda run -n resto pytest -q` and `conda run -n resto ruff check .`. If the `resto` conda environment isn't available in this execution environment, fall back to running `pytest`/`ruff` directly against whatever Python is available, and note that limitation explicitly in the feasibility write-up rather than silently skipping it or failing the whole review.
- Do not infer progress from prior conversation memory or assumptions — only from what is verifiably in the repo right now.

## 2. Update the tracker

- For every task in `docs/progress-tracker.md`, re-check its status (⬜ not started / 🔄 in progress / ✅ done) against the evidence gathered and against its DoD criteria in §4.x of the architecture doc. A task becomes ✅ only when it meets its Done/threshold, never just because related code exists.
- **Do not trust the tracker's existing state as already correct, even for rows that didn't change since the last commit you can see.** A prior update to this file may have been made interactively (not by this skill) and can be incomplete — e.g. a task's code and tests landed and got described in another task's Notes or in the feasibility write-up's prose, but its own row was never flipped to ✅. Cross-check every non-✅ row against `git log`/the repo tree for evidence it was actually finished, not just against the diff since the tracker's last "Last updated" date.
- Update each task's Notes with what concretely changed since the last review; leave unchanged tasks alone rather than inventing movement.
- Refresh the summary count/percentage, the milestone table (M0–M7), and the "Last updated" date at the top of the file.

## 3. Write the feasibility analysis

- Create `docs/feasability-analisis/{yyyy-mm-dd}.md` using today's date (e.g. `date +%F`).
- The content is a **subjective, opinionated** read of how the project is going — not a restatement of the tracker table. Cover:
  - Pace vs. the calendar in `tfm-work-plan.md` (the plan is ~4% overcommitted with zero contingency by design — say plainly whether due dates and weekly hour budgets are being met).
  - Whether the milestones look achievable at the current velocity, especially **M2, M3, M5**, which §5 of the work plan says must not be cut.
  - Concrete risks or bottlenecks actually observed this review (not generic ones restated from the docs).
  - A direct recommendation: keep going as planned, or start applying the fallback downgrade order from work-plan §5 (and which item of that ordered list, if so).
  - Back every claim with what was actually found in step 1 (specific commits, test results, files present/missing) — this must read as a real assessment, not filler.
- If there has been no progress since the last review, say so plainly and briefly instead of padding the report. Every scheduled run still produces a dated entry, even a short one — the point is a continuous timeline of honest snapshots.

## 4. Persist

- Stage and commit `docs/progress-tracker.md` and the new `docs/feasability-analisis/{yyyy-mm-dd}.md`, with a short commit message naming the review date (e.g. `Progress review 2026-09-17`).
- Push to `origin` so the review survives beyond this run's environment — this was explicitly requested for this skill (unattended runs must not leave unpersisted local-only changes).
- If the push fails (e.g. diverged branch), do not force-push — pull/rebase first, and if that's not resolvable automatically, leave the commit local and say so clearly in the run's output rather than doing anything destructive.

# Note
Take into account that in worse case scenario, I still have till end of may to finish correcting some things (not full-time work, but still some time partially end the work).