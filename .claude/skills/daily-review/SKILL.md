---
name: daily-review
description: Daily audit of the RESTO TFM against the work plan. Checks hot tasks only, updates the tracker, writes the diary and a short review, opens a PR.
disable-model-invocation: true
model: sonnet
effort: medium
---

# Daily review

Audit what moved since the last review. A task is done when the code proves it, whatever its row says.

Status legend, counting rules, review text and diary rules: `.claude/skills/common/review-rules.md`. Read it before step 3.

## 1. Evidence

1. `git fetch origin master`, then work on top of the latest `origin/master`.
2. Run `python scripts/review_evidence.py --scope daily`. It prints the last review's date and path, the hot tasks with their commits, spec status and DoD pointer, the rows where the tracker and the spec disagree, the cold count, and the pytest, ruff and mypy results. A hot task marked `DoD not recorded` has its DoD in its work-plan row.
3. The report is the whole evidence set. Open further files only for a hot task and only with `sed -n` or `grep -n` on a line range. Cap diffs and specs with `--stat` or `head -40`.

Done when every hot task in the report has its commits, spec status and DoD pointer in view.

## 2. Verdicts

Every hot task gets one verdict, and the burden of proof sits on ✅.

- A task is ✅ only when its DoD in `docs/tfm-architecture-and-dod.md` §4.x passes against the code and the tests. Existing code is not a pass. A claimed ✅ without a pass is downgraded.
- A task with no proof of progress keeps its status. Notes stay as written.
- A task that needs a paid or deferred measurement is ⏳, never ✅.
- A row where tracker and spec disagree gets a verdict from the code, and the Notes say which of the two was wrong.

Done when each hot task has a verdict and one line of evidence (a commit, a test name, a DoD threshold with its measured value).

## 3. Tracker

Edit only the rows of hot tasks, with `grep -n` to find them and `Edit` to change them. The Notes cell holds one line on what changed. Refresh the summary count, the milestone table and "Last updated".

Done when `git diff docs/progress-tracker.md` touches only hot rows, the summary and the date.

## 4. Review and diary

- Write `docs/progress-reviews/{yyyy-mm-dd}.md`: the delta since the last review, pace against the work-plan calendar, the risks seen in this run's evidence, and one recommendation (keep going, or which fallback step of work-plan §5). Short when little moved. Cite commits and test results.
- Add the diary entries, following the diary rules in `.claude/skills/common/review-rules.md`.
- Run `unslop` (`.claude/skills/unslop/SKILL.md`) over the new review, the diary entries and every Notes cell you changed. Rewrite prose only; leave facts, hashes, numbers, task ids and table structure.

Done when the review cites at least one piece of evidence per claim and the diary has no active day missing.

## 5. Persist

Commit `docs/progress-tracker.md`, the review and `docs/diary.md` on `progress-review/{yyyy-mm-dd}` with the message `Progress review {yyyy-mm-dd}`. Push the branch and open a PR against `master` with `gh pr create`, titled `Progress review {yyyy-mm-dd}`. The body lists status changes, test results and the recommendation in two sentences. If the push fails, keep the commit local and report it.
