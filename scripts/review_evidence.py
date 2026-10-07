"""Evidence report for the daily and weekly reviews: one compact printout instead of ad hoc greps.

    python scripts/review_evidence.py                  # daily scope, 14-day window, runs the checks
    python scripts/review_evidence.py --scope weekly   # every live task is audited
    python scripts/review_evidence.py --no-checks      # skip pytest, ruff and mypy

The script only reads. It never edits the tracker and never decides whether a task is done. It lists
the tasks worth auditing (the hot set), the facts the audit needs for each, and the cold count.

A task is hot when any of these holds (daily scope):
  * its tracker status is 🔄 or ⏳;
  * a commit since the last review names it, or its `.scratch` spec or issues were edited since;
  * it is not done and its latest due date falls inside the window (overdue included);
  * its row says ✅ with a note dated on or after the last review (a fresh done claim);
  * the tracker and its `.scratch` spec disagree (✅ with a spec that is not done, and so on).
Cancelled (🚫) rows are cold unless the spec disagrees. The weekly scope makes every row hot but 🚫.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REVIEW_DIRS = ("docs/progress-reviews", "docs/feasability-analisis")
STATUSES = "⬜🔄✅⏳🚧🚫"
ROW = re.compile(rf"^\|\s*(E\d+\.\d+)\s*\|(.*?)\|\s*([{STATUSES}])[^|]*\|(.*?)\|?\s*$")
PLAN_ROW = re.compile(r"^\|\s*(E\d+\.\d+)\s*\|")
EPIC_HEADER = re.compile(r"^###\s+(E\d+)\b.*?·\s*DoD\s+(.+?)\s*$")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
TASK_ID = re.compile(r"\bE\d+\.\d+\b")
SLUG_ID = re.compile(r"^e(\d+)-(\d+)(?:-|$)")
SPEC_STATUS = re.compile(r"^\*\*Status:\*\*\s*(\S+)", re.MULTILINE)
SPEC_DOD = re.compile(r"\bDoD\s+(§[^·\n]+?)\s*(?:·|$)", re.MULTILINE)
MONTHS = {
    m: i
    for i, m in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1
    )
}
LIVE_NOT_DONE = {"⬜", "🔄", "🚧"}


@dataclass(frozen=True)
class TrackerRow:
    task_id: str
    title: str
    status: str
    notes: str
    note_date: date | None


@dataclass(frozen=True)
class PlanRow:
    points: int | None
    wave: str
    due: date | None
    dod: str | None


@dataclass(frozen=True)
class SpecInfo:
    path: str
    status: str | None
    dod: str | None
    touched: datetime


@dataclass(frozen=True)
class Commit:
    sha: str
    date: str
    subject: str
    task_ids: frozenset[str]


@dataclass
class HotTask:
    task_id: str
    status: str
    title: str
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Classification:
    hot: list[HotTask]
    cold: dict[str, int]


def parse_tracker(text: str) -> list[TrackerRow]:
    """Task rows of the tracker, in file order. Milestone rows (M1, V1...) are not tasks."""
    rows: list[TrackerRow] = []
    for line in text.splitlines():
        match = ROW.match(line)
        if not match:
            continue
        task_id, title, status, notes = match.groups()
        found = ISO_DATE.search(notes[:60])
        note_date = date.fromisoformat(found.group()) if found else None
        rows.append(TrackerRow(task_id, title.strip(), status, notes.strip(), note_date))
    return rows


def _due_date(cell: str, today: date) -> date | None:
    """`26 Nov` has no year: take the year that puts it closest to today."""
    match = re.fullmatch(r"\s*(\d{1,2})\s+([A-Z][a-z]{2})\s*", cell)
    if not match or match.group(2) not in MONTHS:
        return None
    day, month = int(match.group(1)), MONTHS[match.group(2)]
    candidates = [date(year, month, day) for year in (today.year - 1, today.year, today.year + 1)]
    return min(candidates, key=lambda d: abs((d - today).days))


def parse_work_plan(text: str, today: date) -> dict[str, PlanRow]:
    """Points, wave and latest due per task, plus the DoD of the task's epic header.

    Cells are read from the right, so a `|` inside the task cell does not shift the columns.
    """
    plan: dict[str, PlanRow] = {}
    epic_dod: dict[str, str] = {}
    for line in text.splitlines():
        header = EPIC_HEADER.match(line)
        if header:
            epic_dod[header.group(1)] = header.group(2)
            continue
        match = PLAN_ROW.match(line)
        if not match:
            continue
        task_id = match.group(1)
        body = line.rstrip()
        if body.endswith("|"):
            body = body[:-1]
        parts = body.rsplit("|", 3)
        if len(parts) != 4:
            continue
        _, points, wave, due = parts
        epic = task_id.split(".")[0]
        plan[task_id] = PlanRow(
            points=int(points) if points.strip().isdigit() else None,
            wave=wave.strip(),
            due=_due_date(due, today),
            dod=epic_dod.get(epic),
        )
    return plan


def task_id_from_slug(slug: str) -> str | None:
    match = SLUG_ID.match(slug)
    return f"E{match.group(1)}.{match.group(2)}" if match else None


@dataclass(frozen=True)
class ParsedSpec:
    status: str | None
    dod: str | None


def parse_spec(text: str) -> ParsedSpec:
    status = SPEC_STATUS.search(text)
    dod = SPEC_DOD.search(text)
    return ParsedSpec(status.group(1) if status else None, dod.group(1).strip() if dod else None)


def parse_git_log(raw: str) -> list[Commit]:
    """Commits from `--format=%h%x1f%ad%x1f%s%x1f%b%x1e`; review commits carry no task evidence."""
    commits: list[Commit] = []
    for record in raw.split("\x1e"):
        fields = record.strip("\n").split("\x1f")
        if len(fields) != 4:
            continue
        sha, day, subject, body = fields
        if subject.startswith("Progress review"):
            continue
        commits.append(
            Commit(sha.strip(), day, subject, frozenset(TASK_ID.findall(f"{subject}\n{body}")))
        )
    return commits


def latest_review(names: list[str]) -> tuple[str, date] | None:
    """The newest `yyyy-mm-dd.md` across the review directories."""
    dated: list[tuple[date, str]] = []
    for name in names:
        stem = Path(name).stem
        if ISO_DATE.fullmatch(stem):
            dated.append((date.fromisoformat(stem), name))
    if not dated:
        return None
    when, name = max(dated)
    return name, when


def mismatches(rows: list[TrackerRow], specs: dict[str, SpecInfo]) -> list[tuple[str, str]]:
    """Rows whose tracker status and `.scratch` spec status cannot both be true."""
    problems: list[tuple[str, str]] = []
    for row in rows:
        spec = specs.get(row.task_id)
        if spec is None or spec.status is None:
            continue
        if row.status == "✅" and spec.status != "done":
            problems.append((row.task_id, f"tracker ✅ but spec is '{spec.status}'"))
        elif spec.status == "done" and row.status not in ("✅", "⏳"):
            problems.append((row.task_id, f"spec is done but tracker is {row.status}"))
        elif spec.status == "cancelled" and row.status != "🚫":
            problems.append((row.task_id, f"spec is cancelled but tracker is {row.status}"))
        elif row.status == "🚫" and spec.status != "cancelled":
            problems.append((row.task_id, f"tracker 🚫 but spec is '{spec.status}'"))
    return problems


def classify(
    *,
    rows: list[TrackerRow],
    plan: dict[str, PlanRow],
    specs: dict[str, SpecInfo],
    commits: list[Commit],
    since: date,
    today: date,
    window_days: int,
    scope: str,
) -> Classification:
    since_moment = datetime.combine(since, time.min)
    horizon = today + timedelta(days=window_days)
    mismatched = dict(mismatches(rows, specs))
    commit_tasks = {task_id for c in commits for task_id in c.task_ids}
    hot: list[HotTask] = []
    cold: Counter[str] = Counter()
    for row in rows:
        reasons: list[str] = []
        live = row.status != "🚫"
        if scope == "weekly" and live:
            reasons.append("weekly audit")
        if row.status in ("🔄", "⏳"):
            reasons.insert(0, f"status {row.status}")
        spec = specs.get(row.task_id)
        if live and row.task_id in commit_tasks:
            reasons.append("commit since last review")
        if live and spec is not None and spec.touched >= since_moment:
            reasons.append("spec or issues edited since last review")
        due = plan[row.task_id].due if row.task_id in plan else None
        if row.status in LIVE_NOT_DONE and due is not None and due <= horizon:
            reasons.append(f"latest due {due.isoformat()} inside the {window_days}-day window")
        if row.status == "✅" and row.note_date is not None and row.note_date >= since:
            reasons.append(f"done claim dated {row.note_date.isoformat()}")
        if row.task_id in mismatched:
            reasons.append(f"spec mismatch: {mismatched[row.task_id]}")
        if reasons:
            hot.append(HotTask(row.task_id, row.status, row.title, reasons))
        else:
            cold[row.status] += 1
    return Classification(hot, dict(cold))


def _commit_lines(task_id: str, commits: list[Commit]) -> list[str]:
    return [f"    {c.sha} {c.date} {c.subject[:90]}" for c in commits if task_id in c.task_ids][:5]


def format_report(
    result: Classification,
    *,
    plan: dict[str, PlanRow],
    specs: dict[str, SpecInfo],
    commits: list[Commit],
    problems: list[tuple[str, str]],
    last_review: tuple[str, date] | None,
    today: date,
    scope: str,
    window_days: int,
) -> str:
    review = f"{last_review[1].isoformat()} ({last_review[0]})" if last_review else "none found"
    lines = [
        f"Scope: {scope} · window {window_days} days · today {today.isoformat()}",
        f"Last review: {review}",
        f"Hot tasks: {len(result.hot)}",
        "",
    ]
    for task in result.hot:
        row = plan.get(task.task_id)
        spec = specs.get(task.task_id)
        facts = [f"{task.task_id} {task.status} {task.title[:80]}"]
        if row is not None:
            due = (
                f"due {row.due.strftime('%d %b')} ({(row.due - today).days:+d} d)"
                if row.due
                else "no due"
            )
            facts.append(f"  {row.points} pts · wave {row.wave} · {due}")
        dod = (spec.dod if spec and spec.dod else None) or (row.dod if row else None)
        if dod:
            facts.append(f"  DoD {dod}")
        facts.append("  why: " + "; ".join(task.reasons))
        if spec is not None:
            facts.append(f"  spec: {spec.status or 'no status'} ({spec.path})")
        facts.extend(_commit_lines(task.task_id, commits))
        lines.extend(facts)
        lines.append("")
    if problems:
        lines.append("Tracker and spec disagree:")
        lines.extend(f"  {task_id}: {message}" for task_id, message in problems)
        lines.append("")
    counts = ", ".join(f"{status} {n}" for status, n in sorted(result.cold.items()))
    lines.append(
        f"Cold (not opened): {sum(result.cold.values())} tasks" + (f" ({counts})" if counts else "")
    )
    return "\n".join(lines)


def _git(*args: str, root: Path) -> str:
    done = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
    return done.stdout


def scan_specs(root: Path) -> dict[str, SpecInfo]:
    """Specs under `.scratch/` (git-excluded, so the file mtime is the only change signal)."""
    specs: dict[str, SpecInfo] = {}
    scratch = root / ".scratch"
    for directory in [*sorted(scratch.glob("*")), *sorted((scratch / "done").glob("*"))]:
        task_id = task_id_from_slug(directory.name)
        spec_file = directory / "spec.md"
        if task_id is None or task_id in specs or not spec_file.is_file():
            continue
        parsed = parse_spec(spec_file.read_text(encoding="utf-8"))
        files = [spec_file, *sorted((directory / "issues").glob("*.md"))]
        touched = datetime.fromtimestamp(max(f.stat().st_mtime for f in files))
        specs[task_id] = SpecInfo(
            str(spec_file.relative_to(root)), parsed.status, parsed.dod, touched
        )
    return specs


def run_checks(root: Path) -> list[str]:
    """pytest, ruff and mypy: one verdict line each, plus the lines that explain a failure."""
    commands = {
        "pytest": [sys.executable, "-m", "pytest", "-q"],
        "ruff": [sys.executable, "-m", "ruff", "check", "."],
        "mypy": [sys.executable, "-m", "mypy"],
    }
    lines = ["Checks:"]
    for name, command in commands.items():
        try:
            done = subprocess.run(
                command, cwd=root, capture_output=True, text=True, check=False, timeout=1800
            )
        except subprocess.TimeoutExpired:
            lines.append(f"  {name}: timed out after 30 min")
            continue
        output = [line for line in (done.stdout + done.stderr).splitlines() if line.strip()]
        verdict = "ok" if done.returncode == 0 else f"FAILED (exit {done.returncode})"
        lines.append(f"  {name}: {verdict} · {output[-1] if output else 'no output'}")
        if done.returncode != 0:
            keys = ("FAILED", "ERROR", "error:", ".py:")
            lines.extend(f"    {line[:160]}" for line in output if line.startswith(keys))
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--scope", choices=("daily", "weekly"), default="daily")
    parser.add_argument("--window-days", type=int, default=14)
    parser.add_argument("--since", type=date.fromisoformat, help="override the last review date")
    parser.add_argument("--today", type=date.fromisoformat, default=date.today())
    parser.add_argument("--root", type=Path, default=REPO)
    parser.add_argument("--no-checks", action="store_true")
    args = parser.parse_args(argv)
    root: Path = args.root

    tracker_text = (root / "docs/progress-tracker.md").read_text(encoding="utf-8")
    plan = parse_work_plan((root / "docs/tfm-work-plan.md").read_text(encoding="utf-8"), args.today)
    names = [str(p.relative_to(root)) for d in REVIEW_DIRS for p in (root / d).glob("*.md")]
    last_review = latest_review(names)
    updated = re.search(r"^Last updated:\s*(\d{4}-\d{2}-\d{2})", tracker_text, re.MULTILINE)
    since = args.since or (last_review[1] if last_review else None)
    if since is None:
        since = date.fromisoformat(updated.group(1)) if updated else args.today - timedelta(days=7)

    rows = parse_tracker(tracker_text)
    specs = scan_specs(root)
    raw_log = _git(
        "log",
        f"--since={since.isoformat()}",
        "--no-merges",
        "--date=short",
        "--format=%h%x1f%ad%x1f%s%x1f%b%x1e",
        root=root,
    )
    commits = parse_git_log(raw_log)
    result = classify(
        rows=rows,
        plan=plan,
        specs=specs,
        commits=commits,
        since=since,
        today=args.today,
        window_days=args.window_days,
        scope=args.scope,
    )
    print(
        format_report(
            result,
            plan=plan,
            specs=specs,
            commits=commits,
            problems=mismatches(rows, specs),
            last_review=last_review,
            today=args.today,
            scope=args.scope,
            window_days=args.window_days,
        )
    )
    if not args.no_checks:
        print()
        print("\n".join(run_checks(root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
