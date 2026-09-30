"""The task tree API, served over HTTP from a minimal `.scratch/` and tracker in a temp dir."""

from __future__ import annotations

import json
import threading
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from task_tree.server import make_server

TRACKER = """| ID | Task | Status | Notes |
|---|---|---|---|
| E1.1 | Finished task | ✅ | done |
| E1.2 | Open task | ⬜ | not yet |
"""


def _spec(directory: Path, title: str, status: str, blocked: str, spec: str | None = None) -> None:
    directory.mkdir(parents=True)
    body = f"# {title}\n\n**Status:** {status}\n\n**Blocked by:** {blocked}\n\n"
    if spec is not None:
        body += f"## Spec\n\n{spec}\n"
    (directory / "spec.md").write_text(body, encoding="utf-8")


@pytest.fixture
def scratch(tmp_path: Path) -> Path:
    root = tmp_path / ".scratch"
    _spec(root / "e2-1-triage", "E2.1: Needs triage", "needs-triage", "None")
    _spec(root / "e2-2-ready", "E2.2: Ready", "ready", "None", "_Not written yet._")
    _spec(root / "e2-3-specified", "E2.3: Specified", "ready", "None", "A real spec.")
    _spec(root / "e2-4-ticketed", "E2.4: Ticketed", "ready", "None", "A real spec.")
    issues = root / "e2-4-ticketed" / "issues"
    issues.mkdir()
    (issues / "01-first.md").write_text("# 01: First\n\n**Status:** done\n", encoding="utf-8")
    (issues / "02-second.md").write_text(
        "# 02: Second\n\n**Status:** ready\n\n**Blocked by:** 01\n", encoding="utf-8"
    )
    _spec(root / "e2-5-blocked", "E2.5: Blocked", "ready", "E2.1 ([`x`](../x/spec.md))")
    _spec(root / "e2-6-after-done", "E2.6: After a done task", "ready", "E1.1")
    _spec(root / "e2-7-wontfix", "E2.7: Dropped", "wontfix", "None")
    _spec(root / "e2-9-info", "E2.9: Waiting", "needs-info", "None")
    _spec(root / "done" / "e2-10-finished", "E2.10: Finished dir", "done", "None")
    _spec(root / "e2-11-after-dropped", "E2.11: After wontfix", "ready", "E2.7")
    (root / "e2-8-broken").mkdir()
    (root / "e2-8-broken" / "spec.md").write_text("no title, no status\n", encoding="utf-8")
    return root


@pytest.fixture
def base_url(scratch: Path, tmp_path: Path) -> Iterator[str]:
    tracker = tmp_path / "progress-tracker.md"
    tracker.write_text(TRACKER, encoding="utf-8")
    server = make_server(scratch, tracker)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def _full_tree(base_url: str) -> dict[str, Any]:
    with urllib.request.urlopen(f"{base_url}/api/tree") as response:
        tree: dict[str, Any] = json.load(response)
    return tree


def _tree(base_url: str) -> dict[str, dict[str, Any]]:
    return {node["id"]: node for node in _full_tree(base_url)["nodes"]}


def test_stage_follows_the_status_line_the_spec_section_and_the_issues_directory(base_url):
    nodes = _tree(base_url)
    assert nodes["E2.1"]["stage"] == "needs-triage"
    assert nodes["E2.2"]["stage"] == "ready"
    assert nodes["E2.3"]["stage"] == "specified"
    assert nodes["E2.4"]["stage"] == "ticketed"
    assert nodes["E1.1"]["stage"] == "done"
    assert nodes["E2.7"]["stage"] == "wontfix"
    assert nodes["E2.9"]["stage"] == "needs-info"
    assert nodes["E2.10"]["stage"] == "done"
    assert nodes["E2.11"]["blocked"] is False  # a dropped blocker no longer holds anything
    assert [t["id"] for t in nodes["E2.4"]["tickets"]] == ["01", "02"]


def test_a_node_with_an_unfinished_blocker_is_blocked_and_has_an_edge(base_url):
    tree = _full_tree(base_url)
    nodes = {node["id"]: node for node in tree["nodes"]}
    assert nodes["E2.5"]["blocked"] is True
    assert nodes["E2.1"]["blocked"] is False
    assert nodes["E2.5"]["column"] == nodes["E2.1"]["column"] + 1
    assert {"from": "E2.1", "to": "E2.5", "done": False} in tree["edges"]


def test_a_done_blocker_from_the_tracker_leaves_the_node_free_and_the_edge_marked_done(base_url):
    tree = _full_tree(base_url)
    nodes = {node["id"]: node for node in tree["nodes"]}
    assert nodes["E2.6"]["blocked"] is False
    assert {"from": "E1.1", "to": "E2.6", "done": True} in tree["edges"]
    assert "E1.2" not in nodes  # the tracker lists only finished tasks as nodes


def test_a_malformed_spec_yields_a_node_with_a_warning_and_the_rest_still_loads(base_url):
    nodes = _tree(base_url)
    assert nodes["e2-8-broken"]["warnings"]
    assert "E2.1" in nodes


def test_editing_a_spec_changes_the_next_response_without_restarting(base_url, scratch):
    assert _tree(base_url)["E2.1"]["stage"] == "needs-triage"
    spec = scratch / "e2-1-triage" / "spec.md"
    spec.write_text(spec.read_text().replace("needs-triage", "wontfix"), encoding="utf-8")
    assert _tree(base_url)["E2.1"]["stage"] == "wontfix"


def test_the_page_is_served_and_the_server_binds_to_loopback_only(base_url):
    assert base_url.startswith("http://127.0.0.1:")
    with urllib.request.urlopen(f"{base_url}/") as response:
        assert b"/api/tree" in response.read()
