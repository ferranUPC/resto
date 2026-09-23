"""`run_study` (E5.10; ADR-0023, ADR-0025, ADR-0026, ADR-0027) with scripted agent ports, fake
promotions, in-memory repositories and a fake SUMO runner: golden-path shapes, one failure per
`StepError.kind`, dedup, notes, and a Study persisted after every step. No network."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from resto.adapters.persistence.memory import (
    InMemoryDemandRepository,
    InMemoryNetworkRepository,
    InMemoryNoteRepository,
    InMemoryResultRepository,
    InMemoryScenarioRepository,
    InMemoryStudyRepository,
)
from resto.application.ports.agents.coordinator import PlanningContext
from resto.application.ports.llm import AgentRun, StopReason
from resto.application.ports.sumo import RunOutput
from resto.application.tools.expert import EvidenceLedger
from resto.application.use_cases.run_study import (
    ParserFailed,
    StudyAgents,
    StudyBudget,
    StudyDeps,
    StudyPromotions,
    mode_for,
    needed_arms,
    run_study,
)
from resto.domain.constants import DEFAULT_SEEDS
from resto.domain.entities.demand import Demand
from resto.domain.entities.expert_note import ExpertNote, NoteStatus, Provenance
from resto.domain.entities.network import Network
from resto.domain.entities.scenario import Scenario
from resto.domain.entities.simulation_result import RunMode, RunStatus, SimulationResult
from resto.domain.entities.study import Study, StudyStatus
from resto.domain.services.ids import result_id_for, scenario_id_for
from resto.domain.value_objects.answer_value import Edges, Measure, Quantity
from resto.domain.value_objects.arm import BASE_ARM, Arm
from resto.domain.value_objects.demand_source import HistoricalDbSource
from resto.domain.value_objects.demand_spec import DemandProfile
from resto.domain.value_objects.drafts import (
    ExpertNoteDraft,
    ExpertNoteDrafts,
    RejectedIntervention,
    ScenarioDraft,
)
from resto.domain.value_objects.experiment import Experiment, ExperimentRole
from resto.domain.value_objects.expert_answer import Basis, Evidence, EvidenceKind, ExpertAnswer
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import LaneTarget
from resto.domain.value_objects.kpis import Kpis
from resto.domain.value_objects.mechanism import ScriptMechanism, StaticFileMechanism
from resto.domain.value_objects.network_recipe import NetworkRecipe
from resto.domain.value_objects.question import Intent, Mode, Question
from resto.domain.value_objects.report import Report
from resto.domain.value_objects.step_record import StepErrorKind, StepStatus, Usage
from resto.domain.value_objects.study_plan import (
    BuildScenarioStep,
    ClarificationRequest,
    DeriveNetworkStep,
    FromStep,
    GenerateDemandStep,
    RerouteDemandStep,
    ReusedExperiment,
    RunSimulationStep,
    StudyPlan,
)
from resto.domain.value_objects.tasks import ExpertTask, NoteTask
from resto.domain.value_objects.time_window import TimeWindow
from resto.domain.value_objects.topology_modification import AddEdge
from tests.unit.application.use_cases._doubles import FakeRunner, StubNetworkQuery
from tests.unit.domain._fixtures import (
    artifact,
    demand_draft,
    dynamic_intervention,
    good_sanity,
    network_draft,
    runnable_script,
    static_intervention,
)
from tests.unit.domain._samples import demand as sample_demand
from tests.unit.domain._samples import network as sample_network

NET = "abc123"
DEMAND = "t1"
CLOSURE = static_intervention()  # lane 1 of E12, fixed window
UNKNOWN_LANE = Intervention(
    type=InterventionType.LANE_CLOSURE,
    target=LaneTarget(edge_id="E99", lane_index=0),
    window=TimeWindow(7 * 3600, 10 * 3600),
)
NEW_EDGE = AddEdge("J7", "J9", lanes=2, speed=13.9, edge_id="J7J9")
QUERY = StubNetworkQuery(edges={"E12"}, lanes={("E12", 1)})
REPORT = Report(summary="done", mode=Mode.FREE, basis=Basis.OBSERVED)
KPIS = Kpis(mean_delay=24.4, mean_travel_time=85.4, teleports=0, departed=50, arrived=43)

DESCRIBE = Question(text="how congested is the peak?", intent=Intent.DESCRIBE)
WHAT_IF = Question(
    text="what if we close lane 1 of E12?", intent=Intent.COUNTERFACTUAL, interventions=(CLOSURE,)
)
PROPOSED = Question(text="close lane 1 of E12", intent=Intent.RUN, interventions=(CLOSURE,))

BASE_SID = scenario_id_for(NET, DEMAND, (), frozenset())
CLOSURE_SID = scenario_id_for(NET, DEMAND, (CLOSURE,), frozenset())


# -- doubles ------------------------------------------------------------------------------------


def run_of(output: Any, stop: StopReason = StopReason.OUTPUT, tokens: int = 0) -> AgentRun[Any]:
    usage = Usage(input_tokens=tokens)
    return AgentRun(output=output, tool_calls=(), usage=usage, stop_reason=stop)


class Scripted:
    """Answers each call with the next scripted item: an `AgentRun`, an exception to raise, or a
    callable given the call's arguments. `default` answers once the script runs out."""

    def __init__(self, *items: Any, default: Callable[..., Any] | None = None) -> None:
        self.items = list(items)
        self.default = default
        self.calls: list[tuple[Any, ...]] = []

    def _next(self, *args: Any) -> Any:
        self.calls.append(args)
        if not self.items:
            if self.default is None:
                raise AssertionError(f"unexpected call {type(self).__name__}{args}")
            return self.default(*args)
        item = self.items.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item(*args) if callable(item) else item


class FakeParser(Scripted):
    def parse(self, text: str) -> AgentRun[Question]:
        return self._next(text)  # type: ignore[no-any-return]


class FakeCoordinator(Scripted):
    def plan(self, question: Question, context: PlanningContext) -> AgentRun[Any]:
        return self._next(question, context)  # type: ignore[no-any-return]


class FakeAuthor(Scripted):
    def author(self, task: Any) -> AgentRun[Any]:
        return self._next(task)  # type: ignore[no-any-return]


class FakeGenerator(Scripted):
    def generate(self, task: Any) -> AgentRun[Any]:
        return self._next(task)  # type: ignore[no-any-return]


class FakeBuilder(Scripted):
    def build(self, task: Any) -> AgentRun[ScenarioDraft]:
        return self._next(task)  # type: ignore[no-any-return]


class FakeExpert(Scripted):
    def answer(self, task: ExpertTask, ledger: EvidenceLedger) -> AgentRun[ExpertAnswer]:
        return self._next(task, ledger)  # type: ignore[no-any-return]


class FakeNoteWriter(Scripted):
    def write(self, task: NoteTask) -> AgentRun[ExpertNoteDrafts]:
        return self._next(task)  # type: ignore[no-any-return]


class FakeComposer(Scripted):
    def compose(self, study: Study) -> AgentRun[Report]:
        return self._next(study)  # type: ignore[no-any-return]


class RecordingStudies(InMemoryStudyRepository):
    def __init__(self) -> None:
        super().__init__()
        self.states: list[Study] = []

    def store(self, study: Study) -> None:
        self.states.append(study)
        super().store(study)


class RecordingTracer:
    def __init__(self) -> None:
        self.events: list[tuple[str, Mapping[str, Any]]] = []

    def emit(self, study_id: str, event: str, payload: Mapping[str, Any]) -> None:
        self.events.append((event, payload))


def echo_draft(task: Any) -> AgentRun[ScenarioDraft]:
    """A Builder that implements exactly what it was asked, with a static file each."""
    mechanisms = tuple(
        ScriptMechanism()
        if i.condition is not None
        else StaticFileMechanism(file_kind="rerouter", path=Path(f"{n}.add.xml"))
        for n, i in enumerate(task.interventions)
    )
    script = runnable_script() if any(i.condition for i in task.interventions) else None
    draft = ScenarioDraft(
        interventions=task.interventions,
        mechanisms=mechanisms,
        sumocfg=artifact("s.sumocfg", "c1", "sumocfg"),
        rationale="implemented as asked",
        script=script,
    )
    return run_of(draft, tokens=100)


def answers(*values: Any) -> Callable[[ExpertTask, EvidenceLedger], AgentRun[ExpertAnswer]]:
    def answer(task: ExpertTask, ledger: EvidenceLedger) -> AgentRun[ExpertAnswer]:
        ref = ledger.record("compare_kpis", {"result_ids": list(task.result_ids)}, {"ok": True})
        return run_of(
            ExpertAnswer(
                answer="mean delay is about 24 s",
                basis=Basis.OBSERVED,
                confidence=0.8,
                evidence=(Evidence(kind=EvidenceKind.QUERY, ref=ref),),
                values=values or (Quantity(measure=Measure.MEAN_DELAY, value=24.4),),
            ),
            tokens=200,
        )

    return answer


def abstains(proposed: Question) -> AgentRun[ExpertAnswer]:
    return run_of(
        ExpertAnswer(
            answer="the closure has never been simulated",
            basis=Basis.INFERRED,
            confidence=0.2,
            needs_simulation=True,
            proposed_experiment=proposed,
        )
    )


def ok_output() -> RunOutput:
    return RunOutput(
        ok=True,
        error=None,
        artifacts=(artifact("run.sumocfg", "cfg1", "sumocfg"), artifact("e.xml", "ed", "edgedata")),
        wall_clock_s=0.5,
        kpis=KPIS,
    )


def failed_output() -> RunOutput:
    return RunOutput(ok=False, error="Error: SUMO crashed", artifacts=(), wall_clock_s=0.1)


def derived_network(task: Any, run: Any) -> Network:
    return Network(
        network_id="derived-1",
        net_xml=artifact("derived.net.xml", "derived-1", "net"),
        recipe=NetworkRecipe(base_network_id=task.base_network_id, plain_edits=task.modifications),
        sanity_report=good_sanity(),
        derived_from=task.base_network_id,
    )


def _report(study: Study, run: AgentRun[Report]) -> Report:
    assert run.output is not None
    return run.output


class World:
    """Everything `run_study` needs, with the scripted agents reachable for assertions."""

    def __init__(
        self,
        tmp_path: Path,
        *,
        question: Question | AgentRun[Question] | BaseException = DESCRIBE,
        plans: tuple[Any, ...] = (),
        expert: tuple[Any, ...] = (),
        builder: tuple[Any, ...] = (),
        note_writer: tuple[Any, ...] = (),
        composer: tuple[Any, ...] = (),
        runner: FakeRunner | None = None,
        budget: StudyBudget | None = None,
        has_historical_demand: bool = False,
    ) -> None:
        parsed = question if not isinstance(question, Question) else run_of(question, tokens=50)
        self.parser = FakeParser(parsed)
        self.coordinator = FakeCoordinator(*plans)
        self.author = FakeAuthor(default=lambda task: run_of(network_draft(), tokens=100))
        self.generator = FakeGenerator(default=lambda task: run_of(demand_draft(), tokens=100))
        self.builder = FakeBuilder(*builder, default=echo_draft)
        self.expert = FakeExpert(*expert)
        self.note_writer = FakeNoteWriter(
            *note_writer, default=lambda task: run_of(ExpertNoteDrafts())
        )
        self.composer = FakeComposer(
            *composer,
            default=lambda study: run_of(REPORT),
        )
        self.networks = InMemoryNetworkRepository()
        self.networks.store(sample_network())
        self.demands = InMemoryDemandRepository()
        self.demands.store(sample_demand())
        self.scenarios = InMemoryScenarioRepository()
        self.results = InMemoryResultRepository()
        self.notes = InMemoryNoteRepository()
        self.studies = RecordingStudies()
        self.runner = runner or FakeRunner([], default=ok_output())
        self.tracer = RecordingTracer()
        self.promoted_networks: list[Any] = []
        self.deps = StudyDeps(
            agents=StudyAgents(
                parser=self.parser,
                coordinator=self.coordinator,
                network_author=self.author,
                demand_generator=self.generator,
                scenario_builder=self.builder,
                expert=self.expert,
                note_writer=self.note_writer,
                composer=self.composer,
            ),
            promotions=StudyPromotions(
                network=self._promote_network,
                demand=lambda task, run: sample_demand(),
                reroute=self._reroute,
                report=_report,
            ),
            networks=self.networks,
            demands=self.demands,
            scenarios=self.scenarios,
            results=self.results,
            notes=self.notes,
            studies=self.studies,
            runner=self.runner,
            network_query_factory=lambda path: QUERY,
            tracer=self.tracer,
            out_dir=tmp_path,
            has_historical_demand=has_historical_demand,
            budget=budget or StudyBudget(),
        )

    def _promote_network(self, task: Any, run: Any) -> Network:
        network = derived_network(task, run)
        self.promoted_networks.append(task)
        self.networks.store(network)
        return network

    def _reroute(self, demand: Demand, network: Network) -> Demand:
        rerouted = Demand(
            demand_id=f"{demand.demand_id}-on-{network.network_id}",
            network_id=network.network_id,
            spec=demand.spec,
            trips=artifact("trips2.xml", f"{demand.demand_id}-on-{network.network_id}", "trips"),
            routes=artifact("routes2.xml", "r2", "routes"),
            derived_from=demand.demand_id,
        )
        self.demands.store(rerouted)
        return rerouted

    def run(self, **kwargs: Any) -> Study:
        return run_study("the user's text", self.deps, **kwargs)

    def store_scenario(
        self, interventions: tuple[Intervention, ...] = (), seeds: tuple[int, ...] = DEFAULT_SEEDS
    ) -> tuple[str, tuple[str, ...]]:
        """A stored scenario on the study network with ok results for `seeds`."""
        sid = scenario_id_for(NET, DEMAND, interventions, frozenset())
        self.scenarios.store(
            Scenario(
                scenario_id=sid,
                network_id=NET,
                demand_id=DEMAND,
                interventions=interventions,
                mechanisms=tuple(
                    StaticFileMechanism(file_kind="rerouter", path=Path(f"{n}.add.xml"))
                    for n, _ in enumerate(interventions)
                ),
                sumocfg=artifact("stored.sumocfg", "c0", "sumocfg"),
                content_hash="c0",
            )
        )
        ids = []
        for seed in seeds:
            rid = result_id_for(sid, seed, RunMode.BATCH.value)
            self.results.store(
                SimulationResult(
                    result_id=rid,
                    scenario_id=sid,
                    seed=seed,
                    mode=RunMode.BATCH,
                    status=RunStatus.OK,
                    content_hash="h",
                    kpis=KPIS,
                )
            )
            ids.append(rid)
        return sid, tuple(ids)


# -- plans ----------------------------------------------------------------------------------------


def build(
    arm: str = BASE_ARM,
    interventions: tuple[Intervention, ...] = (),
    network: str | FromStep = NET,
    demand: str | FromStep = DEMAND,
    depends_on: tuple[int, ...] = (),
    role: ExperimentRole = ExperimentRole.BASELINE,
) -> BuildScenarioStep:
    return BuildScenarioStep(
        network_id=network,
        demand_id=demand,
        arm=arm,
        role=role,
        purpose=f"arm {arm}",
        interventions=interventions,
        depends_on=depends_on,
    )


def runs(step: int, seeds: tuple[int, ...] | None = None) -> RunSimulationStep:
    return RunSimulationStep(scenario_id=FromStep(step), seeds=seeds, depends_on=(step,))


def plan(*steps: Any, reused: tuple[ReusedExperiment, ...] = (), network: Any = NET) -> Any:
    return run_of(StudyPlan(network_id=network, rationale="as needed", steps=steps, reused=reused))


BASELINE_PLAN = plan(build(), runs(0))
TREATMENT_PLAN = plan(build("treatment", (CLOSURE,), role=ExperimentRole.TREATMENT), runs(0))


def tools(study: Study, phase: int = 0) -> list[tuple[str, StepStatus]]:
    return [(s.tool, s.status) for s in study.phases[phase].steps]


def failed_kind(study: Study) -> StepErrorKind:
    step = study.phases[-1].failed_step
    assert step is not None and step.error is not None
    return step.error.kind


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
    assert task.result_ids == ids and task.mode is Mode.FREE and task.network_id == NET
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
        build(),
        runs(2),
        build("edge", network=derived, demand=rerouted, depends_on=(0, 1)),
        runs(4),
        build("edge+closure", (CLOSURE,), network=derived, demand=rerouted, depends_on=(0, 1)),
        runs(6),
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
    # TODO(E5.3): the Expert still sees only the study network
    assert world.expert.calls[0][0].network_id == NET


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
        build(), runs(0), build("treatment", interventions, role=ExperimentRole.TREATMENT), runs(2)
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


def test_a_rejected_expert_answer_is_the_agents(tmp_path: Path) -> None:
    world = World(tmp_path, plans=(BASELINE_PLAN,), expert=(answers(Edges(edge_ids=("E99",))),))

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


def _historical_plan() -> Any:
    demand = GenerateDemandStep(
        network_id=NET, profile=DemandProfile.PEAK, seed=1, sources=(HistoricalDbSource(),)
    )
    return plan(demand, build(demand=FromStep(0), depends_on=(0,)), runs(1))


@pytest.mark.parametrize(
    ("question", "bad_plan"),
    [
        (DESCRIBE, plan(build(), runs(0), network="nope")),
        (DESCRIBE, plan(build(demand="nope"), runs(0))),
        (DESCRIBE, plan()),
        (WHAT_IF, plan(build(), runs(0), build("treatment", (CLOSURE,)), runs(2))),
        (DESCRIBE, plan(build())),
        (DESCRIBE, plan(build(interventions=(CLOSURE,)), runs(0))),
        (DESCRIBE, _historical_plan()),
    ],
    ids=[
        "unknown-network",
        "unknown-demand",
        "missing-arm",
        "extra-arm",
        "built-never-run",
        "wrong-interventions",
        "historical-without-capability",
    ],
)
def test_an_invalid_plan_is_the_agents(tmp_path: Path, question: Question, bad_plan: Any) -> None:
    world = World(tmp_path, question=question, plans=(bad_plan,))

    study = world.run()

    steps = bad_plan.output.steps
    assert_failed_at(study, "plan", StepErrorKind.AGENT, skipped=len(steps))
    assert study.phases[0].plan == bad_plan.output
    assert world.builder.calls == []


def test_a_run_of_a_stored_scenario_id_is_rejected(tmp_path: Path) -> None:
    world = World(tmp_path)
    sid, _ = world.store_scenario()
    bad = plan(RunSimulationStep(scenario_id=sid))
    world.coordinator.items.append(bad)

    study = world.run()

    assert_failed_at(study, "plan", StepErrorKind.AGENT, skipped=1)


def test_an_arm_realised_in_an_earlier_phase_is_not_planned_again(tmp_path: Path) -> None:
    again = plan(build(), runs(0), build("treatment", (CLOSURE,)), runs(2))
    world = World(
        tmp_path,
        question=WHAT_IF,
        plans=(BASELINE_PLAN, again),
        expert=(abstains(PROPOSED),),
    )

    study = world.run()

    assert_failed_at(study, "plan", StepErrorKind.AGENT, skipped=4)
    error = study.phases[1].failed_step.error  # type: ignore[union-attr]
    assert error is not None
    assert "arm 'base' was already realised in an earlier phase" in error.details


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
    (hit, _), = world.notes.search("", NET, {"scenario_id": BASE_SID})
    assert hit.status is NoteStatus.UNVERIFIED


def test_a_new_result_settles_the_unverified_notes_of_its_scenario(tmp_path: Path) -> None:
    world = World(tmp_path, plans=(BASELINE_PLAN,), expert=(answers(),))
    world.notes.store(unverified_note(BASE_SID, KPIS.mean_delay))

    world.run()

    (hit, _), = world.notes.search("", NET, {"scenario_id": BASE_SID})
    assert hit.status is NoteStatus.CONFIRMED
    assert any(event == "note_status" for event, _ in world.tracer.events)


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
    (hit, _), = world.notes.search("", NET, {"scenario_id": BASE_SID})
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
    assert any(event == "note_writer_failed" for event, _ in world.tracer.events)
    assert "note_writer" not in [s.tool for s in study.phases[0].steps]


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


def test_mode_for_forces_the_last_round_and_forced_questions() -> None:
    assert mode_for(DESCRIBE, 1, 3) is Mode.FREE
    assert mode_for(DESCRIBE, 3, 3) is Mode.FORCED
    assert mode_for(replace(DESCRIBE, mode=Mode.FORCED), 1, 3) is Mode.FORCED


def test_needed_arms_follow_the_intent_in_phase_0_and_run_later() -> None:
    assert needed_arms(DESCRIBE, 0) == (BASE_ARM,)
    assert needed_arms(WHAT_IF, 0) == (BASE_ARM,)
    assert needed_arms(replace(WHAT_IF, intent=Intent.RUN), 0) == (BASE_ARM, "treatment")
    assert needed_arms(WHAT_IF, 1) == (BASE_ARM, "treatment")
