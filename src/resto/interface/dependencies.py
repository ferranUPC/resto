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
from resto.application.executor import StudyAgents, StudyDeps, StudyPromotions
from resto.application.ports.llm import Budget, ToolAgent
from resto.application.ports.tracing import Tracer
from resto.application.tools.expert import ExpertCollaborators
from resto.application.tools.scenario_builder import BuilderCollaborators
from resto.application.use_cases.run_simulation import RunSimulation
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


def build_deps(
    *, db: SqliteDatabase, agent: ToolAgent, budget: Budget, tracer: Tracer, out_dir: Path
) -> StudyDeps:
    """Studies are kept in memory: there is no persistent `StudyRepository` yet, and the SQLite
    database is the DatabaseMCP reference backend, which does not hold them (ADR-0002).
    `out_dir` here is only the Builder's; the study's own settings are `StudySettings`.
    """
    network_query_loader = StoredNetworkQueryLoader(db.networks)
    studies = InMemoryStudyRepository()
    runner = SubprocessSumoRunner()
    return StudyDeps(
        agents=StudyAgents(
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
                        demands=db.demands,
                        out_dir=out_dir / "builder",
                    ),
                    out_dir=out_dir / "builder",
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
        ),
        promotions=StudyPromotions(
            network=_Pending("network promotion", "E6.1"),
            demand=_Pending("demand promotion", "E7.1"),
            reroute=_Pending("reroute_demand", "E7.1"),
        ),
        networks=db.networks,
        demands=db.demands,
        scenarios=db.scenarios,
        results=db.results,
        notes=db.notes,
        studies=studies,
        runner=runner,
        run_simulation=RunSimulation(
            runner, db.results, FilesystemRunDirectories(), out_dir / "results"
        ),
        network_query_loader=network_query_loader,
        tracer=tracer,
        planner=plan_study,
        update_note_status=UpdateNoteStatus(db.notes),
        write_note=WriteNote(db.notes),
    )
