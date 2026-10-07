"""Shared test world for the Executor tests, the CLI tests and the golden paths: scripted agent
ports, fake promotions, in-memory repositories, a fake SUMO runner and sample plans. No network."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from resto.adapters.persistence.memory import (
    InMemoryDemandRepository,
    InMemoryNetworkRepository,
    InMemoryNoteRepository,
    InMemoryResultRepository,
    InMemoryScenarioRepository,
    InMemoryStudyRepository,
)
from resto.adapters.sumo.network_query_loader import StoredNetworkQueryLoader
from resto.adapters.sumo.run_directories import FilesystemRunDirectories
from resto.application.executor import (
    StudyAgents,
    StudyBudget,
    StudyDeps,
    StudyPromotions,
    StudySettings,
)
from resto.application.ports.llm import AgentRun, StopReason
from resto.application.ports.sumo import RunOutput
from resto.application.ports.tracing import TraceEvent
from resto.application.tools.expert import EvidenceLedger
from resto.application.use_cases.run_study import run_study
from resto.domain.constants import DEFAULT_SEEDS
from resto.domain.entities.demand import Demand
from resto.domain.entities.network import Network
from resto.domain.entities.scenario import Scenario
from resto.domain.entities.simulation_result import RunMode, RunStatus, SimulationResult
from resto.domain.entities.study import Study
from resto.domain.services.ids import result_id_for, scenario_id_for
from resto.domain.services.planner import PlanningContext
from resto.domain.value_objects.answer_value import Measure, Quantity
from resto.domain.value_objects.drafts import (
    ExpertNoteDrafts,
    ScenarioDraft,
)
from resto.domain.value_objects.experiment import ExperimentRole
from resto.domain.value_objects.expert_answer import Basis, Evidence, EvidenceKind, ExpertAnswer
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import LaneTarget
from resto.domain.value_objects.kpis import Kpis
from resto.domain.value_objects.mechanism import ScriptMechanism, StaticFileMechanism
from resto.domain.value_objects.network_recipe import NetworkRecipe
from resto.domain.value_objects.outcomes import Found
from resto.domain.value_objects.question import Intent, Mode, Question
from resto.domain.value_objects.report import Report
from resto.domain.value_objects.step_record import StepErrorKind, StepStatus, Usage
from resto.domain.value_objects.study_plan import (
    StudyPlan,
)
from resto.domain.value_objects.tasks import ExpertTask, NoteTask, ObtainNetworkTask
from resto.domain.value_objects.time_window import TimeWindow
from resto.domain.value_objects.topology_modification import AddEdge
from tests.unit.application._doubles import FakeRunner, StubNetworkQuery
from tests.unit.domain._fixtures import (
    DEMAND,
    NET,
    after_obtain_network,
    artifact,
    build_step,
    good_sanity,
    network_draft,
    plan_network,
    run_step,
    runnable_script,
    static_intervention,
)
from tests.unit.domain._samples import demand as sample_demand
from tests.unit.domain._samples import network as sample_network

CLOSURE = static_intervention()  # lane 1 of E12, fixed window
UNKNOWN_LANE = Intervention(
    type=InterventionType.LANE_CLOSURE,
    target=LaneTarget(edge_id="E99", lane_index=0),
    window=TimeWindow(7 * 3600, 10 * 3600),
)
NEW_EDGE = AddEdge("J7", "J9", lanes=2, speed=13.9, edge_id="J7J9")
QUERY = StubNetworkQuery(edges={"E12"}, lanes={("E12", 1)})
DERIVED_QUERY = StubNetworkQuery(edges={"E12", "J7J9"}, lanes={("E12", 1)})  # NEW_EDGE added
REPORT = Report(summary="done", mode=Mode.FREE, basis=Basis.OBSERVED)
KPIS = Kpis(mean_delay=24.4, mean_travel_time=85.4, teleports=0, departed=50, arrived=43)

NETWORK_ROUNDS = 7
CALIBRATION_ROUNDS = 3
"""The World's configured limits, apart from the usual 5 to show where a value comes from."""

DESCRIBE = Question(text="how congested is the peak?", intent=Intent.DESCRIBE)
WHAT_IF = Question(
    text="what if we close lane 1 of E12?", intent=Intent.COMPARE, interventions=(CLOSURE,)
)
DESCRIBE_CHANGE = Question(
    text="how would closing lane 1 of E12 look?", intent=Intent.DESCRIBE, interventions=(CLOSURE,)
)
"""Phase 0 plans only the base; the Expert has to ask for the closure."""
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


class FakePlanner(Scripted):
    """The injected planner: answers each call with the next scripted `StudyPlan`, or raises the
    next scripted `PlanningError`. `calls` holds the `(question, context)` of every call."""

    def __call__(self, question: Question, context: PlanningContext) -> StudyPlan:
        return self._next(question, context)  # type: ignore[no-any-return]


class FakeAuthor(Scripted):
    """`obtain` and `author` draw from the same script, in call order."""

    def obtain(self, task: Any) -> AgentRun[Any]:
        return self._next(task)  # type: ignore[no-any-return]

    def author(self, task: Any) -> AgentRun[Any]:
        return self._next(task)  # type: ignore[no-any-return]


class FakeGenerator(Scripted):
    def obtain(self, task: Any) -> AgentRun[Any]:
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
    """The in-memory tracer: keeps the typed events, no JSON in between."""

    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def emit(self, study_id: str, event: TraceEvent) -> None:
        self.events.append(event)


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


def obtained_network(task: Any, run: Any) -> Network:
    return Network(
        network_id="obtained-1",
        net_xml=artifact("obtained.net.xml", "obtained-1", "net"),
        recipe=run.output.recipe,
        sanity_report=good_sanity(),
    )


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


@dataclass(frozen=True)
class Simulations:
    """The runner's calls as (scenario_id, seed) pairs, in call order."""

    load_checks: tuple[tuple[str, int], ...]
    study_runs: tuple[tuple[str, int], ...]


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
        author: tuple[Any, ...] = (),
        generator: tuple[Any, ...] = (),
        note_writer: tuple[Any, ...] = (),
        composer: tuple[Any, ...] = (),
        runner: FakeRunner | None = None,
        budget: StudyBudget | None = None,
    ) -> None:
        parsed = question if not isinstance(question, Question) else run_of(question, tokens=50)
        self.parser = FakeParser(parsed)
        self.planner = FakePlanner(*plans)
        self.author = FakeAuthor(
            *author,
            default=lambda task: (
                run_of(Found(NET))
                if isinstance(task, ObtainNetworkTask)
                else run_of(network_draft(), tokens=100)
            ),
        )
        self.generator = FakeGenerator(*generator, default=lambda task: run_of(Found(DEMAND)))
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
        self.query_loads: list[Path] = []
        self.deps = StudyDeps(
            agents=StudyAgents(
                parser=self.parser,
                network_author=self.author,
                demand_generator=self.generator,
                scenario_builder=self.builder,
                expert=self.expert,
                note_writer=self.note_writer,
                composer=self.composer,
            ),
            promotions=StudyPromotions(
                network=self._promote_network,
                demand=self._promote_demand,
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
            run_dirs=FilesystemRunDirectories(),
            network_query_loader=StoredNetworkQueryLoader(self.networks, self._load_query),
            tracer=self.tracer,
            planner=self.planner,
        )
        self.settings = StudySettings(
            out_dir=tmp_path,
            network_max_rounds=NETWORK_ROUNDS,
            calibration_max_rounds=CALIBRATION_ROUNDS,
            budget=budget or StudyBudget(),
        )

    def _load_query(self, path: Path) -> StubNetworkQuery:
        self.query_loads.append(path)
        return DERIVED_QUERY if path.name == "derived.net.xml" else QUERY

    def _promote_network(self, task: Any, run: Any) -> Network:
        network = (
            obtained_network(task, run)
            if isinstance(task, ObtainNetworkTask)
            else derived_network(task, run)
        )
        self.promoted_networks.append(task)
        self.networks.store(network)
        return network

    def _promote_demand(self, task: Any, run: Any) -> Demand:
        demand = replace(
            sample_demand(),
            demand_id="obtained-demand",
            network_id=task.network_id,
            trips=artifact("trips3.xml", "obtained-demand", "trips"),
        )
        self.demands.store(demand)
        return demand

    def _reroute(self, demand: Demand, network: Network) -> Demand:
        rerouted = Demand(
            demand_id=f"{demand.demand_id}-on-{network.network_id}",
            network_id=network.network_id,
            spec=demand.spec,
            trips=artifact("trips2.xml", f"{demand.demand_id}-on-{network.network_id}", "trips"),
            routes=artifact("routes2.xml", "r2", "routes"),
            description=demand.description,
            labels=demand.labels,
            derived_from=demand.demand_id,
        )
        self.demands.store(rerouted)
        return rerouted

    def simulations(self) -> Simulations:
        """What reached the runner, read off `runner.calls` as (scenario_id, seed) pairs: the load
        checks of built scenarios apart from the study's runs."""
        load_checks: list[tuple[str, int]] = []
        study_runs: list[tuple[str, int]] = []
        for _, seed, out_dir in self.runner.calls:
            if out_dir.name == "load_check":
                load_checks.append((out_dir.parent.name, seed))
                continue
            result = self.results.get(out_dir.name.split(".")[0])
            assert result is not None, f"a run left no result: {out_dir}"
            study_runs.append((result.scenario_id, result.seed))
        return Simulations(tuple(load_checks), tuple(study_runs))

    def run(self, **kwargs: Any) -> Study:
        return run_study("the user's text", self.deps, self.settings, **kwargs)

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


def plan(*steps: Any, network: Any = NET) -> StudyPlan:
    """A plan of `steps` behind the `obtain_network` step every plan has: see
    `after_obtain_network` for how the indexes in `steps` are read. The tests seed it through
    the injected planner (`World.planner`)."""
    return StudyPlan(
        network_id=plan_network(network),
        rationale="as needed",
        steps=after_obtain_network(*steps),
    )


BASELINE_PLAN = plan(build_step(), run_step(0))
WHAT_IF_PLAN = plan(
    build_step(),
    run_step(0),
    build_step("treatment", (CLOSURE,), role=ExperimentRole.TREATMENT),
    run_step(2),
)
"""Phase 0 of `WHAT_IF`: both sides of the contrast (ADR-0038)."""
TREATMENT_PLAN = plan(
    build_step("treatment", (CLOSURE,), role=ExperimentRole.TREATMENT), run_step(0)
)


def tools(study: Study, phase: int = 0) -> list[tuple[str, StepStatus]]:
    return [(s.tool, s.status) for s in study.phases[phase].steps]


def failed_kind(study: Study) -> StepErrorKind:
    step = study.phases[-1].failed_step
    assert step is not None and step.error is not None
    return step.error.kind
