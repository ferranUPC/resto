"""`scripts/review_evidence.py`: the evidence report behind the daily and weekly reviews.

The script's logic is pure functions over text and dates; these tests feed them small tracker,
work-plan and git-log fixtures. Nothing here runs git, pytest or the scan of the real repo.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "review_evidence.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("review_evidence", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["review_evidence"] = module
    spec.loader.exec_module(module)
    return module


re_ = _load()

TRACKER = """# Progress tracker

Last updated: 2026-10-07

### E1 — MCP servers

| ID | Task | Status | Notes |
|---|---|---|---|
| E1.1 | Finished long ago | ✅ | 2026-09-14, commit `daf304d`: all seven tools |
| E1.2 | Finished this week | ✅ | 2026-10-06, commit `abc1234`: new thing |
| E1.3 | In progress | 🔄 | half built |
| E1.4 | Far future | ⬜ | not started |
| E1.5 | Soon due | ⬜ | not started |
| E1.6 | Measured later | ⏳ | waits for a suite |
| E1.7 | Dropped | 🚫 cancelled | replaced |
| E1.8 | Spec says done | ⬜ | untouched |

| ID | Target | Deadline | Milestone | Status | Notes |
|---|---|---|---|---|---|
| M1 | Mon 26 Oct | Fri 27 Nov | Planner loop built | ⬜ | milestone row, not a task |
"""

WORK_PLAN = """### E1 — MCP servers and `traci_api` (94) · DoD §4.9, §4.10

| ID | Task | Output | pts | Wave | Latest due |
|---|---|---|---|---|---|
| E1.1 | A task with a `|` free cell | tools | 8 | — | 10 Sep |
| E1.3 | In progress | code | 6 | 1b | 26 Nov |
| E1.4 | Far future | code | 3 | 3 | 15 Jan |
| E1.5 | Soon due | code | 2 | 1a | 16 Oct |
| E1.7 | Dropped | — | 0 | — | — |
"""

TODAY = date(2026, 10, 7)
LAST_REVIEW = date(2026, 10, 6)


def test_parse_tracker_reads_status_and_first_note_date() -> None:
    rows = re_.parse_tracker(TRACKER)

    assert [r.task_id for r in rows] == [f"E1.{n}" for n in range(1, 9)]
    by_id = {r.task_id: r for r in rows}
    assert by_id["E1.1"].status == "✅"
    assert by_id["E1.1"].note_date == date(2026, 9, 14)
    assert by_id["E1.3"].status == "🔄"
    assert by_id["E1.3"].note_date is None
    assert by_id["E1.7"].status == "🚫"


def test_parse_tracker_skips_milestone_rows() -> None:
    ids = {r.task_id for r in re_.parse_tracker(TRACKER)}

    assert "M1" not in ids


def test_parse_work_plan_reads_points_wave_due_and_epic_dod() -> None:
    plan = re_.parse_work_plan(WORK_PLAN, today=TODAY)

    assert plan["E1.3"].points == 6
    assert plan["E1.3"].wave == "1b"
    assert plan["E1.3"].due == date(2026, 11, 26)
    assert plan["E1.3"].dod == "§4.9, §4.10"
    assert plan["E1.4"].due == date(2027, 1, 15)
    assert plan["E1.7"].due is None


def test_parse_work_plan_takes_cells_from_the_right_so_a_pipe_in_the_task_cell_is_harmless() -> (
    None
):
    plan = re_.parse_work_plan(WORK_PLAN, today=TODAY)

    assert plan["E1.1"].points == 8
    assert plan["E1.1"].due == date(2026, 9, 10)


def test_spec_task_id_comes_from_the_directory_slug() -> None:
    assert re_.task_id_from_slug("e5-3-loop-closure") == "E5.3"
    assert re_.task_id_from_slug("e10-7-thesis-draft-v1") == "E10.7"
    assert re_.task_id_from_slug("r13-deterministic-planner") is None
    assert re_.task_id_from_slug("unplanned") is None


def test_parse_spec_reads_status_and_dod() -> None:
    text = (
        "# E5.3: Loop closure\n\n**Status:** ready\n\n"
        "**Work plan:** E5.3 · E5 — Input Parser · DoD §4.1, §4.2, §4.8 · 6 pts · wave 1b\n"
    )

    spec = re_.parse_spec(text)

    assert spec.status == "ready"
    assert spec.dod == "§4.1, §4.2, §4.8"


def test_parse_spec_tolerates_missing_fields() -> None:
    spec = re_.parse_spec("# Something\n")

    assert spec.status is None
    assert spec.dod is None


def test_parse_git_log_maps_task_ids_in_subject_and_body_to_commits() -> None:
    raw = (
        "abc1234\x1f2026-10-06\x1fE5.15: wire the planner\x1fbody mentions E3.7 too\x1e"
        "def5678\x1f2026-10-06\x1fProgress review 2026-10-06\x1fE1.1 E1.2\x1e"
        "0123456\x1f2026-10-06\x1fRefactor r13, no task\x1f\x1e"
    )

    commits = re_.parse_git_log(raw)

    assert [c.sha for c in commits] == ["abc1234", "0123456"]
    assert commits[0].task_ids == frozenset({"E5.15", "E3.7"})
    assert commits[1].task_ids == frozenset()


def test_latest_review_picks_the_newest_file_across_directories() -> None:
    names = [
        "docs/progress-reviews/2026-10-05.md",
        "docs/feasability-analisis/2026-10-07.md",
        "docs/feasability-analisis/2026-10-06.md",
        "docs/progress-reviews/notes.md",
    ]

    path, when = re_.latest_review(names)

    assert path == "docs/feasability-analisis/2026-10-07.md"
    assert when == date(2026, 10, 7)


def test_latest_review_is_none_when_there_is_no_review_yet() -> None:
    assert re_.latest_review(["docs/progress-reviews/notes.md"]) is None


def _specs(**by_id: tuple[str, datetime]) -> dict[str, Any]:
    return {
        task_id: re_.SpecInfo(
            path=f".scratch/{task_id}/spec.md", status=status, dod=None, touched=touched
        )
        for task_id, (status, touched) in by_id.items()
    }


def _classify(**overrides: object) -> dict[str, Any]:
    rows = re_.parse_tracker(TRACKER)
    plan = re_.parse_work_plan(WORK_PLAN, today=TODAY)
    kwargs: dict[str, Any] = {
        "rows": rows,
        "plan": plan,
        "specs": {},
        "commits": [],
        "since": LAST_REVIEW,
        "today": TODAY,
        "window_days": 14,
        "scope": "daily",
    }
    kwargs.update(overrides)
    result = re_.classify(**kwargs)
    return {t.task_id: t for t in result.hot} | {"_cold": result.cold}


def test_in_progress_and_awaiting_measurement_are_hot() -> None:
    result = _classify()

    assert "status" in result["E1.3"].reasons[0]
    assert "E1.6" in result


def test_a_task_due_within_the_window_is_hot_and_a_far_one_is_cold() -> None:
    result = _classify()

    assert "E1.5" in result
    assert "E1.4" not in result


def test_a_task_due_just_outside_the_window_is_cold() -> None:
    plan = re_.parse_work_plan(WORK_PLAN.replace("16 Oct", "22 Oct"), today=TODAY)

    result = _classify(plan=plan)

    assert "E1.5" not in result


def test_a_commit_or_a_spec_touched_since_the_last_review_makes_a_task_hot() -> None:
    commit = re_.Commit("abc1234", "2026-10-06", "E1.4: start", frozenset({"E1.4"}))
    touched = datetime(2026, 10, 6, 21, 0)
    specs = _specs(**{"E1.8": ("ready", touched)})

    result = _classify(commits=[commit], specs=specs)

    assert "E1.4" in result
    assert "E1.8" in result


def test_a_spec_untouched_since_the_last_review_does_not_make_a_task_hot() -> None:
    specs = _specs(**{"E1.8": ("ready", datetime(2026, 9, 1))})

    assert "E1.8" not in _classify(specs=specs)


def test_a_done_claim_newer_than_the_last_review_is_hot_and_an_old_one_is_not() -> None:
    result = _classify()

    assert "E1.2" in result
    assert "E1.1" not in result


def test_cancelled_rows_are_cold_unless_the_spec_disagrees() -> None:
    assert "E1.7" not in _classify()

    specs = _specs(**{"E1.7": ("needs-triage", datetime(2026, 9, 1))})
    result = _classify(specs=specs)

    assert "E1.7" in result
    assert any("spec" in reason for reason in result["E1.7"].reasons)


def test_mismatches_between_tracker_and_spec() -> None:
    specs = _specs(
        **{
            "E1.1": ("ready", datetime(2026, 9, 1)),
            "E1.8": ("done", datetime(2026, 9, 1)),
            "E1.3": ("ready", datetime(2026, 9, 1)),
        }
    )

    problems = re_.mismatches(re_.parse_tracker(TRACKER), specs)

    ids = {task_id for task_id, _ in problems}
    assert ids == {"E1.1", "E1.8"}


def test_a_done_spec_matches_a_row_awaiting_measurement() -> None:
    specs = _specs(**{"E1.6": ("done", datetime(2026, 9, 1))})

    assert re_.mismatches(re_.parse_tracker(TRACKER), specs) == []


def test_mismatched_tasks_are_hot() -> None:
    specs = _specs(**{"E1.1": ("ready", datetime(2026, 9, 1))})

    result = _classify(specs=specs)

    assert "E1.1" in result


def test_weekly_scope_makes_every_live_task_hot() -> None:
    result = _classify(scope="weekly")

    assert {"E1.1", "E1.2", "E1.3", "E1.4", "E1.5", "E1.6", "E1.8"} <= set(result)
    assert "E1.7" not in result
    assert result["_cold"] == {"🚫": 1}


def test_cold_tasks_are_counted_by_status() -> None:
    cold = _classify()["_cold"]

    assert cold == {"✅": 1, "⬜": 2, "🚫": 1}


def test_format_report_names_hot_tasks_and_only_counts_cold_ones() -> None:
    commit = re_.Commit("abc1234", "2026-10-06", "E1.3: more", frozenset({"E1.3"}))
    rows = re_.parse_tracker(TRACKER)
    plan = re_.parse_work_plan(WORK_PLAN, today=TODAY)
    result = re_.classify(
        rows=rows,
        plan=plan,
        specs={},
        commits=[commit],
        since=LAST_REVIEW,
        today=TODAY,
        window_days=14,
        scope="daily",
    )

    text = re_.format_report(
        result,
        plan=plan,
        specs={},
        commits=[commit],
        problems=[],
        last_review=("docs/feasability-analisis/2026-10-07.md", date(2026, 10, 7)),
        today=TODAY,
        scope="daily",
        window_days=14,
    )

    assert "E1.3" in text
    assert "abc1234" in text
    assert "Cold (not opened)" in text
    assert "E1.4" not in text
    assert "docs/feasability-analisis/2026-10-07.md" in text
