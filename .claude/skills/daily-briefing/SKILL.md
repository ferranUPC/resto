---
name: daily-briefing
description: Quick-read status briefing for starting a RESTO work session — summarizes what happened since the last session (commits, uncommitted work) against docs/progress-tracker.md and docs/tfm-work-plan.md, and ends with the exact next command to type (e.g. `/triage E3.7`), read from the task's phase in the local `.scratch/` tracker. Read-only, interactive, fast — never commits, pushes, or edits files. For a full evidence-based DoD audit that updates the tracker, use progress-review instead.
---

# Daily briefing

A short "good morning" status check, meant to run in a few seconds at the start of a session, not a full audit. It answers three questions: what happened since I last looked, where does the project stand, what's the one command to run next. It never modifies the repo — no commits, no pushes, no edits to docs or to `.scratch/`.

Do not duplicate `progress-review`'s job: don't re-derive DoD compliance from scratch, don't run the full test suite, don't write a feasibility analysis. Trust `docs/progress-tracker.md` as the current source of truth for task status and only flag when it looks stale (see step 5).

## 1. Gather evidence (fast, read-only)

- Read the "Last updated" date at the top of `docs/progress-tracker.md`.
- `git log --oneline --since="<that date>"` (fall back to `-15` if the date parse is awkward) to see what landed since the last tracker update.
- `git status` to surface uncommitted or stashed work — this matters as much as merged commits for "where did I leave off."
- `git log -1 --format=%cd --date=relative` for a sense of recency.
- List `docs/feasability-analisis/` and note the date of the most recent entry, if any.
- Read the **phase** of every task in `.scratch/` (the local tracker, git-excluded; conventions in `docs/agents/issue-tracker.md`): `grep -rH --include='*.md' '^\*\*Status' .scratch`, plus each spec's `**Blocked by:**` line and whether its `## Spec` section is still the seeded placeholder. If `.scratch/` does not exist (e.g. a fresh clone), say so in one line and fall back to naming a task without a command.

## 2. Read project state

- `docs/progress-tracker.md`: current summary line (done / total), any 🔄 in-progress tasks, and the milestone table.
- `docs/tfm-work-plan.md`: due dates for the wave(s) currently active or next up, so urgency can be stated in real days-remaining terms against today's date; §4.3–4.4 for the critical paths.
- Skip `docs/tfm-architecture-and-dod.md` unless a specific DoD threshold is needed to explain why a task isn't ✅ yet — this briefing reports status, it doesn't re-litigate it.

## 3. Pick the next action

Choose **one task**, then read its **next command** off its phase.

**Which task**, first match wins:

1. A task already in flight: a spec past `needs-triage` and not `done`, or a 🔄 task in the tracker. Finishing beats starting.
2. Otherwise, an **unblocked** `needs-triage` spec — every task on its `Blocked by:` line is `done` in `.scratch/` or ✅/⏳ in the tracker. Among those, prefer the head of the critical chain that feeds the nearest milestone target (work plan §4.3), then the earlier wave, then the earlier latest due.

Skip specs whose only remaining work is a measurement (a `**Measured in:**` line and ⏳ in the tracker): they wait for their validation pass.

**Which command**, from the chosen task's phase in `.scratch/<task>/`:

| Phase | Next command |
|---|---|
| spec `needs-triage` | `/triage <task-id>` |
| spec `needs-info` | none: the maintainer answers the open questions under `## Comments`, then `/triage <task-id>` |
| spec `ready`, `## Spec` still the placeholder | `/to-spec` on `.scratch/<task>/spec.md` |
| spec written, `issues/` empty | `/to-tickets` on `.scratch/<task>/spec.md` |
| open tickets in `issues/` | `/implement` on the lowest-numbered open ticket whose `Blocked by` tickets are all `done` |
| every ticket `done`, spec not yet `done` | close the spec (`Status: done`); the ✅ is `progress-review`'s call |
| a `map.md` with an open, unblocked, unclaimed ticket | `/wayfinder` on that map |

Small tasks may skip `/to-spec` and `/to-tickets` when the triage brief says so; follow the brief.

## 4. Write the briefing

Keep it short — bullets, not prose. Structure:

- **Since last time**: 1-3 lines on what commits landed (reference short hashes) and any uncommitted work sitting in the working tree. If nothing changed, say so plainly rather than padding.
- **Where things stand**: current completion %, which wave is active, and the nearest upcoming milestone target/deadline from `tfm-work-plan.md` with days remaining computed against today's actual date — don't guess or reuse a stale date from memory. Add one line counting `.scratch/` specs by phase (e.g. "44 specs: 43 needs-triage, 1 ready").
- **Next**: the task from step 3 — its ID, one line on what it involves, and why it's next (in flight, head of the critical path to M3, blocking X), with the reasoning pulled from the work plan, never invented. End the briefing with the command on its own line, ready to copy:

  ```
  /triage E3.7
  ```

## 5. Staleness check

If the tracker's "Last updated" date is more than ~7 days old, or `git log` shows meaningfully more activity than the tracker's notes reflect, say so explicitly and suggest running `progress-review` to refresh it — but do not run it yourself or attempt any of its steps.

Flag a mismatch between the two trackers in one line when you see it: a `.scratch/` spec `done` whose task is still ⬜ in the tracker (normal until the next review), or a ✅ task whose spec is still open (the spec needs closing).
