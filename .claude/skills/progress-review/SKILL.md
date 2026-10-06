---
name: progress-review
description: Reviews docs/tfm-work-plan.md against the real state of the repo, updates docs/progress-tracker.md, and writes a dated subjective feasibility analysis to docs/progress-reviews/{yyyy-mm-dd}.md. Designed to run unattended on a schedule — commits its output on a branch and opens a PR against master.
model: sonnet
effort: high
---

# Progress review

Runs a check of real progress on the RESTO TFM against the plan, and records an honest, evidence-based status update. This is meant to run unattended (via a scheduled cron, possibly in a fresh environment with no one watching) — leave the repo in a clean state with the review committed, pushed on a branch and opened as a PR, and never fabricate progress that isn't backed by evidence.

## 1. Gather evidence

- Read `docs/tfm-work-plan.md` (epics, hours, due dates, milestones), `docs/tfm-architecture-and-dod.md` (per-module DoD, §4.x — the real acceptance bar, not "code exists"), and the current `docs/progress-tracker.md`.
- Inspect the actual repo state: `git log --oneline -20`, `git status`, `git diff` since the tracker's last "Last updated" date, and the `src/resto/` tree.
- Try to run the test suite: `conda run -n resto pytest -q` and `conda run -n resto ruff check .`. If the `resto` conda environment isn't available in this execution environment, fall back to running `pytest`/`ruff` directly against whatever Python is available, and note that limitation explicitly in the feasibility write-up rather than silently skipping it or failing the whole review.
- Do not infer progress from prior conversation memory or assumptions — only from what is verifiably in the repo right now.

## 2. Update the tracker

- For every task in `docs/progress-tracker.md`, re-check its status (⬜ not started / 🔄 in progress / ✅ done) against the evidence gathered and against its DoD criteria in §4.x of the architecture doc. A task becomes ✅ only when it meets its Done/threshold, never just because related code exists.
- The statuses, and the tracker's legend line, are exactly these (decided 2026-09-24, wayfinder #3):
  - ⬜ not started · 🔄 in progress · ✅ done.
  - ⏳ **awaiting measurement**: the work is built and every development run it needs has been done; the only thing between it and ✅ is a measurement suite in `eval/measurement-plans.md`, which runs in Validation 1 or 2. The Notes name the suite and say whether the development evidence (e.g. a 1-repetition sweep) already meets the threshold. A deferred paid run is never a reason for 🚧.
  - 🚧 **blocked**: cannot proceed for a stated reason outside our control (an external person, data or service); the Notes say what unblocks it.
- A ⏳ task turns ✅ only on its suite's result in a validation pass; Validation 1's reduced checkpoints are interim and never turn a task ✅.
- **Do not trust the tracker's existing state as already correct, even for rows that didn't change since the last commit you can see.** A prior update to this file may have been made interactively (not by this skill) and can be incomplete — e.g. a task's code and tests landed and got described in another task's Notes or in the feasibility write-up's prose, but its own row was never flipped to ✅. Cross-check every non-✅ row against `git log`/the repo tree for evidence it was actually finished, not just against the diff since the tracker's last "Last updated" date.
- Update each task's Notes with what concretely changed since the last review; leave unchanged tasks alone rather than inventing movement.
- Refresh the summary count/percentage (⏳ tasks and their hours are counted separately, never as done), the milestone table (every row of work-plan §2: M0–M7, V1, feature freeze, V2, with target and deadline; M8 is recorded, not planned; a build milestone is met when all its tasks are ✅ or ⏳), and the "Last updated" date at the top of the file.

## 3. Write the feasibility analysis

- Create `docs/progress-reviews/{yyyy-mm-dd}.md` using today's date (e.g. `date +%F`).
- The content is a **subjective, opinionated** read of how the project is going — not a restatement of the tracker table. Cover:
  - Pace vs. the calendar in `tfm-work-plan.md` (v0.3: plan hours are story points, 38.5 pts/week, ≈ +170 pts of slack; each milestone has a target and a deadline, each task a wave and a latest due — say plainly whether milestone targets are being met, and whether any deadline is at risk).
  - Whether the milestones look achievable at the current velocity, especially **M2, M3, M5**, which §5 of the work plan says must not be cut.
  - Concrete risks or bottlenecks actually observed this review (not generic ones restated from the docs).
  - A direct recommendation: keep going as planned, or start applying the fallback order from work-plan §5 (and which step of that ordered list, if so).
  - Back every claim with what was actually found in step 1 (specific commits, test results, files present/missing) — this must read as a real assessment, not filler.
- If there has been no progress since the last review, say so plainly and briefly instead of padding the report. Every scheduled run still produces a dated entry, even a short one — the point is a continuous timeline of honest snapshots.
- Before committing, run the `unslop` skill (`.claude/skills/unslop/SKILL.md`) over the new feasibility analysis and over every tracker Notes cell you wrote or changed this run. Rewrite only prose; leave facts, commit hashes, numbers, task ids and table structure as they are.

## 3b. Write the diary

- `docs/diary.md` is a diary shown in the "Diary" tab of the GitHub Pages site. It has an intro line, then one entry per active day, **newest first**, each as a level-2 heading with the date as `dd.mm.yyyy` followed by one paragraph. The file is hand-ordered, so put new entries directly under the intro, above the previous newest one.
- Days with no activity get no entry. There is no "no changes" filler.
- Write an entry for **every day that has commits but no entry yet**, from the newest date in the diary up to yesterday and today's commits included only if the day is already over (a review that runs at 7:00 covers the previous day). Group commits by **author date** (`git log --format='%h %ad %s' --date=format:'%d.%m.%Y'`), not by push time, and skip merge commits and `Progress review` commits unless they carry real content. Read the diffs or ADRs when a commit message is unclear.
- Each entry is in English, 2 to 4 short sentences, result oriented: what now works, what was fixed, what was decided. Example: "Work focused on refactors across the application. The bug that prevented starting the app with the in-memory backend is fixed. Costs can also be computed when a study is launched from the CLI." No commit hashes or file lists.
- Writing rules, so entries stay useful later:
  - State facts, never judgments. No "productive", "big", "strong", "quiet", "ahead of schedule". Name the focus instead: "Work focused on the Network Expert." A day with only a review or no code reads "No code changes."
  - Keep what is hard to recover from git: task ids, ADR numbers, thresholds and measured numbers, costs, what was decided and why, what is blocked or postponed and on what.
  - Say what changed in behavior or scope, not which files or commits.
  - Past or present tense, one voice, no advice or plans for the future.
- Run `unslop` over the new entries too. Stage `docs/diary.md` with the rest of the review's output. The Pages workflow watches that file, so the site rebuilds when the PR merges.

## 4. Persist

- Stage and commit `docs/progress-tracker.md`, the new `docs/progress-reviews/{yyyy-mm-dd}.md` and `docs/diary.md`, with a short commit message naming the review date (e.g. `Progress review 2026-09-17`).
- Before starting step 1, make sure you work on top of the latest `origin/master` (`git fetch origin master`), so the review sees everything pushed so far.
- Commit on a branch (the session's designated `claude/*` branch in a cloud run, or `progress-review/{yyyy-mm-dd}` otherwise), never directly on `master`. Push that branch to `origin` and **open a pull request against `master`** titled `Progress review {yyyy-mm-dd}`. The PR body holds the run's summary: tasks whose status changed, test/ruff/mypy results, and the feasibility recommendation in one or two sentences. The maintainer merges it.
- Open the PR with whatever GitHub tool the environment provides (`gh pr create`, or a built-in pull-request tool). If none works, say so clearly in the run's output and give the compare URL that `git push` printed, so the PR can be opened by hand.
- If the push fails, do not force-push. Leave the commit local and say so clearly in the run's output rather than doing anything destructive.

# Note
Take into account that in worse case scenario, I still have till end of may to finish correcting some things (not full-time work, but still some time partially end the work).