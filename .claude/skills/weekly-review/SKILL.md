---
name: weekly-review
description: Weekly full audit of the RESTO TFM against the work plan. Re-verifies every live task, prunes tracker Notes, writes the feasibility analysis and the diary, opens a PR.
disable-model-invocation: true
model: sonnet
effort: high
---

# Weekly review

Audit every task, including the ones nobody touched. Trust no row: a ✅ stays ✅ only while its evidence still exists, and a ⬜ with code behind it is work nobody claimed.

Status legend, counting rules, review text and diary rules: `.claude/skills/common/review-rules.md`. Read it before step 2.

## 1. Evidence

1. `git fetch origin master`, then work on top of the latest `origin/master`.
2. Run `python scripts/review_evidence.py --scope weekly`. Every live task is hot in this scope. The report gives each task its commits, spec status, DoD pointer and due date, lists the rows where the tracker and the spec disagree, and ends with the pytest, ruff and mypy results. A task marked `DoD not recorded` has its DoD in its work-plan row.
3. Open further files only for one task at a time and only with `sed -n` or `grep -n` on a line range. Cap diffs and specs with `--stat` or `head -40`.

Done when the report is in view and the three checks have a verdict. A check that failed goes into the review as a finding.

## 2. Audit by epic

Launch one subagent per epic, in parallel. Give each its epic's section of the report and the rules below. It audits every live task of its epic, edits no file, and returns only the rows whose status should change and the claims that failed, each with its evidence. Every live task gets a verdict from the code, and the burden of proof sits on ✅.

- **✅ rows.** Check that the evidence its Notes name (commit, test, file, ADR) still exists: `git cat-file -t <sha>`, `grep -rn <test name> tests`. Evidence that is gone, or a DoD that no longer passes, downgrades the row.
- **⏳ rows.** Confirm the work is built and the named suite in `eval/measurement-plans.md` is the only thing left.
- **🔄 and ⬜ rows.** A task is ✅ only when its DoD in `docs/tfm-architecture-and-dod.md` §4.x passes against the code and the tests. A ⬜ row whose code, spec or commits show it started moves to 🔄. A row whose DoD already passes moves to ✅ or ⏳.
- **Rows where tracker and spec disagree.** The code decides, and the Notes say which of the two was wrong.
- **🚫 rows.** Confirm the spec reads `Status: cancelled` and that the replacement, if any, exists.

Merge the subagents' returns into one running list of the rows whose status changes and of the claims that failed their check. A confirmed row needs no entry.

Done when every epic has a subagent return and the running list covers every change.

## 3. Tracker

- Apply the status changes from the list. Refresh the summary count, the milestone table and "Last updated".
- Prune every Notes cell longer than 300 characters to its current status reason and one evidence pointer (commit, ADR or spec). Earlier text stays in git history.
- Edit rows with `grep -n` to find them and `Edit` to change them.

Done when `git diff docs/progress-tracker.md` shows each changed status backed by the list, and no Notes cell is over 300 characters.

## 4. Review and diary

- Write `docs/progress-reviews/{yyyy-mm-dd}.md` with the title "Weekly review". Cover:
  - the rows corrected and the claims that failed, each with its evidence;
  - the week's pace against 38.5 pts per week and the plan's slack;
  - M2, M3 and M5, each with its remaining tasks and whether its deadline holds;
  - the risks seen in this run's evidence;
  - one recommendation: keep going, or which fallback step of work-plan §5 to apply.
- Add the diary entries, following the diary rules in `.claude/skills/common/review-rules.md`.
- Run `unslop` (`.claude/skills/unslop/SKILL.md`) over the new review, the diary entries and every Notes cell you changed or wrote. Rewrite prose only; leave facts, hashes, numbers, task ids and table structure.

Done when every claim in the review cites a commit, a test result or a file, and the diary has no active day missing.

## 5. Persist

Commit `docs/progress-tracker.md`, the review and `docs/diary.md` on `progress-review/{yyyy-mm-dd}` with the message `Weekly review {yyyy-mm-dd}`. Push the branch and open a PR against `master` with `gh pr create`, titled `Weekly review {yyyy-mm-dd}`. The body lists the status changes, the number of Notes pruned, the check results and the recommendation in two sentences. If the push fails, keep the commit local and report it.
