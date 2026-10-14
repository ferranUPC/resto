"""`NetworkPromoter` (E6.1/02; ADR-0001, ADR-0045 §9): the recipe of a draft is replayed without an
LLM, with real `netgenerate` and `netconvert`, and the draft is promoted only if the replay gives
the hash the draft claims and a failed sanity check was reported."""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import pytest

from resto.adapters.sumo.netconvert import SubprocessNetconvertRunner
from resto.adapters.sumo.plain_edit import XmlPlainNetEditor
from resto.application.ports.llm import AgentRun, StopReason
from resto.application.promoters.network import NetworkPromoter
from resto.application.promotion import Blame, DraftRejected, RunWithoutDraft
from resto.domain.entities.network import Network
from resto.domain.value_objects.drafts import NetworkDraft, UnresolvedIssue
from resto.domain.value_objects.network_recipe import NetworkRecipe
from resto.domain.value_objects.network_source import GridNetwork
from resto.domain.value_objects.sanity_report import SanityReport
from resto.domain.value_objects.step_record import Usage
from resto.domain.value_objects.tasks import NetworkTask, ObtainNetworkTask
from resto.domain.value_objects.topology_modification import (
    AddEdge,
    RemoveEdge,
    SetLanes,
    SetSpeed,
    TopologyModification,
)
from tests.unit.domain._fixtures import bad_sanity, good_sanity, network_draft

RUNNER = SubprocessNetconvertRunner()
GRID = GridNetwork(x_number=3, y_number=3)
OBTAIN = ObtainNetworkTask(network_ref="a 3 by 3 grid", max_rounds=2)


class SpeedEditor:
    """`PlainNetEditor` double that understands only `set_speed`, enough to replay a derivation."""

    def apply(self, plain_dir: Path, modification: TopologyModification) -> None:
        assert isinstance(modification, SetSpeed)
        for edges in plain_dir.glob("*.edg.xml"):
            text = edges.read_text()
            edges.write_text(
                re.sub(
                    rf'(id="{modification.edge_id}"[^>]*?speed=")[^"]*"',
                    rf'\g<1>{modification.speed}"',
                    text,
                )
            )


def run_of(draft: NetworkDraft | None) -> AgentRun[NetworkDraft]:
    reason = StopReason.OUTPUT if draft else StopReason.BUDGET
    return AgentRun(output=draft, tool_calls=(), usage=Usage(), stop_reason=reason)


def promoter() -> NetworkPromoter:
    return NetworkPromoter(RUNNER, SpeedEditor())


def grid_draft(tmp_path: Path, **overrides: object) -> NetworkDraft:
    built = RUNNER.generate(GRID, tmp_path / "agent")
    return network_draft(recipe=NetworkRecipe(source=GRID), net_artifact=built, **overrides)


def test_a_generated_network_is_promoted_with_its_content_hash_as_id(tmp_path: Path) -> None:
    draft = grid_draft(tmp_path)

    network = promoter().promote(run_of(draft), OBTAIN)

    assert network.network_id == draft.net_artifact.content_hash
    assert network.net_xml == draft.net_artifact
    assert network.recipe == draft.recipe
    assert network.sanity_report == draft.sanity_report
    assert network.derived_from is None


def test_a_replay_that_gives_another_hash_is_rejected(tmp_path: Path) -> None:
    other = RUNNER.generate(GridNetwork(x_number=4, y_number=3), tmp_path / "other")
    draft = network_draft(recipe=NetworkRecipe(source=GRID), net_artifact=other)

    with pytest.raises(DraftRejected, match="content_hash") as rejected:
        promoter().promote(run_of(draft), OBTAIN)

    assert rejected.value.blame is Blame.AGENT


def test_a_failed_sanity_check_with_nothing_reported_is_rejected(tmp_path: Path) -> None:
    draft = grid_draft(tmp_path, sanity_report=bad_sanity())

    with pytest.raises(DraftRejected, match="sanity") as rejected:
        promoter().promote(run_of(draft), OBTAIN)

    assert rejected.value.blame is Blame.AGENT


def test_a_failed_sanity_check_is_promoted_when_the_issue_is_reported(tmp_path: Path) -> None:
    issue = UnresolvedIssue("junction", "A0", "dead end", needed_tool="add_node")
    draft = grid_draft(tmp_path, sanity_report=bad_sanity(), unresolved=(issue,))

    network = promoter().promote(run_of(draft), OBTAIN)

    assert network.sanity_report == bad_sanity()


def test_the_task_threshold_decides_whether_the_sanity_check_failed(tmp_path: Path) -> None:
    middling = SanityReport(
        largest_scc_ratio=0.9, zero_length_edges=0, all_reachable_from_fringe=True
    )
    draft = grid_draft(tmp_path, sanity_report=middling)

    with pytest.raises(DraftRejected, match="sanity"):
        promoter().promote(run_of(draft), OBTAIN)
    lenient = replace(OBTAIN, min_scc_ratio=0.85)
    assert promoter().promote(run_of(draft), lenient).sanity_report == middling


def test_a_run_without_a_draft_is_refused(tmp_path: Path) -> None:
    with pytest.raises(RunWithoutDraft):
        promoter().promote(run_of(None), OBTAIN)


def test_options_on_a_generated_network_are_rejected_not_ignored(tmp_path: Path) -> None:
    draft = grid_draft(tmp_path)
    recipe = replace(draft.recipe, netconvert_options=("--no-turnarounds",))

    with pytest.raises(DraftRejected, match="netconvert_options"):
        promoter().promote(run_of(replace(draft, recipe=recipe)), OBTAIN)


def test_an_obtained_network_cannot_be_a_derivation(tmp_path: Path) -> None:
    draft = network_draft(recipe=NetworkRecipe(base_network_id="base1"))

    with pytest.raises(DraftRejected, match="derivation"):
        promoter().promote(run_of(draft), OBTAIN)


def stored_base(tmp_path: Path) -> Network:
    built = RUNNER.generate(GRID, tmp_path / "base")
    base = Network(
        network_id=built.content_hash,
        net_xml=built,
        recipe=NetworkRecipe(source=GRID),
        sanity_report=good_sanity(),
    )
    return base


def derived_draft(tmp_path: Path, base: Network, edits: tuple[SetSpeed, ...]) -> NetworkDraft:
    plain = RUNNER.export_plain(base.net_xml, tmp_path / "plain")
    for edit in edits:
        SpeedEditor().apply(plain, edit)
    built = RUNNER.build(None, plain, (), tmp_path / "derived")
    recipe = NetworkRecipe(base_network_id=base.network_id, plain_edits=edits)
    return network_draft(recipe=recipe, net_artifact=built)


def test_a_derived_network_replays_from_its_base_and_points_at_it(tmp_path: Path) -> None:
    base = stored_base(tmp_path)
    draft = derived_draft(tmp_path, base, (SetSpeed("A0A1", 8.33),))
    task = NetworkTask(base_network_id=base.network_id, max_rounds=2)

    network = promoter().promote(run_of(draft), task, base.net_xml)

    assert network.derived_from == base.network_id
    assert network.network_id != base.network_id
    assert network.network_id == draft.net_artifact.content_hash


def test_a_derivation_whose_edits_do_not_give_the_claimed_hash_is_rejected(
    tmp_path: Path,
) -> None:
    base = stored_base(tmp_path)
    draft = derived_draft(tmp_path, base, (SetSpeed("A0A1", 8.33),))
    claimed = replace(draft.recipe, plain_edits=(SetSpeed("A0A1", 5.0),))
    task = NetworkTask(base_network_id=base.network_id, max_rounds=2)

    with pytest.raises(DraftRejected, match="content_hash"):
        promoter().promote(run_of(replace(draft, recipe=claimed)), task, base.net_xml)


def test_a_derivation_must_start_from_the_task_base_network(tmp_path: Path) -> None:
    base = stored_base(tmp_path)
    draft = derived_draft(tmp_path, base, (SetSpeed("A0A1", 8.33),))
    task = NetworkTask(base_network_id="someone-else", max_rounds=2)

    with pytest.raises(DraftRejected, match="base"):
        promoter().promote(run_of(draft), task, base.net_xml)


ALL_EDITS: tuple[TopologyModification, ...] = (
    RemoveEdge("A0A1"),
    AddEdge("A0", "C2", lanes=2, speed=11.11, edge_id="shortcut"),
    SetLanes("B0B1", 2),
    SetSpeed("B0C0", 8.33),
)


def real_derived_draft(
    tmp_path: Path, base: Network, edits: tuple[TopologyModification, ...]
) -> NetworkDraft:
    """What the edit tools leave behind: the base exported, edited with the real editor, rebuilt."""
    plain = RUNNER.export_plain(base.net_xml, tmp_path / "plain")
    for edit in edits:
        XmlPlainNetEditor().apply(plain, edit)
    built = RUNNER.build(None, plain, (), tmp_path / "derived")
    recipe = NetworkRecipe(base_network_id=base.network_id, plain_edits=edits)
    return network_draft(recipe=recipe, net_artifact=built)


def test_the_four_edits_replay_to_the_same_hash_and_the_derived_network_points_at_its_base(
    tmp_path: Path,
) -> None:
    base = stored_base(tmp_path)
    draft = real_derived_draft(tmp_path, base, ALL_EDITS)
    task = NetworkTask(base_network_id=base.network_id, max_rounds=2)

    network = NetworkPromoter(RUNNER, XmlPlainNetEditor()).promote(
        run_of(draft), task, base.net_xml
    )

    assert network.derived_from == base.network_id
    assert network.network_id == draft.net_artifact.content_hash != base.network_id
    assert network.recipe.plain_edits == ALL_EDITS


def test_each_edit_changes_the_network_it_derives(tmp_path: Path) -> None:
    base = stored_base(tmp_path)
    hashes = {
        real_derived_draft(tmp_path / str(i), base, (edit,)).net_artifact.content_hash
        for i, edit in enumerate(ALL_EDITS)
    }

    assert len(hashes) == len(ALL_EDITS)
    assert base.network_id not in hashes


def test_a_recipe_with_an_edit_that_cannot_apply_is_rejected_not_approximated(
    tmp_path: Path,
) -> None:
    base = stored_base(tmp_path)
    draft = real_derived_draft(tmp_path, base, (SetSpeed("B0C0", 8.33),))
    bad = replace(draft.recipe, plain_edits=(AddEdge("A0", "Z9", lanes=1, speed=8.0),))
    task = NetworkTask(base_network_id=base.network_id, max_rounds=2)

    with pytest.raises(DraftRejected, match="add_node") as rejected:
        NetworkPromoter(RUNNER, XmlPlainNetEditor()).promote(
            run_of(replace(draft, recipe=bad)), task, base.net_xml
        )

    assert rejected.value.blame is Blame.AGENT
