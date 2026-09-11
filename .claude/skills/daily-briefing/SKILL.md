---
name: daily-briefing
description: Quick-read status briefing for starting a RESTO work session — summarizes what happened since the last session (commits, uncommitted work) against docs/progress-tracker.md and docs/tfm-work-plan.md, and recommends the single next concrete task. Read-only, interactive, fast — never commits, pushes, or edits files. For a full evidence-based DoD audit that updates the tracker, use progress-review instead.
---

# Daily briefing

A short "good morning" status check, meant to run in a few seconds at the start of a session, not a full audit. It answers three questions: what happened since I last looked, where does the project stand, what's the one thing to do next. It never modifies the repo — no commits, no pushes, no edits to docs.

Do not duplicate `progress-review`'s job: don't re-derive DoD compliance from scratch, don't run the full test suite, don't write a feasibility analysis. Trust `docs/progress-tracker.md` as the current source of truth for task status and only flag when it looks stale (see step 4).

## 1. Gather evidence (fast, read-only)

- Read the "Last updated" date at the top of `docs/progress-tracker.md`.
- `git log --oneline --since="<that date>"` (fall back to `-15` if the date parse is awkward) to see what landed since the last tracker update.
- `git status` to surface uncommitted or stashed work — this matters as much as merged commits for "where did I leave off."
- `git log -1 --format=%cd --date=relative` for a sense of recency.
- List `docs/feasability-analisis/` and note the date of the most recent entry, if any.

## 2. Read project state

- `docs/progress-tracker.md`: current summary line (X/65 done), any 🔄 in-progress tasks, and the milestone table.
- `docs/tfm-work-plan.md`: due dates for the epic(s) currently active or next up, so urgency can be stated in real days-remaining terms against today's date.
- Skip `docs/tfm-architecture-and-dod.md` unless a specific DoD threshold is needed to explain why a task isn't ✅ yet — this briefing reports status, it doesn't re-litigate it.

## 3. Write the briefing

Keep it short — bullets, not prose. Structure:

- **Since last time**: 1-3 lines on what commits landed (reference short hashes) and any uncommitted work sitting in the working tree. If nothing changed, say so plainly rather than padding.
- **Where things stand**: current completion %, which epic is active, and the nearest upcoming due date from `tfm-work-plan.md` with days remaining computed against today's actual date — don't guess or reuse a stale date from memory.
- **Next up**: exactly one recommended task, chosen as (a) the current 🔄 in-progress task if one exists and isn't blocked, else (b) the next ⬜ task in the active epic by due date. Name its ID, one line on what it involves, and why it's next (blocking something, on the critical path to the nearest milestone, etc.) — pull that reasoning from the work plan, don't invent it.

## 4. Staleness check

If the tracker's "Last updated" date is more than ~7 days old, or `git log` shows meaningfully more activity than the tracker's notes reflect, say so explicitly and suggest running `progress-review` to refresh it — but do not run it yourself or attempt any of its steps.
