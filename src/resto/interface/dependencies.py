"""The composition root (ADR-0025 §6, ADR-0042 §14): the one place where the study's agent ports
meet their implementations and the infrastructure is bound.

The Demand Generator (E7.1) is a `_Pending` placeholder that raises `NotImplementedError`; so are
the promoters of its drafts and of a reroute (`DemandPromoter`, `ReroutePromoter`) until those tasks
build them. The Network Author is real: its tools use the real `netgenerate`/`netconvert`, the
Nominatim and Overpass adapters and the SUMO prober, and `NetworkPromoter` replays recipes with the
same runner and the plain XML editor. Nothing here touches the network until an agent calls a tool.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import NoReturn

from resto.adapters.llm.agents.composer import ComposerPort
from resto.adapters.llm.agents.expert import ExpertPort, NoteWriterPort
from resto.adapters.llm.agents.input_parser import InputParserPort
from resto.adapters.llm.agents.network_author import NetworkAuthorCollaborators, NetworkAuthorPort
from resto.adapters.llm.agents.scenario_builder import ScenarioBuilderPort
from resto.adapters.llm.config import RoundsConfig
from resto.adapters.osm.nominatim import NominatimGeocoder
from resto.adapters.osm.overpass import OverpassOsmSource
from resto.adapters.persistence.memory import InMemoryStudyRepository
from resto.adapters.persistence.sqlite.repositories import SqliteDatabase
from resto.adapters.sumo.demand import SumoDemandTools
from resto.adapters.sumo.demand_scaling import SumoDemandScaler
from resto.adapters.sumo.netconvert import SubprocessNetconvertRunner
from resto.adapters.sumo.network_probe import SumoNetworkProber
from resto.adapters.sumo.network_query_loader import StoredNetworkQueryLoader
from resto.adapters.sumo.netxml import SumolibNetworkQuery
from resto.adapters.sumo.plain_edit import XmlPlainNetEditor
from resto.adapters.sumo.run_directories import FilesystemRunDirectories
from resto.adapters.sumo.runner import SubprocessSumoRunner
from resto.adapters.sumo.typemaps import typemap_dir
from resto.adapters.sumo.writers.rerouter import RerouterWriter
from resto.adapters.sumo.writers.sumocfg import SumocfgFileWriter
from resto.adapters.sumo.writers.tls_program import TlsProgramWriter
from resto.adapters.sumo.writers.vss import VssWriter
from resto.application.event_bus import EventBus
from resto.application.event_handlers.note_verification import NoteVerificationHandler
from resto.application.event_handlers.trace import TRACED_EVENTS, TraceHandler
from resto.application.ports.agents.demand_generator import DemandGeneratorAgent
from resto.application.ports.agents.network_author import NetworkAuthorAgent
from resto.application.ports.llm import Budget, ToolAgent
from resto.application.ports.osm import OsmLimits
from resto.application.ports.repositories import (
    NoteRepository,
    ResultRepository,
    ScenarioRepository,
)
from resto.application.ports.tracing import Tracer
from resto.application.promoters.demand import DemandPromoter
from resto.application.promoters.expert_answer import ExpertAnswerPromoter
from resto.application.promoters.network import NetworkPromoter
from resto.application.promoters.notes import NotePromoter
from resto.application.promoters.report import ReportPromoter
from resto.application.promoters.reroute import ReroutePromoter
from resto.application.promoters.scenario import ScenarioPromoter
from resto.application.run_study import RunStudy
from resto.application.run_study.spend import StudyBudget
from resto.application.run_study.stages.closing import ComposeStage, NotesStage
from resto.application.run_study.stages.expert_round import ExpertRoundStage
from resto.application.run_study.stages.parse import ParseStage
from resto.application.run_study.stages.plan import PlanStage
from resto.application.run_study.steps.build_scenario import BuildScenarioExecutor
from resto.application.run_study.steps.derive_network import DeriveNetworkExecutor
from resto.application.run_study.steps.obtain_demand import ObtainDemandExecutor
from resto.application.run_study.steps.obtain_network import ObtainNetworkExecutor
from resto.application.run_study.steps.reroute_demand import RerouteDemandExecutor
from resto.application.run_study.steps.run_simulation import RunSimulationExecutor
from resto.application.tools.expert import ExpertCollaborators
from resto.application.tools.scenario_builder import BuilderCollaborators
from resto.application.use_cases.build_scenario import BuildScenario
from resto.application.use_cases.run_simulation import RunSimulation
from resto.application.use_cases.scale_demand import ScaleDemand
from resto.domain.events import SimulationsRecorded
from resto.domain.services.planner import plan_study
from resto.domain.value_objects.study_plan import (
    BuildScenarioStep,
    DeriveNetworkStep,
    ObtainDemandStep,
    ObtainNetworkStep,
    RerouteDemandStep,
    RunSimulationStep,
)

AGENT_SECONDS = 300.0
NETWORK_AUTHOR_STEPS = 40
"""Tool calls one Network Author run may make. A repair cycle takes several (edit, recompile,
`sanity_check`), so the Author gets far more than the other agents' `max_steps`."""
NETWORK_AUTHOR_SECONDS = 900.0


class _Pending:
    """An agent port whose implementation is a later task."""

    def __init__(self, what: str, task_id: str) -> None:
        self._what = what
        self._task_id = task_id

    def __call__(self, *args: object) -> NoReturn:
        raise NotImplementedError(f"the {self._what} is not implemented yet ({self._task_id})")

    parse = author = obtain = compose = __call__


def build_event_bus(
    *,
    notes: NoteRepository,
    scenarios: ScenarioRepository,
    results: ResultRepository,
    tracer: Tracer,
) -> EventBus:
    """The bus of the study's domain events (ADR-0041 §11, ADR-0042 §11), with its handlers in the
    order the bus documents: the trace first, then note verification."""
    bus = EventBus(tracer)
    trace = TraceHandler(tracer)
    for event_type in TRACED_EVENTS:
        bus.subscribe(event_type, trace)
    bus.subscribe(
        SimulationsRecorded,
        NoteVerificationHandler(notes=notes, scenarios=scenarios, results=results),
    )
    return bus


def build_run_study(
    *,
    db: SqliteDatabase,
    agent: ToolAgent,
    budget: Budget,
    tracer: Tracer,
    out_dir: Path,
    rounds: RoundsConfig | None = None,
    study_budget: StudyBudget | None = None,
    network_author: NetworkAuthorAgent | None = None,
    demand_generator: DemandGeneratorAgent | None = None,
    osm_limits: OsmLimits | None = None,
) -> RunStudy:
    """The ready `RunStudy`. Studies are kept in memory: there is no persistent `StudyRepository`
    yet, and the SQLite database is the DatabaseMCP reference backend, which does not hold them
    (ADR-0002). `out_dir` is the root of everything the study writes: `builder/` (the Builder's
    scratch and its demand scaling), `results/` (RunSimulation) and `scenarios/` (BuildScenario).
    `network_author` and `demand_generator` replace the agents (tests, manual runs); the Network
    Author works under `network/` and downloads OpenStreetMap within `osm_limits`."""
    rounds = rounds or RoundsConfig()
    osm_limits = osm_limits or OsmLimits()
    netconvert = SubprocessNetconvertRunner()
    plain_editor = XmlPlainNetEditor()
    author = network_author or NetworkAuthorPort(
        agent=agent,
        budget=replace(budget, max_steps=NETWORK_AUTHOR_STEPS, max_seconds=NETWORK_AUTHOR_SECONDS),
        collaborators=NetworkAuthorCollaborators(
            networks=db.networks,
            runner=netconvert,
            editor=plain_editor,
            prober=SumoNetworkProber(SubprocessSumoRunner()),
            open_network=SumolibNetworkQuery,
            osm=OverpassOsmSource(limits=osm_limits),
            geocoder=NominatimGeocoder(out_dir / "network" / "geocoder"),
            typemap_dir=typemap_dir(),
            out_dir=out_dir / "network" / "author",
            limits=osm_limits,
        ),
    )
    generator = demand_generator or _Pending("Demand Generator", "E7.1")
    builder_dir = out_dir / "builder"
    loader = StoredNetworkQueryLoader(db.networks)
    runner = SubprocessSumoRunner()
    network_promoter = NetworkPromoter(netconvert, plain_editor)
    builder = ScenarioBuilderPort(
        agent=agent,
        budget=budget,
        collaborators=BuilderCollaborators(
            networks=db.networks,
            demands=db.demands,
            network_query_loader=loader,
            rerouter_writer=RerouterWriter(),
            vss_writer=VssWriter(),
            tls_program_writer=TlsProgramWriter(),
            sumocfg_writer=SumocfgFileWriter(),
            scale_demand=ScaleDemand(
                scaler=SumoDemandScaler(),
                duarouter=SumoDemandTools(),
                demand_repository=db.demands,
                out_dir=builder_dir,
            ),
            out_dir=builder_dir,
        ),
    )
    expert = ExpertPort(
        agent=agent,
        budget=budget,
        collaborators=ExpertCollaborators(
            network_query_loader=loader, results=db.results, scenarios=db.scenarios, notes=db.notes
        ),
    )
    return RunStudy(
        parse=ParseStage(InputParserPort(agent=agent, budget=budget)),
        plan=PlanStage(plan_study, networks=db.networks, demands=db.demands),
        expert_round=ExpertRoundStage(expert, loader, ExpertAnswerPromoter()),
        notes=NotesStage(
            NoteWriterPort(agent=agent, budget=budget),
            NotePromoter(),
            networks=db.networks,
            scenarios=db.scenarios,
            notes=db.notes,
            tracer=tracer,
        ),
        compose=ComposeStage(
            ComposerPort(agent=agent, budget=budget, results=db.results), ReportPromoter()
        ),
        steps={
            ObtainNetworkStep: ObtainNetworkExecutor(
                author, db.networks, network_promoter, rounds.network_max_rounds
            ),
            DeriveNetworkStep: DeriveNetworkExecutor(
                author, db.networks, network_promoter, rounds.network_max_rounds
            ),
            ObtainDemandStep: ObtainDemandExecutor(
                generator, db.demands, DemandPromoter(), rounds.calibration_max_rounds
            ),
            RerouteDemandStep: RerouteDemandExecutor(db.networks, db.demands, ReroutePromoter()),
            BuildScenarioStep: BuildScenarioExecutor(
                builder,
                db.scenarios,
                db.results,
                BuildScenario(
                    networks=db.networks,
                    demands=db.demands,
                    scenarios=db.scenarios,
                    network_query_loader=loader,
                    runner=runner,
                    promoter=ScenarioPromoter(),
                    out_dir=out_dir / "scenarios",
                ),
            ),
            RunSimulationStep: RunSimulationExecutor(
                db.scenarios,
                db.results,
                RunSimulation(
                    runner=runner,
                    results=db.results,
                    run_dirs=FilesystemRunDirectories(),
                    out_dir=out_dir / "results",
                ),
            ),
        },
        studies=InMemoryStudyRepository(),
        events=build_event_bus(
            notes=db.notes, scenarios=db.scenarios, results=db.results, tracer=tracer
        ),
        tracer=tracer,
        budget=study_budget or StudyBudget(),
    )
