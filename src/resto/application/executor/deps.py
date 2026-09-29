"""What the composition root builds to run a `Study`: the agents, the promotions not
implemented yet, and the repositories and adapters. The study's settings are `StudySettings`."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from resto.application.ports.agents.composer import ComposerAgent
from resto.application.ports.agents.coordinator import CoordinatorAgent
from resto.application.ports.agents.demand_generator import DemandGeneratorAgent
from resto.application.ports.agents.expert import ExpertAgent
from resto.application.ports.agents.input_parser import InputParserAgent
from resto.application.ports.agents.network_author import NetworkAuthorAgent
from resto.application.ports.agents.note_writer import NoteWriterAgent
from resto.application.ports.agents.scenario_builder import ScenarioBuilderAgent
from resto.application.ports.llm import AgentRun
from resto.application.ports.repositories import (
    DemandRepository,
    NetworkRepository,
    NoteRepository,
    ResultRepository,
    ScenarioRepository,
    StudyRepository,
)
from resto.application.ports.run_directories import RunDirectories
from resto.application.ports.sumo import SumoRunner
from resto.application.ports.tracing import Tracer
from resto.application.use_cases.build_scenario import NetworkQueryFactory
from resto.domain.constants import (
    DEFAULT_STUDY_MAX_AGENT_CALLS,
    DEFAULT_STUDY_MAX_SIMULATIONS,
    DEFAULT_STUDY_MAX_TOKENS,
)
from resto.domain.entities.demand import Demand
from resto.domain.entities.network import Network
from resto.domain.entities.study import Study
from resto.domain.value_objects.drafts import DemandDraft, NetworkDraft
from resto.domain.value_objects.report import Report
from resto.domain.value_objects.tasks import DemandTask, NetworkTask


@dataclass(frozen=True, slots=True)
class StudyBudget:
    """What one `Study` may spend in total, on top of each agent call's own `Budget`
    (ADR-0023 §5). Exhausting it fails the step about to run with `StepError(budget)`."""

    max_tokens: int = DEFAULT_STUDY_MAX_TOKENS
    max_simulations: int = DEFAULT_STUDY_MAX_SIMULATIONS
    max_agent_calls: int = DEFAULT_STUDY_MAX_AGENT_CALLS


@dataclass(frozen=True, slots=True)
class StudySettings:
    """What varies per study run and is not a collaborator (ADR-0030 follow-up)."""

    out_dir: Path
    budget: StudyBudget = field(default_factory=StudyBudget)
    has_historical_demand: bool = False


@dataclass(frozen=True, slots=True)
class StudyAgents:
    parser: InputParserAgent
    coordinator: CoordinatorAgent
    network_author: NetworkAuthorAgent
    demand_generator: DemandGeneratorAgent
    scenario_builder: ScenarioBuilderAgent
    expert: ExpertAgent
    note_writer: NoteWriterAgent
    composer: ComposerAgent


@dataclass(frozen=True, slots=True)
class StudyPromotions:
    """The promotions not implemented yet (E5.4, E6.1, E6.2), injected so the Executor does not
    change when they land. A `ValueError` means the draft was rejected (`StepError(agent)`); any
    other exception is `infrastructure`. `network` promotes both a created and a derived network
    (the task says which).

    A temporary seam, not a port to extend: it goes away with E5.4 / E6.1 / E6.2, when the
    Executor calls those use cases directly, as it already does with `build_scenario`."""

    network: Callable[[NetworkTask, AgentRun[NetworkDraft]], Network]
    demand: Callable[[DemandTask, AgentRun[DemandDraft]], Demand]
    reroute: Callable[[Demand, Network], Demand]
    report: Callable[[Study, AgentRun[Report]], Report]


@dataclass(frozen=True, slots=True)
class StudyDeps:
    agents: StudyAgents
    promotions: StudyPromotions
    networks: NetworkRepository
    demands: DemandRepository
    scenarios: ScenarioRepository
    results: ResultRepository
    notes: NoteRepository
    studies: StudyRepository
    runner: SumoRunner
    run_dirs: RunDirectories
    network_query_factory: NetworkQueryFactory
    tracer: Tracer
