"""The composition root (ADR-0025 §6): the one place where the Executor's agent ports meet
their implementations and the infrastructure is bound.

Agents that do not exist yet (Network Author, E6.1; Demand Generator, E7.1) and the promotions of
their drafts are `_Pending` placeholders that raise `NotImplementedError`.
"""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn

from resto.adapters.llm.agents.composer import ComposerPort
from resto.adapters.llm.agents.expert import ExpertPort, NoteWriterPort
from resto.adapters.llm.agents.input_parser import InputParserPort
from resto.adapters.llm.agents.scenario_builder import ScenarioBuilderPort
from resto.adapters.persistence.memory import InMemoryStudyRepository
from resto.adapters.persistence.sqlite.repositories import SqliteDatabase
from resto.adapters.sumo.demand import SumoDemandTools
from resto.adapters.sumo.demand_scaling import SumoDemandScaler
from resto.adapters.sumo.network_query_loader import StoredNetworkQueryLoader
from resto.adapters.sumo.run_directories import FilesystemRunDirectories
from resto.adapters.sumo.runner import SubprocessSumoRunner
from resto.adapters.sumo.writers.rerouter import RerouterWriter
from resto.adapters.sumo.writers.sumocfg import SumocfgFileWriter
from resto.adapters.sumo.writers.tls_program import TlsProgramWriter
from resto.adapters.sumo.writers.vss import VssWriter
from resto.application.event_bus import EventBus, TraceDomainEvents
from resto.application.executor import StudyAgents, StudyDeps, StudyPromotions, StudySettings
from resto.application.executor.note_verification import VerifyNotes
from resto.application.ports.llm import Budget, ToolAgent
from resto.application.ports.repositories import (
    NoteRepository,
    ResultRepository,
    ScenarioRepository,
)
from resto.application.ports.tracing import Tracer
from resto.application.tools.expert import ExpertCollaborators
from resto.application.tools.scenario_builder import BuilderCollaborators
from resto.application.use_cases.ask_expert import AskExpert
from resto.application.use_cases.build_scenario import BuildScenario
from resto.application.use_cases.compose_report import ComposeReport
from resto.application.use_cases.run_simulation import RunSimulation
from resto.application.use_cases.run_study import RunStudy
from resto.application.use_cases.scale_demand import ScaleDemand
from resto.application.use_cases.update_note_status import UpdateNoteStatus
from resto.application.use_cases.write_note import WriteNote
from resto.domain.services.planner import plan_study

AGENT_SECONDS = 300.0


class _Pending:
    """An agent port, or a promotion, whose implementation is a later task."""

    def __init__(self, what: str, task_id: str) -> None:
        self._what = what
        self._task_id = task_id

    def __call__(self, *args: object) -> NoReturn:
        raise NotImplementedError(f"the {self._what} is not implemented yet ({self._task_id})")

    parse = author = obtain = compose = __call__


def build_agents(
    *,
    db: SqliteDatabase,
    agent: ToolAgent,
    budget: Budget,
    network_query_loader: StoredNetworkQueryLoader,
    out_dir: Path,
) -> StudyAgents:
    """The agent ports; `out_dir` is the root of the Builder's scratch (`builder/`)."""
    builder_dir = out_dir / "builder"
    return StudyAgents(
        parser=InputParserPort(agent=agent, budget=budget),
        network_author=_Pending("Network Author", "E6.1"),
        demand_generator=_Pending("Demand Generator", "E7.1"),
        scenario_builder=ScenarioBuilderPort(
            agent=agent,
            budget=budget,
            collaborators=BuilderCollaborators(
                networks=db.networks,
                demands=db.demands,
                network_query_loader=network_query_loader,
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
        ),
        expert=ExpertPort(
            agent=agent,
            budget=budget,
            collaborators=ExpertCollaborators(
                network_query_loader=network_query_loader,
                results=db.results,
                scenarios=db.scenarios,
                notes=db.notes,
            ),
        ),
        note_writer=NoteWriterPort(agent=agent, budget=budget),
        composer=ComposerPort(agent=agent, budget=budget, results=db.results),
    )


def build_promotions() -> StudyPromotions:
    """The promotions of the drafts, all pending."""
    return StudyPromotions(
        network=_Pending("network promotion", "E6.1"),
        demand=_Pending("demand promotion", "E7.1"),
        reroute=_Pending("reroute_demand", "E7.1"),
    )


def build_run_simulation(
    *, db: SqliteDatabase, runner: SubprocessSumoRunner, out_dir: Path
) -> RunSimulation:
    return RunSimulation(
        runner=runner,
        results=db.results,
        run_dirs=FilesystemRunDirectories(),
        out_dir=out_dir / "results",
    )


def build_build_scenario(
    *,
    db: SqliteDatabase,
    runner: SubprocessSumoRunner,
    network_query_loader: StoredNetworkQueryLoader,
    out_dir: Path,
) -> BuildScenario:
    return BuildScenario(
        networks=db.networks,
        demands=db.demands,
        scenarios=db.scenarios,
        network_query_loader=network_query_loader,
        runner=runner,
        out_dir=out_dir / "scenarios",
    )


def build_deps(
    *, db: SqliteDatabase, agent: ToolAgent, budget: Budget, tracer: Tracer, out_dir: Path
) -> StudyDeps:
    """Studies are kept in memory: there is no persistent `StudyRepository` yet, and the SQLite
    database is the DatabaseMCP reference backend, which does not hold them (ADR-0002).
    `out_dir` is the root of everything the study writes: `builder/` (the Builder's scratch and
    its demand scaling), `results/` (RunSimulation) and `scenarios/` (BuildScenario). The study's
    other settings are `StudySettings`.
    """
    network_query_loader = StoredNetworkQueryLoader(db.networks)
    runner = SubprocessSumoRunner()
    return StudyDeps(
        agents=build_agents(
            db=db,
            agent=agent,
            budget=budget,
            network_query_loader=network_query_loader,
            out_dir=out_dir,
        ),
        promotions=build_promotions(),
        networks=db.networks,
        demands=db.demands,
        scenarios=db.scenarios,
        results=db.results,
        studies=InMemoryStudyRepository(),
        run_simulation=build_run_simulation(db=db, runner=runner, out_dir=out_dir),
        events=build_event_bus(
            notes=db.notes, scenarios=db.scenarios, results=db.results, tracer=tracer
        ),
        tracer=tracer,
        planner=plan_study,
        ask_expert=AskExpert(loader=network_query_loader),
        build_scenario=build_build_scenario(
            db=db, runner=runner, network_query_loader=network_query_loader, out_dir=out_dir
        ),
        compose_report=ComposeReport(),
        write_note=WriteNote(db.notes),
    )


def build_event_bus(
    *,
    notes: NoteRepository,
    scenarios: ScenarioRepository,
    results: ResultRepository,
    tracer: Tracer,
) -> EventBus:
    """The bus of the study's domain events (ADR-0041 §11): the trace first, then note
    verification. The bus queues what a handler publishes, so this order does not change the
    trace."""
    bus = EventBus(tracer)
    bus.subscribe("trace", TraceDomainEvents(tracer))
    bus.subscribe(
        "note_verification",
        VerifyNotes(
            notes=notes,
            scenarios=scenarios,
            results=results,
            update_note_status=UpdateNoteStatus(notes),
            publish=bus.publish,
        ),
    )
    return bus


def build_run_study(
    *,
    db: SqliteDatabase,
    agent: ToolAgent,
    budget: Budget,
    tracer: Tracer,
    settings: StudySettings,
) -> RunStudy:
    """The ready `RunStudy`: the object graph of `build_deps`, built with `settings.out_dir` as its
    `out_dir`, plus `settings` itself, which `RunStudy` hands to the Executor."""
    deps = build_deps(db=db, agent=agent, budget=budget, tracer=tracer, out_dir=settings.out_dir)
    return RunStudy(deps, settings)
