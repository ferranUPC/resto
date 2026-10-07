# Review rules

Shared by `daily-review` and `weekly-review`. Both are user-invoked, so neither can load the other; the rules live here once, in a tracked file that a clean clone or a cloud run can read.

## Statuses

Decided 2026-09-24 (wayfinder #3). The tracker's legend line repeats these symbols.

- ⬜ not started · 🔄 in progress · ✅ done.
- ⏳ **awaiting measurement**: the work is built and every development run it needs is done. Only a measurement suite in `eval/measurement-plans.md`, run in Validation 1 or 2, stands between it and ✅. The Notes name the suite and say whether the development evidence (for example a 1-repetition sweep) already meets the threshold. A deferred paid run is never a reason for 🚧.
- 🚧 **blocked**: cannot proceed for a stated reason outside our control (an external person, data or service). The Notes say what unblocks it. A dropped task is never 🚧.
- 🚫 **cancelled**: a task whose spec in `.scratch/` reads `Status: cancelled`. The Notes say why and, when the spec has a `**Cancelled:** replaced by <id>` line, name the replacement.

## Counting

- ✅ needs the task's Done/threshold from `docs/tfm-architecture-and-dod.md` §4.x to pass. Related code existing is not a pass.
- A ⏳ task turns ✅ only on its suite's result in a validation pass. Validation 1's reduced checkpoints are interim and never turn a task ✅.
- ⏳ tasks and their points are counted apart from done. 🚫 tasks and their points are counted apart too, and leave both the total and the pending points.
- A 🚫 task is never named as "next". It does not hold a milestone open. Its dependents inherit its blockers or wait on its replacement (`docs/agents/issue-tracker.md`).
- A build milestone (M2 to M7) is met when all its tasks are ✅ or ⏳. The milestone table lists every row of work-plan §2: M0 to M7, V1, feature freeze, V2, with target and deadline. M8 is recorded, not planned.

## Review text

- The calendar: plan hours are story points, 38.5 pts per week, about +170 pts of slack. Each milestone has a target and a deadline, each task a wave and a latest due. Say plainly whether milestone targets are met and whether a deadline is at risk. M2, M3 and M5 must not be cut (work-plan §5).
- Slack beyond the plan: in the worst case the maintainer still has until the end of May to finish corrections, part-time.
- With no progress since the last review, write a short entry saying so. Every run still produces a dated file.

## Diary

`docs/diary.md` has an intro line, then one entry per active day, newest first, each a level-2 heading dated `dd.mm.yyyy` followed by one paragraph. The file is hand-ordered, so a new entry goes directly under the intro.

- Write an entry for every day that has commits and no entry yet, from the newest date in the diary up to yesterday. Today's commits count only if the day is over (a review at 7:00 covers the previous day).
- Group commits by author date: `git log --format='%h %ad %s' --date=format:'%d.%m.%Y'`. Skip merge commits and `Progress review` commits unless they carry real content. Read the diff or the ADR when a message is unclear.
- Days with no activity get no entry and no filler.
- English, 2 to 4 short sentences, result oriented: what now works, what was fixed, what was decided. Example: "Work focused on refactors across the application. The bug that prevented starting the app with the in-memory backend is fixed. Costs can also be computed when a study is launched from the CLI."
- State facts. Name the focus ("Work focused on the Network Expert") and leave judgments out ("productive", "big", "quiet", "ahead of schedule"). A day with only a review or no code reads "No code changes."
- Keep what git does not recover easily: task ids, ADR numbers, thresholds and measured numbers, costs, what was decided and why, what is blocked or postponed and on what.
- Say what changed in behavior or scope, not which files or commits. Past or present tense, one voice, no advice and no plans.
