"""A specialist that returns `NeedsUser` through `execute_study` with the scripted agents (ADR-0037
§4): the study ends in `awaiting_user` at that step, never in `failed`, and never goes back to the
Coordinator."""

from pathlib import Path

import pytest

from resto.domain.entities.study import StudyStatus
from resto.domain.value_objects.outcomes import (
    DemandNotNamed,
    DemandNotObtainable,
    Found,
    FoundItem,
    NeedsUser,
    NeedsUserReason,
    NetworkNotFound,
    SeveralCandidates,
    WindowMissing,
)
from resto.domain.value_objects.step_record import StepStatus
from resto.interface.render import render_study
from tests.unit.application._world import DESCRIBE, World, answers, run_of, tools
from tests.unit.application.executor.test_obtain_steps import _obtain_plan
from tests.unit.domain._fixtures import NET, demand_draft, network_draft

NETWORK_SIDE: tuple[tuple[NeedsUserReason, tuple[str, ...]], ...] = (
    (NetworkNotFound("Gran Via"), ()),
    (SeveralCandidates(), ("BCN-1347", "BCN-1211")),
)
DEMAND_SIDE: tuple[tuple[NeedsUserReason, tuple[str, ...]], ...] = (
    (WindowMissing(), ()),
    (DemandNotNamed(), ()),
    (DemandNotObtainable("Easter 2019 traffic"), ()),
    (SeveralCandidates(), ("peak-a", "peak-b")),
)


def _needs(reason: NeedsUserReason, candidates: tuple[str, ...], **kw: object) -> NeedsUser:
    return NeedsUser(reason, f"I was asked for it and cannot: {reason.kind}", candidates, **kw)  # type: ignore[arg-type]


@pytest.mark.parametrize(("reason", "candidates"), NETWORK_SIDE)
def test_the_network_author_needing_the_user_stops_the_study(
    tmp_path: Path, reason: NeedsUserReason, candidates: tuple[str, ...]
) -> None:
    needs = _needs(reason, candidates)
    world = World(tmp_path, plans=(_obtain_plan(),), author=(run_of(needs, tokens=70),))

    study = world.run()

    assert study.status is StudyStatus.AWAITING_USER
    phase = study.phases[0]
    assert phase.needs_user == needs
    assert tools(study) == [
        ("plan", StepStatus.OK),
        ("obtain_network", StepStatus.NEEDS_USER),
        ("obtain_demand", StepStatus.SKIPPED),
        ("build_scenario", StepStatus.SKIPPED),
        ("run_simulation", StepStatus.SKIPPED),
    ]
    assert phase.steps[1].usage.input_tokens == 70
    assert world.generator.calls == [] and world.builder.calls == []
    assert world.expert.calls == []


@pytest.mark.parametrize(("reason", "candidates"), DEMAND_SIDE)
def test_the_demand_generator_needing_the_user_keeps_what_was_found(
    tmp_path: Path, reason: NeedsUserReason, candidates: tuple[str, ...]
) -> None:
    needs = _needs(reason, candidates, found=(FoundItem("network", NET),))
    world = World(tmp_path, plans=(_obtain_plan(),), generator=(run_of(needs),))

    study = world.run()

    assert study.status is StudyStatus.AWAITING_USER
    phase = study.phases[0]
    assert phase.needs_user == needs
    assert phase.needs_user.candidates == candidates  # type: ignore[union-attr]
    assert [(s.tool, s.status) for s in phase.steps] == [
        ("plan", StepStatus.OK),
        ("obtain_network", StepStatus.OK),
        ("obtain_demand", StepStatus.NEEDS_USER),
        ("build_scenario", StepStatus.SKIPPED),
        ("run_simulation", StepStatus.SKIPPED),
    ]
    assert phase.steps[1].produced_ids == (NET,)  # the network found stays on the record
    assert study.network_ids == (NET,)
    assert world.builder.calls == [] and world.expert.calls == []


def test_the_study_never_goes_back_to_the_coordinator(tmp_path: Path) -> None:
    world = World(
        tmp_path,
        plans=(_obtain_plan(),),
        generator=(run_of(_needs(DemandNotNamed(), ())),),
    )

    world.run()

    assert len(world.coordinator.calls) == 1


def test_a_rerun_after_awaiting_user_reuses_what_was_promoted(tmp_path: Path) -> None:
    world = World(
        tmp_path,
        plans=(_obtain_plan(), _obtain_plan()),
        author=(run_of(network_draft(), tokens=100), run_of(Found("obtained-1"))),
        generator=(run_of(_needs(WindowMissing(), ())), run_of(demand_draft())),
        expert=(answers(),),
    )

    first = world.run()
    world.parser.items.append(run_of(DESCRIBE, tokens=50))
    second = world.run()

    assert first.status is StudyStatus.AWAITING_USER
    assert len(world.promoted_networks) == 1  # promoted once, the rerun found it
    assert second.status is StudyStatus.COMPLETED
    assert second.phases[0].steps[1].produced_ids == ("obtained-1",)


def test_the_waiting_study_renders_without_a_model_call(tmp_path: Path) -> None:
    needs = _needs(SeveralCandidates(), ("peak-a", "peak-b"), found=(FoundItem("network", NET),))
    world = World(tmp_path, plans=(_obtain_plan(),), generator=(run_of(needs),))
    study = world.run()
    calls = [len(a.calls) for a in (world.parser, world.coordinator, world.author, world.generator)]

    text = render_study(study)

    assert needs.message in text
    assert "Candidates:\n- peak-a\n- peak-b" in text
    assert f"Already found:\n- network `{NET}`" in text
    assert f"- `obtain_network` ok: {NET}" in text
    assert "Ask again, naming the one you mean." in text
    assert calls == [
        len(a.calls) for a in (world.parser, world.coordinator, world.author, world.generator)
    ]

