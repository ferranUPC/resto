"""`run_study` (E5.10; ADR-0023, ADR-0025, ADR-0026, ADR-0027): golden-path shapes, one failure per
`StepError.kind`, dedup, notes, and a Study persisted after every step. No network."""

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from resto.application.executor import (
    StudyBudget,
)
from resto.application.ports.llm import StopReason
from resto.application.ports.network_query import NetworkNotStored
from resto.application.ports.tracing import (
    ExpertRoundHeld,
    ModelCall,
    NoteStatusChanged,
    NoteWriterFailed,
    PhaseStarted,
    PlanMade,
    ReportComposed,
    StepTraced,
    StudyCreated,
)
from resto.application.use_cases.run_study import ParserFailed
from resto.domain.constants import DEFAULT_SEEDS
from resto.domain.entities.expert_note import ExpertNote, NoteStatus, Provenance
from resto.domain.entities.simulation_result import RunMode
from resto.domain.entities.study import Study, StudyStatus
from resto.domain.services.ids import result_id_for
from resto.domain.value_objects.answer_value import Edges, Measure, Quantity
from resto.domain.value_objects.arm import BASE_ARM, Arm
from resto.domain.value_objects.drafts import (
    ExpertNoteDraft,
    ExpertNoteDrafts,
    RejectedIntervention,
    ScenarioDraft,
)
from resto.domain.value_objects.experiment import Experiment, ExperimentRole
from resto.domain.value_objects.expert_answer import Basis, Evidence, EvidenceKind
from resto.domain.value_objects.intervention import Intervention
from resto.domain.value_objects.question import Intent, Mode, Question
from resto.domain.value_objects.step_record import StepErrorKind, StepStatus, Usage
from resto.domain.value_objects.study_plan import (
    ClarificationRequest,
    DeriveNetworkStep,
    FromStep,
    RerouteDemandStep,
    ReusedExperiment,
)
from tests.unit.application._doubles import FakeRunner
from tests.unit.application._world import (
    BASE_SID,
    BASELINE_PLAN,
    CLOSURE,
    CLOSURE_SID,
    DESCRIBE,
    KPIS,
    NEW_EDGE,
    PROPOSED,
    TREATMENT_PLAN,
    UNKNOWN_LANE,
    WHAT_IF,
    World,
    abstains,
    answers,
    echo_draft,
    failed_kind,
    failed_output,
    ok_output,
    plan,
    run_of,
    tools,
)
from tests.unit.domain._fixtures import (
    DEMAND,
    NET,
    artifact,
    build_step,
    dynamic_intervention,
    run_step,
)

# -- golden paths ---------------------------------------------------------------------------------


def test_gp1_a_zero_step_plan_answers_from_reused_results(tmp_path: Path) -> None:
    world = World(tmp_path, expert=(answers(),))
    sid, ids = world.store_scenario()
    world.coordinator.items.append(
        plan(reused=(ReusedExperiment(sid, BASE_ARM, ExperimentRole.BASELINE, "stored baseline"),))
    )

    study = world.run()

    assert study.status is StudyStatus.COMPLETED
    assert study.report is not None
    assert tools(study) == [
        ("plan", StepStatus.OK),
        ("ask_expert", StepStatus.OK),
        ("compose_report", StepStatus.OK),
    ]
    assert study.phases[0].experiments == (
        Experiment(sid, BASE_ARM, ExperimentRole.BASELINE, "stored baseline", ids, reused=True),
    )
    assert world.runner.calls == [] and world.builder.calls == []
    task = world.expert.calls[0][0]
    assert task.result_ids == ids and task.mode is Mode.FREE and task.network_ids == (NET,)
    assert study.network_ids == (NET,)


def test_gp2_builds_and_runs_the_baseline_with_the_default_seeds(tmp_path: Path) -> None:
    world = World(tmp_path, plans=(BASELINE_PLAN,), expert=(answers(),))

    study = world.run()

    assert study.status is StudyStatus.COMPLETED
    assert [t for t, _ in tools(study)] == [
        "plan",
        "build_scenario",
        "run_simulation",
        "ask_expert",
        "compose_report",
    ]
    (experiment,) = study.phases[0].experiments
    expected = tuple(result_id_for(BASE_SID, s, RunMode.BATCH.value) for s in DEFAULT_SEEDS)
    assert experiment == Experiment(
        BASE_SID, BASE_ARM, ExperimentRole.BASELINE, "arm base", expected
    )
    assert [seed for _, seed, _ in world.runner.calls] == [0, *DEFAULT_SEEDS]  # load check + runs
    assert study.phases[0].steps[2].usage == Usage(simulations=3)
    assert study.phases[0].steps[1].usage == Usage(input_tokens=100)


def test_gp3_counterfactual_free_plans_the_treatment_only_when_the_expert_asks(
    tmp_path: Path,
) -> None:
    world = World(
        tmp_path,
        question=WHAT_IF,
        plans=(BASELINE_PLAN, TREATMENT_PLAN),
        expert=(abstains(PROPOSED), answers()),
    )

    study = world.run()

    assert study.status is StudyStatus.COMPLETED
    assert len(study.phases) == 2
    assert study.phases[1].question == PROPOSED
    assert [e.arm for p in study.phases for e in p.experiments] == [BASE_ARM, "treatment"]
    _, context = world.coordinator.calls[1]
    assert context.phase == 1 and context.network_id == NET
    assert [e.arm for e in context.experiments] == [BASE_ARM]
    first, second = (call[0] for call in world.expert.calls)
    assert first.question == second.question == WHAT_IF.text
    assert (first.mode, second.mode) == (Mode.FREE, Mode.FREE)
    assert len(first.result_ids) == 3 and len(second.result_ids) == 6
    assert not any(r.forced_by_limit for r in study.rounds)


def test_forced_mode_answers_in_one_phase_and_offers_the_predicted_scenario(
    tmp_path: Path,
) -> None:
    world = World(
        tmp_path,
        question=replace(WHAT_IF, mode=Mode.FORCED),
        plans=(BASELINE_PLAN,),
        expert=(answers(),),
    )

    study = world.run()

    assert study.status is StudyStatus.COMPLETED and len(study.phases) == 1
    assert world.expert.calls[0][0].mode is Mode.FORCED
    assert study.rounds[0].forced_by_limit is False
    (task,) = (call[0] for call in world.note_writer.calls)
    assert [(s.scenario_id, s.arm, s.simulated) for s in task.scenarios] == [
        (BASE_SID, BASE_ARM, True),
        (CLOSURE_SID, "treatment", False),
    ]


def test_the_mode_given_by_the_user_overrides_the_parsers(tmp_path: Path) -> None:
    world = World(tmp_path, question=WHAT_IF, plans=(BASELINE_PLAN,), expert=(answers(),))

    study = world.run(mode=Mode.FORCED)

    assert study.question.mode is Mode.FORCED
    assert study.status is StudyStatus.COMPLETED


def test_the_last_round_is_forced_by_the_limit(tmp_path: Path) -> None:
    world = World(
        tmp_path,
        question=WHAT_IF,
        plans=(BASELINE_PLAN, TREATMENT_PLAN),
        expert=(abstains(PROPOSED), answers()),
    )

    study = world.run(max_rounds=2)

    assert [call[0].mode for call in world.expert.calls] == [Mode.FREE, Mode.FORCED]
    assert [r.forced_by_limit for r in study.rounds] == [False, True]
    assert study.status is StudyStatus.COMPLETED


def test_combined_topology_and_intervention_arms_share_one_derivation(tmp_path: Path) -> None:
    question = Question(
        text="does the new J7-J9 edge compensate closing lane 1 of E12?",
        intent=Intent.RUN,
        arms=(
            Arm("edge", topology_changes=(NEW_EDGE,)),
            Arm("edge+closure", topology_changes=(NEW_EDGE,), interventions=(CLOSURE,)),
        ),
    )
    derived, rerouted = FromStep(0), FromStep(1)
    gp11 = plan(
        DeriveNetworkStep(base_network_id=NET, modifications=(NEW_EDGE,)),
        RerouteDemandStep(demand_id=DEMAND, network_id=derived, depends_on=(0,)),
        build_step(),
        run_step(2),
        build_step("edge", network=derived, demand=rerouted, depends_on=(0, 1)),
        run_step(4),
        build_step("edge+closure", (CLOSURE,), network=derived, demand=rerouted, depends_on=(0, 1)),
        run_step(6),
    )
    world = World(tmp_path, question=question, plans=(gp11,), expert=(answers(),))

    study = world.run()

    assert study.status is StudyStatus.COMPLETED
    assert len(world.author.calls) == 1
    assert world.promoted_networks[0].base_network_id == NET
    experiments = study.phases[0].experiments
    assert [e.arm for e in experiments] == [BASE_ARM, "edge", "edge+closure"]
    assert all(len(e.result_ids) == 3 for e in experiments)
    assert world.scenarios.get(experiments[2].scenario_id).network_id == "derived-1"  # type: ignore[union-attr]
    assert study.network_ids == ("derived-1", NET)
    assert world.expert.calls[0][0].network_ids == ("derived-1", NET)


def _derive_plan() -> Any:
    derived, rerouted = FromStep(0), FromStep(1)
    return plan(
        DeriveNetworkStep(base_network_id=NET, modifications=(NEW_EDGE,)),
        RerouteDemandStep(demand_id=DEMAND, network_id=derived, depends_on=(0,)),
        build_step(),
        run_step(2),
        build_step("edge", network=derived, demand=rerouted, depends_on=(0, 1)),
        run_step(4),
    )


def _edge_question() -> Question:
    return Question(
        text="does the new J7-J9 edge relieve E12?",
        intent=Intent.RUN,
        arms=(Arm("edge", topology_changes=(NEW_EDGE,)),),
    )


def test_an_answer_about_an_edge_only_the_derived_network_has_is_accepted(tmp_path: Path) -> None:
    about_new_edge = answers(Edges(edge_ids=("J7J9",), network_id="derived-1"))
    world = World(
        tmp_path, question=_edge_question(), plans=(_derive_plan(),), expert=(about_new_edge,)
    )

    study = world.run()

    assert study.status is StudyStatus.COMPLETED
    assert study.rounds[0].answer.values == (Edges(edge_ids=("J7J9",), network_id="derived-1"),)


def test_the_derived_edge_is_rejected_when_the_answer_names_the_base_network(
    tmp_path: Path,
) -> None:
    on_base = answers(Edges(edge_ids=("J7J9",), network_id=NET))
    world = World(tmp_path, question=_edge_question(), plans=(_derive_plan(),), expert=(on_base,))

    study = world.run()

    assert_failed_at(study, "ask_expert", StepErrorKind.AGENT, skipped=0)


def test_an_answer_naming_a_network_the_study_never_had_is_rejected(tmp_path: Path) -> None:
    stranger = answers(Edges(edge_ids=("E12",), network_id="never-derived"))
    world = World(tmp_path, plans=(BASELINE_PLAN,), expert=(stranger,))

    study = world.run()

    assert_failed_at(study, "ask_expert", StepErrorKind.AGENT, skipped=0)


def test_a_proposed_experiment_may_name_the_derived_network_but_not_a_stranger(
    tmp_path: Path,
) -> None:
    on_derived = abstains(replace(PROPOSED, network_ref="derived-1"))
    world = World(
        tmp_path,
        question=_edge_question(),
        plans=(_derive_plan(), TREATMENT_PLAN),
        expert=(on_derived, answers()),
    )
    accepted = world.run()
    assert accepted.status is StudyStatus.COMPLETED and len(accepted.phases) == 2

    on_stranger = abstains(replace(PROPOSED, network_ref="never-derived"))
    rejecting = World(
        tmp_path / "second",
        question=_edge_question(),
        plans=(_derive_plan(),),
        expert=(on_stranger,),
    )
    assert_failed_at(rejecting.run(), "ask_expert", StepErrorKind.AGENT, skipped=0)


def test_the_scope_of_a_later_round_includes_a_network_derived_in_an_earlier_phase(
    tmp_path: Path,
) -> None:
    about_new_edge = answers(Edges(edge_ids=("J7J9",), network_id="derived-1"))
    world = World(
        tmp_path,
        question=_edge_question(),
        plans=(_derive_plan(), TREATMENT_PLAN),
        expert=(abstains(PROPOSED), about_new_edge),
    )

    study = world.run()

    assert study.status is StudyStatus.COMPLETED
    first, second = (call[0] for call in world.expert.calls)
    assert set(first.network_ids) == set(second.network_ids) == {NET, "derived-1"}


def test_an_ambiguous_question_awaits_the_user_without_planning(tmp_path: Path) -> None:
    world = World(tmp_path, question=replace(DESCRIBE, ambiguities=("which peak?",)))

    study = world.run()

    assert study.status is StudyStatus.AWAITING_USER
    assert world.coordinator.calls == []
    assert len(world.studies.states) == 1


def test_a_coordinator_clarification_in_phase_0_awaits_the_user(tmp_path: Path) -> None:
    clarification = ClarificationRequest("two networks are labelled Gran Via", ("gv-1", "gv-2"))
    world = World(tmp_path, plans=(run_of(clarification),))

    study = world.run()

    assert study.status is StudyStatus.AWAITING_USER
    assert study.phases[0].clarification == clarification
    assert study.phases[0].steps == ()


def test_a_coordinator_clarification_in_a_later_phase_fails_the_study(tmp_path: Path) -> None:
    world = World(
        tmp_path,
        question=WHAT_IF,
        plans=(BASELINE_PLAN, run_of(ClarificationRequest("which lane?"))),
        expert=(abstains(PROPOSED),),
    )

    study = world.run()

    assert study.status is StudyStatus.FAILED
    assert tools(study, 1) == [("plan", StepStatus.FAILED)]
    assert failed_kind(study) is StepErrorKind.AGENT
    assert study.phases[1].plan is None


@pytest.mark.parametrize(
    "parsed",
    [ConnectionError("down"), run_of(None, StopReason.BUDGET)],
    ids=["exception", "budget"],
)
def test_no_study_exists_when_the_parser_fails(tmp_path: Path, parsed: Any) -> None:
    world = World(tmp_path, question=parsed)

    with pytest.raises(ParserFailed):
        world.run()

    assert world.studies.states == []


# -- failures, one per kind -----------------------------------------------------------------------


def assert_failed_at(study: Study, tool: str, kind: StepErrorKind, skipped: int) -> None:
    steps = study.phases[-1].steps
    failed = next(i for i, s in enumerate(steps) if s.status is StepStatus.FAILED)
    assert study.status is StudyStatus.FAILED
    assert steps[failed].tool == tool
    assert failed_kind(study) is kind
    assert [s.status for s in steps[failed + 1 :]] == [StepStatus.SKIPPED] * skipped
    assert study.report is None


def run_treatment(tmp_path: Path, interventions: tuple[Intervention, ...], **world: Any) -> Study:
    question = Question(text="close it", intent=Intent.RUN, interventions=interventions)
    two_arms = plan(
        build_step(),
        run_step(0),
        build_step("treatment", interventions, role=ExperimentRole.TREATMENT),
        run_step(2),
    )
    return World(tmp_path, question=question, plans=(two_arms,), **world).run()


def test_an_unknown_edge_is_the_users_input(tmp_path: Path) -> None:
    study = run_treatment(tmp_path, (UNKNOWN_LANE,))

    assert_failed_at(study, "build_scenario", StepErrorKind.USER_INPUT, skipped=1)
    assert [e.arm for e in study.phases[0].experiments] == [BASE_ARM]


def test_an_intervention_the_builder_rejects_is_the_users_input(tmp_path: Path) -> None:
    rejected = ScenarioDraft(
        interventions=(),
        mechanisms=(),
        sumocfg=artifact("s.sumocfg", "c1", "sumocfg"),
        rationale="cannot close a lane that is the only one",
        rejected=(RejectedIntervention(CLOSURE, "E12 has a single lane"),),
    )
    study = run_treatment(tmp_path, (CLOSURE,), builder=(echo_draft, run_of(rejected)))

    assert_failed_at(study, "build_scenario", StepErrorKind.USER_INPUT, skipped=1)
    error = study.phases[0].failed_step.error  # type: ignore[union-attr]
    assert error is not None and any("single lane" in d for d in error.details)


def test_an_agent_out_of_its_budget_is_budget(tmp_path: Path) -> None:
    out_of_budget = run_of(None, StopReason.BUDGET)
    study = run_treatment(tmp_path, (CLOSURE,), builder=(echo_draft, out_of_budget))

    assert_failed_at(study, "build_scenario", StepErrorKind.BUDGET, skipped=1)


def test_the_study_simulation_budget_is_checked_before_running(tmp_path: Path) -> None:
    study = run_treatment(tmp_path, (CLOSURE,), budget=StudyBudget(max_simulations=4))

    assert_failed_at(study, "run_simulation", StepErrorKind.BUDGET, skipped=0)
    assert len(study.phases[0].experiments[0].result_ids) == 3


def test_the_parsers_tokens_count_against_the_study_budget(tmp_path: Path) -> None:
    world = World(tmp_path, plans=(BASELINE_PLAN,), budget=StudyBudget(max_tokens=50))

    study = world.run()

    assert_failed_at(study, "plan", StepErrorKind.BUDGET, skipped=0)
    assert world.coordinator.calls == []


def test_a_failed_sumo_run_is_infrastructure_with_its_logs(tmp_path: Path) -> None:
    runner = FakeRunner([ok_output(), failed_output()], default=ok_output())
    world = World(tmp_path, plans=(BASELINE_PLAN,), runner=runner)

    study = world.run()

    assert_failed_at(study, "run_simulation", StepErrorKind.INFRASTRUCTURE, skipped=0)
    error = study.phases[0].failed_step.error  # type: ignore[union-attr]
    assert error is not None and "Error: SUMO crashed" in error.details
    assert any(d.startswith("logs: ") for d in error.details)


def test_an_exception_from_an_agent_is_infrastructure(tmp_path: Path) -> None:
    study = run_treatment(tmp_path, (CLOSURE,), builder=(echo_draft, ConnectionError("503")))

    assert_failed_at(study, "build_scenario", StepErrorKind.INFRASTRUCTURE, skipped=1)


def test_an_online_scenario_is_infrastructure_until_e2_5(tmp_path: Path) -> None:
    study = run_treatment(tmp_path, (dynamic_intervention(),))

    assert_failed_at(study, "run_simulation", StepErrorKind.INFRASTRUCTURE, skipped=0)


def test_an_expert_round_on_a_network_that_is_not_stored_is_infrastructure(tmp_path: Path) -> None:
    world = World(tmp_path, plans=(BASELINE_PLAN,))
    loader = world.deps.network_query_loader
    gone = False

    class VanishingLoader:
        def load(self, network_id: str) -> Any:
            if gone:
                raise NetworkNotStored(f"network {network_id!r} is not stored")
            return loader.load(network_id)

    def answer_after_the_network_vanishes(task: Any, ledger: Any) -> Any:
        nonlocal gone
        gone = True
        return answers()(task, ledger)

    world.deps = replace(world.deps, network_query_loader=VanishingLoader())
    world.expert.items.append(answer_after_the_network_vanishes)

    study = world.run()

    assert_failed_at(study, "ask_expert", StepErrorKind.INFRASTRUCTURE, skipped=0)
    error = study.phases[0].failed_step.error  # type: ignore[union-attr]
    assert error is not None and "is not stored" in error.message
    assert study.phases[0].round is None


def test_an_expert_round_loads_the_study_network_once(tmp_path: Path) -> None:
    world = World(tmp_path, plans=(BASELINE_PLAN,), expert=(answers(),))

    world.run()

    assert len(world.query_loads) == 1


def test_a_rejected_expert_answer_is_the_agents(tmp_path: Path) -> None:
    world = World(
        tmp_path,
        plans=(BASELINE_PLAN,),
        expert=(answers(Edges(edge_ids=("E99",), network_id=NET)),),
    )

    study = world.run()

    assert_failed_at(study, "ask_expert", StepErrorKind.AGENT, skipped=0)
    assert study.phases[0].round is None


def test_a_failed_report_fails_the_study(tmp_path: Path) -> None:
    world = World(
        tmp_path,
        plans=(BASELINE_PLAN,),
        expert=(answers(),),
        composer=(run_of(None, StopReason.BUDGET),),
    )

    study = world.run()

    assert_failed_at(study, "compose_report", StepErrorKind.BUDGET, skipped=0)
    assert study.phases[0].round is not None


def test_an_invalid_plan_is_the_agents(tmp_path: Path) -> None:
    """The wiring only: which problems a plan has is `plan_problems`' (test_plan_validation)."""
    bad_plan = plan(build_step(), run_step(0), network="nope")
    world = World(tmp_path, plans=(bad_plan,))

    study = world.run()

    assert_failed_at(study, "plan", StepErrorKind.AGENT, skipped=2)
    assert study.phases[0].plan == bad_plan.output
    assert world.builder.calls == []
    error = study.phases[0].failed_step.error  # type: ignore[union-attr]
    assert error is not None
    assert error.message == "the plan of phase 0 is invalid"
    assert error.details == (
        "unknown network 'nope'",
        "step 0: its arm keeps the topology, but runs on another network",
    )


# -- dedup and note verification ------------------------------------------------------------------


def unverified_note(scenario_id: str, value: float) -> ExpertNote:
    return ExpertNote(
        note_id=f"n-{scenario_id[:6]}",
        network_id=NET,
        study_id="an-earlier-study",
        text="mean delay at peak",
        provenance=Provenance.OPINION,
        basis=Basis.EXTRAPOLATED,
        scenario_id=scenario_id,
        values=(Quantity(measure=Measure.MEAN_DELAY, value=value),),
    )


def test_stored_results_are_not_rerun_and_verify_no_note(tmp_path: Path) -> None:
    world = World(tmp_path, plans=(BASELINE_PLAN,), expert=(answers(),))
    world.store_scenario()
    note = unverified_note(BASE_SID, KPIS.mean_delay)
    world.notes.store(note)

    study = world.run()

    assert study.status is StudyStatus.COMPLETED
    assert world.builder.calls == [] and world.runner.calls == []
    assert study.phases[0].steps[1].usage == Usage()
    assert study.phases[0].steps[2].usage == Usage(simulations=0)
    ((hit, _),) = world.notes.search("", NET, {"scenario_id": BASE_SID})
    assert hit.status is NoteStatus.UNVERIFIED


def test_a_new_result_settles_the_unverified_notes_of_its_scenario(tmp_path: Path) -> None:
    world = World(tmp_path, plans=(BASELINE_PLAN,), expert=(answers(),))
    world.notes.store(unverified_note(BASE_SID, KPIS.mean_delay))

    world.run()

    ((hit, _),) = world.notes.search("", NET, {"scenario_id": BASE_SID})
    assert hit.status is NoteStatus.CONFIRMED
    assert any(isinstance(e, NoteStatusChanged) for e in world.tracer.events)


def test_only_missing_seeds_are_run(tmp_path: Path) -> None:
    world = World(tmp_path, plans=(BASELINE_PLAN,), expert=(answers(),))
    world.store_scenario(seeds=(1,))

    study = world.run()

    assert [seed for _, seed, _ in world.runner.calls] == [2, 3]
    assert study.phases[0].steps[2].usage == Usage(simulations=2)
    assert len(study.phases[0].experiments[0].result_ids) == 3


# -- notes ----------------------------------------------------------------------------------------


def test_notes_are_written_after_the_final_round_with_its_ledger(tmp_path: Path) -> None:
    draft = ExpertNoteDraft(
        text="the peak baseline has a mean delay of 24 s",
        basis=Basis.OBSERVED,
        evidence=(Evidence(kind=EvidenceKind.QUERY, ref="q1"),),
        scenario_ref=BASE_SID,
    )
    world = World(
        tmp_path,
        plans=(BASELINE_PLAN,),
        expert=(answers(),),
        note_writer=(run_of(ExpertNoteDrafts(notes=(draft,))),),
    )

    study = world.run()

    assert study.status is StudyStatus.COMPLETED
    (note_id,) = study.note_ids
    ((hit, _),) = world.notes.search("", NET, {"scenario_id": BASE_SID})
    assert hit.note_id == note_id and hit.provenance is Provenance.SIMULATION
    assert hit.study_id == study.study_id


def test_a_failing_note_writer_is_traced_and_the_study_completes(tmp_path: Path) -> None:
    world = World(
        tmp_path,
        plans=(BASELINE_PLAN,),
        expert=(answers(),),
        note_writer=(run_of(None, StopReason.BUDGET),),
    )

    study = world.run()

    assert study.status is StudyStatus.COMPLETED
    assert study.note_ids == ()
    assert any(isinstance(e, NoteWriterFailed) for e in world.tracer.events)
    assert "note_writer" not in [s.tool for s in study.phases[0].steps]


def test_the_model_calls_of_a_study_sum_to_its_steps_and_the_parsers_tokens(
    tmp_path: Path,
) -> None:
    world = World(tmp_path, plans=(BASELINE_PLAN,), expert=(answers(),))

    study = world.run()

    calls = [e for e in world.tracer.events if isinstance(e, ModelCall)]
    steps = [s for p in study.phases for s in p.steps]
    assert study.status is StudyStatus.COMPLETED
    assert sum(c.usage.input_tokens for c in calls) == 50 + sum(s.usage.input_tokens for s in steps)
    agent_steps = [s for s in steps if s.tool != "run_simulation"]
    assert len(calls) == 1 + len(agent_steps) + 1  # the Parser, the steps, the note writer


def test_a_failed_agent_call_still_emits_its_model_call(tmp_path: Path) -> None:
    world = World(
        tmp_path,
        plans=(BASELINE_PLAN,),
        expert=(run_of(None, StopReason.BUDGET, tokens=7),),
    )

    study = world.run()

    calls = [e for e in world.tracer.events if isinstance(e, ModelCall)]
    assert study.status is StudyStatus.FAILED
    assert calls[-1].usage.input_tokens == 7


def _flow(world: World) -> list[object]:
    """The phase, plan, step, round and report events of a trace, as comparable tuples."""
    flow: list[object] = []
    for e in world.tracer.events:
        if isinstance(e, PhaseStarted):
            flow.append(("phase", e.phase))
        elif isinstance(e, PlanMade):
            flow.append(("plan", e.phase))
        elif isinstance(e, StepTraced):
            flow.append(("step", e.phase, e.tool))
        elif isinstance(e, ExpertRoundHeld):
            flow.append(("round", e.phase, e.round))
        elif isinstance(e, ReportComposed):
            flow.append("report")
    return flow


def test_a_multi_phase_study_traces_phases_plans_steps_rounds_and_the_report(
    tmp_path: Path,
) -> None:
    world = World(
        tmp_path,
        question=WHAT_IF,
        plans=(BASELINE_PLAN, TREATMENT_PLAN),
        expert=(abstains(PROPOSED), answers()),
    )

    study = world.run()

    flow = _flow(world)
    assert study.status is StudyStatus.COMPLETED
    assert flow[:3] == [("phase", 0), ("plan", 0), ("step", 0, "build_scenario")]
    assert flow.index(("round", 0, 1)) < flow.index(("phase", 1)) < flow.index(("plan", 1))
    assert [f for f in flow if isinstance(f, tuple) and f[0] == "round"] == [
        ("round", 0, 1),
        ("round", 1, 2),
    ]
    assert flow[-3:] == [("round", 1, 2), ("step", 1, "compose_report"), "report"]
    assert flow[-1] == "report"
    assert flow.count("report") == 1
    plan_event = next(e for e in world.tracer.events if isinstance(e, PlanMade))
    assert plan_event.plan == study.phases[0].plan
    assert isinstance(world.tracer.events[0], StudyCreated)


def test_a_clarification_in_phase_0_traces_no_plan(tmp_path: Path) -> None:
    world = World(tmp_path, plans=(run_of(ClarificationRequest("which network?")),))

    world.run()

    assert _flow(world) == [("phase", 0)]


def test_a_failed_plan_traces_no_plan(tmp_path: Path) -> None:
    world = World(tmp_path, plans=(plan(build_step(), run_step(0), network="nope"),))

    world.run()

    assert not any(isinstance(e, PlanMade) for e in world.tracer.events)


def test_a_failed_report_traces_no_report(tmp_path: Path) -> None:
    world = World(
        tmp_path,
        plans=(BASELINE_PLAN,),
        expert=(answers(),),
        composer=(run_of(None, StopReason.BUDGET),),
    )

    world.run()

    flow = _flow(world)
    assert ("round", 0, 1) in flow
    assert "report" not in flow


# -- persistence and helpers ----------------------------------------------------------------------


def test_the_study_is_persisted_after_every_step(tmp_path: Path) -> None:
    world = World(tmp_path, plans=(BASELINE_PLAN,), expert=(answers(),))

    study = world.run()

    states = world.studies.states
    assert {s.study_id for s in states} == {study.study_id}
    assert states[-1] == study == world.studies.get(study.study_id)
    step_counts = [len(s.phases[0].steps) for s in states]
    assert step_counts == sorted(step_counts)
    assert set(range(len(study.phases[0].steps) + 1)) <= set(step_counts)
