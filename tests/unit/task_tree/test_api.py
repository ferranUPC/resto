"""The task tree API, served over HTTP from a minimal `.scratch/` and tracker in a temp dir."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from task_tree.server import make_server

TRACKER = """| ID | Task | Status | Notes |
|---|---|---|---|
| E1.1 | Finished task | ✅ | notes for the finished one |
| E1.2 | Open task | ⬜ | not yet |
| E1.3 | Second finished | ✅ | done |
| E3.1 | Other epic | ✅ | done |
| E2.4 | Ticketed task | 🔄 | half built |
| E2.1 | Needs triage task | ⏳ | waits for EXP-01 |
| E2.2 | Ready task | 🚧 | waiting on an external person |
| E2.3 | Specified task | ⬜ | not started |
"""

PLAN = """| ID | Task | Proof | Pts | Wave | Due |
|---|---|---|---|---|---|
| E1.1 | Finished task, planned | tests | 3 | 1a | 5 Oct |
| E2.4 | Ticketed task, planned | tests | 12 | 2 | 11 Dec |

### 4.2 Measurement DAG

```mermaid
flowchart LR
  classDef pass fill:#1f3b73,color:#fff
  classDef suite fill:#e8eefc,color:#000
  classDef task fill:#fff,color:#000

  V1{{"Validation 1 · 14 Dec"}}:::pass
  V2{{"Validation 2<br/>each suite once"}}:::pass
  S1(["EXP-01 forced · $4"]):::suite
  S2(["N4 Parser held-out"]):::suite

  V1 --> V2
  V1 -.->|"reduced checkpoints"| S1
  V2 --> S1 & S2
  S1 --> T1["✅ E4.2 E1.1 report"]:::task
  T1 --> C1["E2.1 calibration · 8"]:::task
  S1 & S2 ==> T2["✅ E5.1"]:::task --> M7(("M7 · 18 Feb")):::pass
end
```
"""

OTHER_SECTION_PLAN = """### 4.2 Measurement DAG

Diagram removed.

### 4.3 Critical paths

```mermaid
flowchart LR
  X(("Not the measurement DAG")):::pass
```
"""

BROKEN_PLAN = """### 4.2 Measurement DAG

```mermaid
flowchart LR
  V1{{"Validation 1"}}:::pass
  this line is not mermaid at all !!
  V1 --> V2
```
"""


def _spec(directory: Path, title: str, status: str, blocked: str, spec: str | None = None) -> None:
    directory.mkdir(parents=True)
    body = f"# {title}\n\n**Status:** {status}\n\n**Blocked by:** {blocked}\n\n"
    if title.startswith("E2.4"):
        body += "**Work plan:** E2.4 · E2 · 12 pts · wave 2 · latest due 11 Dec\n\n"
        body += "**Measured in:** V2 · EXP-01\n\n"
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
        "# 02: Second\n\n**What to build:** Do the second thing.\n\n**Status:** ready\n\n"
        "**Blocked by:** 01\n",
        encoding="utf-8",
    )
    _spec(root / "e2-5-blocked", "E2.5: Blocked", "ready", "E2.1 ([`x`](../x/spec.md))")
    _spec(root / "e2-6-after-done", "E2.6: After a done task", "ready", "E1.1")
    _spec(root / "e2-7-wontfix", "E2.7: Dropped", "wontfix", "None")
    _spec(root / "e2-9-info", "E2.9: Waiting", "needs-info", "None")
    _spec(root / "done" / "e2-10-finished", "E2.10: Finished dir", "done", "None")
    _spec(root / "e2-11-after-dropped", "E2.11: After wontfix", "ready", "E2.7")
    _spec(root / "e2-12-urgent", "E2.12: Urgent spec", "ready", "None")
    _spec(root / "e2-13-urgent-done", "E2.13: Urgent but dropped", "wontfix", "None")
    for name in ("e2-12-urgent", "e2-13-urgent-done"):
        spec = root / name / "spec.md"
        spec.write_text(spec.read_text() + "**Priority:** urgent\n", encoding="utf-8")
    _spec(root / "e2-16-urgent-ticket", "E2.16: Urgent ticket inside", "ready", "None", "A spec.")
    urgent_issues = root / "e2-16-urgent-ticket" / "issues"
    urgent_issues.mkdir()
    (urgent_issues / "01-urgent.md").write_text(
        "# 03: Urgent ticket\n\n**Status:** ready\n\n**Priority:** urgent\n", encoding="utf-8"
    )
    (urgent_issues / "02-urgent-done.md").write_text(
        "# 04: Urgent and done\n\n**Status:** done\n\n**Priority:** urgent\n", encoding="utf-8"
    )
    (root / "e2-14-half").mkdir()
    (root / "e2-14-half" / "spec.md").write_text("# E2.14: Half written\n", encoding="utf-8")
    (root / "e2-15-binary").mkdir()
    (root / "e2-15-binary" / "spec.md").write_bytes(b"\xff\xfe\x00 not utf-8")
    (root / "e2-8-broken").mkdir()
    (root / "e2-8-broken" / "spec.md").write_text("no title, no status\n", encoding="utf-8")
    return root


@pytest.fixture
def plan_text() -> str:
    return PLAN


@pytest.fixture
def launches() -> list[tuple[str, Path]]:
    return []


@pytest.fixture
def base_url(
    scratch: Path, tmp_path: Path, plan_text: str, launches: list[tuple[str, Path]]
) -> Iterator[str]:
    tracker = tmp_path / "progress-tracker.md"
    tracker.write_text(TRACKER, encoding="utf-8")
    plan = tmp_path / "tfm-work-plan.md"
    plan.write_text(plan_text, encoding="utf-8")
    server = make_server(
        scratch, tracker, plan=plan, launcher=lambda prompt, cwd: launches.append((prompt, cwd))
    )
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


def test_a_ticket_row_carries_its_name_stage_and_number_in_order(base_url):
    tickets = _tree(base_url)["E2.4"]["tickets"]
    assert [(t["id"], t["name"], t["stage"]) for t in tickets] == [
        ("01", "First", "done"),
        ("02", "Second", "ready"),
    ]


def test_a_ticket_is_blocked_only_while_a_ticket_it_lists_is_unfinished(base_url, scratch):
    assert [t["blocked"] for t in _tree(base_url)["E2.4"]["tickets"]] == [False, False]
    (scratch / "e2-4-ticketed" / "issues" / "01-first.md").write_text(
        "# 01: First\n\n**Status:** ready\n", encoding="utf-8"
    )
    assert [t["blocked"] for t in _tree(base_url)["E2.4"]["tickets"]] == [False, True]


def test_a_node_with_an_unfinished_blocker_is_blocked_and_has_an_edge(base_url):
    tree = _full_tree(base_url)
    nodes = {node["id"]: node for node in tree["nodes"]}
    assert nodes["E2.5"]["blocked"] is True
    assert nodes["E2.1"]["blocked"] is False
    assert nodes["E2.5"]["column"] == nodes["E2.1"]["column"] + 1
    assert {"from": "E2.1", "to": "E2.5", "done": False, "inferred": False} in tree["edges"]


def test_a_done_blocker_from_the_tracker_leaves_the_node_free_and_the_edge_marked_done(base_url):
    tree = _full_tree(base_url)
    nodes = {node["id"]: node for node in tree["nodes"]}
    assert nodes["E2.6"]["blocked"] is False
    assert {"from": "E1.1", "to": "E2.6", "done": True, "inferred": False} in tree["edges"]
    assert "E1.2" not in nodes  # the tracker lists only finished tasks as nodes


def test_finished_tasks_sit_in_their_own_lane_and_do_not_push_pending_ones_right(base_url):
    nodes = {n["id"]: n for n in _full_tree(base_url)["nodes"]}
    assert nodes["E1.1"]["lane"] == "done"
    assert nodes["E2.6"]["lane"] == "active"
    assert nodes["E2.6"]["column"] == 0  # its only blocker, E1.1, is finished


def test_pending_nodes_are_grouped_into_one_rail_per_milestone_by_latest_due(base_url):
    tree = _full_tree(base_url)
    names = [r["name"] for r in tree["rails"]]
    assert names[0].startswith("Validation 1")  # 14 Dec, the earliest dated milestone
    assert names.index(next(n for n in names if n.startswith("M7"))) == 1  # 18 Feb
    assert names[2].startswith("Validation 2")  # undated milestones close the list
    nodes = {n["id"]: n for n in tree["nodes"]}
    assert nodes["E2.4"]["rail"] == 0  # planned for 11 Dec, before Validation 1 ends
    assert nodes["dag:M7"]["rail"] == 1


def test_task_nodes_carry_the_points_of_their_work_plan_row(base_url):
    nodes = {n["id"]: n for n in _full_tree(base_url)["nodes"]}
    assert nodes["E2.4"]["points"] == 12
    assert nodes["E1.1"]["points"] == 3  # a finished task keeps its points
    assert nodes["E2.6"]["points"] is None  # not in the plan table
    assert nodes["dag:M7"]["points"] is None


def test_a_malformed_spec_yields_a_node_with_a_warning_and_the_rest_still_loads(base_url):
    nodes = _tree(base_url)
    assert nodes["e2-8-broken"]["warnings"]
    assert "E2.1" in nodes


def test_a_half_written_or_unreadable_spec_keeps_its_parsed_fields_and_the_rest_still_loads(
    base_url,
):
    nodes = _tree(base_url)
    assert nodes["E2.14"]["name"] == "Half written"
    assert any("Status" in w for w in nodes["E2.14"]["warnings"])
    assert nodes["e2-15-binary"]["warnings"]
    assert nodes["E2.1"]["warnings"] == []
    assert nodes["E2.12"]["stage"] == "ready"


def test_the_tracker_marks_awaiting_measurement_and_external_blocks_on_exactly_those_tasks(
    base_url,
):
    nodes = _tree(base_url)
    marks = {i: n["tracker_mark"] for i, n in nodes.items() if n["kind"] == "task"}
    assert marks["E2.1"] == "awaiting"
    assert marks["E2.2"] == "blocked"
    assert [i for i, m in marks.items() if m] == ["E2.1", "E2.2"]


def test_an_open_urgent_spec_or_ticket_is_urgent_and_a_finished_one_is_not(base_url):
    nodes = _tree(base_url)
    assert nodes["E2.12"]["urgent"] is True
    assert nodes["E2.13"]["urgent"] is False  # wontfix
    assert nodes["E2.16"]["urgent"] is True  # carries an open urgent ticket
    assert nodes["E2.3"]["urgent"] is False
    assert [t["urgent"] for t in nodes["E2.16"]["tickets"]] == [True, False]


def test_the_frontier_is_every_unblocked_unfinished_task_and_follows_the_specs(base_url, scratch):
    nodes = _tree(base_url)
    assert nodes["E2.3"]["frontier"] is True
    assert nodes["E2.5"]["frontier"] is False  # blocked by E2.1
    assert nodes["E2.9"]["frontier"] is False  # needs-info
    assert nodes["E2.2"]["frontier"] is False  # the tracker marks it 🚧
    assert nodes["E2.7"]["frontier"] is False  # wontfix
    assert nodes["E1.1"]["frontier"] is False  # done
    assert nodes["dag:V1"]["frontier"] is False
    spec = scratch / "e2-1-triage" / "spec.md"
    spec.write_text(spec.read_text().replace("needs-triage", "done"), encoding="utf-8")
    nodes = _tree(base_url)
    assert nodes["E2.1"]["frontier"] is False
    assert nodes["E2.5"]["frontier"] is True


def test_editing_a_spec_changes_the_next_response_without_restarting(base_url, scratch):
    assert _tree(base_url)["E2.1"]["stage"] == "needs-triage"
    spec = scratch / "e2-1-triage" / "spec.md"
    spec.write_text(spec.read_text().replace("needs-triage", "wontfix"), encoding="utf-8")
    assert _tree(base_url)["E2.1"]["stage"] == "wontfix"


def test_the_page_is_served_and_the_server_binds_to_loopback_only(base_url):
    assert base_url.startswith("http://127.0.0.1:")
    with urllib.request.urlopen(f"{base_url}/") as response:
        assert b"/api/tree" in response.read()


def test_done_tasks_without_a_spec_get_guessed_edges_within_and_across_epics(base_url):
    tree = _full_tree(base_url)
    guessed = [(e["from"], e["to"]) for e in tree["edges"] if e["inferred"]]
    assert sorted(guessed) == [("E1.1", "E1.3"), ("E1.1", "E3.1")]
    assert all(e["done"] for e in tree["edges"] if e["inferred"])
    assert not any(e["inferred"] for e in tree["edges"] if e["to"] in ("E2.5", "E2.6"))


def _get(base_url: str, path: str) -> tuple[int, dict[str, Any] | None]:
    try:
        with urllib.request.urlopen(f"{base_url}{path}") as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as err:
        return err.code, None


def test_a_task_detail_carries_its_stage_spec_header_and_tickets(base_url):
    status, detail = _get(base_url, "/api/task/E2.4")
    assert status == 200 and detail is not None
    assert detail["stage"] == "ticketed"
    assert (detail["points"], detail["latest_due"]) == ("12", "11 Dec")
    assert detail["measured_in"] == "V2 · EXP-01"
    assert [t["id"] for t in detail["tickets"]] == ["01", "02"]


def test_a_done_task_absent_from_scratch_still_shows_what_the_plan_and_tracker_hold(base_url):
    status, detail = _get(base_url, "/api/task/E1.1")
    assert status == 200 and detail is not None
    assert detail["stage"] == "done"
    assert "Finished task, planned" in detail["plan_excerpt"]
    assert detail["tracker_notes"] == "notes for the finished one"
    assert detail["tickets"] == []


def test_a_ticket_detail_carries_its_question_status_and_blockers(base_url):
    status, detail = _get(base_url, "/api/task/E2.4/ticket/02")
    assert status == 200 and detail is not None
    assert detail["question"] == "Do the second thing."
    assert (detail["stage"], detail["blocked_by"], detail["task_id"]) == ("ready", ["01"], "E2.4")


def test_an_unknown_task_or_ticket_is_a_404(base_url):
    assert _get(base_url, "/api/task/E9.9")[0] == 404
    assert _get(base_url, "/api/task/E2.4/ticket/09")[0] == 404
    assert _get(base_url, "/api/task/E2.1/ticket/01")[0] == 404


def test_a_task_with_a_spec_also_shows_its_plan_row_and_tracker_notes(base_url):
    _, detail = _get(base_url, "/api/task/E2.4")
    assert detail is not None
    assert "Ticketed task, planned" in detail["plan_excerpt"]
    assert (detail["tracker_status"], detail["tracker_notes"]) == ("🔄", "half built")


def test_a_task_without_a_spec_shows_no_guessed_blockers(base_url):
    _, detail = _get(base_url, "/api/task/E1.3")
    assert detail is not None and detail["blocked_by"] == []


def test_the_measurement_dag_adds_milestone_suite_and_validates_nodes_with_their_labels(base_url):
    nodes = _tree(base_url)
    assert nodes["dag:V1"]["kind"] == "milestone"
    assert nodes["dag:V1"]["name"] == "Validation 1 · 14 Dec"
    assert nodes["dag:V2"]["name"] == "Validation 2 each suite once"
    assert nodes["dag:S1"]["kind"] == "suite"
    assert nodes["dag:T1"]["kind"] == "validates"
    assert nodes["dag:M7"]["kind"] == "milestone"
    assert nodes["E2.1"]["kind"] == "task"
    assert len([n for n in nodes if n.startswith("dag:")]) == 7


def test_the_measurement_dag_edges_follow_chains_fan_out_and_labelled_arrows(base_url):
    tree = _full_tree(base_url)
    pairs = {(e["from"], e["to"]) for e in tree["edges"] if e["from"].startswith("dag:")}
    assert pairs == {
        ("dag:V1", "dag:V2"), ("dag:V1", "dag:S1"), ("dag:V2", "dag:S1"), ("dag:V2", "dag:S2"),
        ("dag:S1", "dag:T1"), ("dag:S1", "dag:T2"), ("dag:S2", "dag:T2"), ("dag:T2", "dag:M7"),
        ("dag:T1", "E2.1"),
    }
    nodes = {n["id"]: n for n in tree["nodes"]}
    assert nodes["dag:S1"]["column"] > nodes["dag:V2"]["column"]
    assert tree["warnings"] == []


def test_a_change_to_the_mermaid_block_shows_up_on_the_next_request(base_url, tmp_path):
    (tmp_path / "tfm-work-plan.md").write_text(
        '### 4.2 DAG\n\n```mermaid\nflowchart LR\n  A(("Only one")):::pass\n```\n', encoding="utf-8"
    )
    nodes = _tree(base_url)
    assert nodes["dag:A"]["name"] == "Only one"
    assert "dag:V1" not in nodes


@pytest.mark.parametrize("plan_text", [BROKEN_PLAN, "no diagram here\n", OTHER_SECTION_PLAN])
def test_an_unreadable_measurement_dag_keeps_the_tasks_and_reports_a_warning(base_url):
    tree = _full_tree(base_url)
    assert any(n["id"] == "E2.1" and n["kind"] == "task" for n in tree["nodes"])
    assert tree["warnings"]


def test_dag_nodes_named_after_a_real_task_are_that_task_and_validates_nodes_link_from_theirs(
    base_url,
):
    tree = _full_tree(base_url)
    nodes = {n["id"]: n for n in tree["nodes"]}
    pairs = {(e["from"], e["to"]) for e in tree["edges"]}
    assert "dag:C1" not in nodes  # "E2.1 calibration" is the real task E2.1
    assert ("dag:T1", "E2.1") in pairs
    assert ("E1.1", "dag:T1") in pairs  # a task listed in a "✅" node leads to it
    assert not any(t == "dag:T1" and f == "E4.2" for f, t in pairs)  # E4.2 is not a node
    assert nodes["E2.1"]["column"] > nodes["dag:T1"]["column"]
    assert nodes["E2.1"]["blocked"] is False  # the diagram never blocks a task


def _post(base_url: str, body: dict[str, Any]) -> int:
    request = urllib.request.Request(
        f"{base_url}/api/launch",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request) as response:
            return int(response.status)
    except urllib.error.HTTPError as err:
        return err.code


@pytest.mark.parametrize(
    ("task", "directory", "expected"),
    [
        ("E2.1", "e2-1-triage", "/triage {spec}"),
        (
            "E2.2",
            "e2-2-ready",
            "/grill-with-docs {spec} and, once the decisions are settled, run /to-spec on it "
            "in this same session.",
        ),
        ("E2.3", "e2-3-specified", "/to-tickets {spec}"),
        ("E2.4", "e2-4-ticketed", "/implement {ticket}"),
    ],
)
def test_the_next_step_button_launches_the_fixed_template_of_the_stage(
    base_url, scratch, launches, task, directory, expected
):
    assert _post(base_url, {"id": task, "action": "next"}) == 200
    root = scratch.parent
    spec = f".scratch/{directory}/spec.md"
    ticket = f".scratch/{directory}/issues/02-second.md"
    assert launches == [(expected.format(spec=spec, ticket=ticket), root)]


def test_ticketed_launches_the_first_takeable_ticket_and_a_ticket_row_only_its_own(
    base_url, scratch, launches
):
    (scratch / "e2-4-ticketed" / "issues" / "01-first.md").write_text(
        "# 01: First\n\n**Status:** ready\n", encoding="utf-8"
    )
    assert _post(base_url, {"id": "E2.4", "action": "next"}) == 200
    assert _post(base_url, {"id": "E2.4", "action": "ticket", "ticket": "02"}) == 200
    assert [p for p, _ in launches] == [
        "/implement .scratch/e2-4-ticketed/issues/01-first.md",
        "/implement .scratch/e2-4-ticketed/issues/02-second.md",
    ]


def test_grill_opens_grill_with_docs_on_the_spec_in_every_stage_but_done(
    base_url, scratch, launches
):
    for task in ("E2.1", "E2.2", "E2.3", "E2.4"):
        assert _post(base_url, {"id": task, "action": "grill"}) == 200
    assert all(p.startswith("/grill-with-docs .scratch/") for p, _ in launches)
    assert len(launches) == 4
    assert _post(base_url, {"id": "E2.10", "action": "grill"}) == 400
    assert len(launches) == 4


def test_an_unknown_id_action_or_ticket_is_rejected_and_launches_nothing(base_url, launches):
    bad = [
        {"id": "E9.9", "action": "next"},
        {"id": "E2.1", "action": "rm -rf"},
        {"id": "E2.1"},
        {"id": "E2.4", "action": "ticket", "ticket": "99"},
        {"id": "E2.4", "action": "ticket", "ticket": "../../etc"},
        {"id": "E1.1", "action": "next"},  # done, no spec
        {"id": "E2.10", "action": "next"},  # done
        {"id": "E2.7", "action": "next"},  # wontfix
    ]
    assert [_post(base_url, body) for body in bad] == [400] * len(bad)
    assert launches == []


def test_the_prompt_reaches_claude_as_one_shell_argument_even_with_quotes_and_spaces():
    import shlex

    from task_tree.launch import terminal_command

    prompt = "/implement .scratch/it's a dir/issues/01-\"x\" $(y).md"
    words = shlex.split(terminal_command(prompt, Path("/repo root")))
    assert words == ["cd", "/repo root", "&&", "claude", prompt]
