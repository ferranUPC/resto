"""Terminal launches: fixed prompt templates for ids that exist, opened in Terminal.app."""

from __future__ import annotations

import shlex
import subprocess
from collections.abc import Callable
from pathlib import Path

from task_tree.tree import CLOSED, _load_tasks

Launcher = Callable[[str, Path], None]

DAILY_REVIEW_ACTION = "daily-review"
DAILY_REVIEW_PROMPT = "/daily-review"


class LaunchRejected(ValueError):
    """The id, action or ticket does not match anything that exists."""


def terminal_command(prompt: str, cwd: Path) -> str:
    """The shell line Terminal runs: the prompt is one quoted argument to `claude`."""
    return f"cd {shlex.quote(str(cwd))} && claude {shlex.quote(prompt)}"


def _applescript_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def terminal_launcher(prompt: str, cwd: Path) -> None:
    """Open a new Terminal.app window running `claude` with `prompt` as its first message."""
    script = (
        'tell application "Terminal"\n'
        "  activate\n"
        f"  do script {_applescript_string(terminal_command(prompt, cwd))}\n"
        "end tell"
    )
    subprocess.run(["osascript", "-e", script], check=True, capture_output=True, timeout=30)


def build_prompt(
    scratch: Path,
    tracker: Path,
    task_id: str,
    action: str,
    ticket_id: str | None = None,
) -> str:
    """The fixed prompt for `action` on `task_id`, or LaunchRejected when nothing matches."""
    tasks, _ = _load_tasks(scratch, tracker)
    task = tasks.get(task_id)
    if task is None or task.directory is None or not (task.directory / "spec.md").is_file():
        raise LaunchRejected(f"unknown task {task_id!r}")
    root = scratch.parent
    spec = (task.directory / "spec.md").relative_to(root).as_posix()
    if action == "grill":
        if task.stage in ("done", "cancelled"):
            raise LaunchRejected(f"a {task.stage} task has nothing left to grill")
        return f"/grill-with-docs {spec}"
    if action == "implement-spec":
        if task.stage != "ticketed" or not any(
            t["stage"] not in CLOSED and not t["blocked"] for t in task.tickets
        ):
            raise LaunchRejected("only a ticketed task with a takeable ticket can be implemented")
        return f"/implement-spec {spec}"
    if action == "ticket" or (action == "next" and task.stage == "ticketed"):
        if action == "ticket":
            ticket = next((t for t in task.tickets if t["id"] == ticket_id), None)
        else:
            ticket = next(
                (t for t in task.tickets if t["stage"] not in CLOSED and not t["blocked"]), None
            )
        if ticket is None:
            raise LaunchRejected("no such ticket, or none is takeable")
        path = next((task.directory / "issues").glob(f"{ticket['id']}-*.md"), None)
        if path is None:
            raise LaunchRejected("ticket file is gone")
        return f"/implement {path.relative_to(root).as_posix()}"
    if action != "next":
        raise LaunchRejected(f"unknown action {action!r}")
    if task.stage == "needs-triage":
        return f"/triage {spec}"
    if task.stage == "ready":
        return (
            f"/grill-with-docs {spec} and, once the decisions are settled, run /to-spec on it "
            "in this same session."
        )
    if task.stage == "specified":
        return f"/to-tickets {spec}"
    raise LaunchRejected(f"no next step for stage {task.stage!r}")
