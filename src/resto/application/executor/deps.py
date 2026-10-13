"""What the composition root (`interface/dependencies.py`) builds to run a `Study`: the agents, the
planner, the repositories, the network query loader, the event bus with its subscribers already
wired, the tracer for telemetry, the promoters (the network, demand and reroute ones pending until
E6.1 and E7.1), and the use-case instances the Executor calls (`RunSimulation`, `BuildScenario`),
each already holding its own collaborators. The per-run values that are not collaborators are
`StudySettings`."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from resto.application.event_bus import EventBus
from resto.application.ports.agents.composer import ComposerAgent
from resto.application.ports.agents.demand_generator import DemandGeneratorAgent
from resto.application.ports.agents.expert import ExpertAgent
from resto.application.ports.agents.input_parser import InputParserAgent
from resto.application.ports.agents.network_author import NetworkAuthorAgent
from resto.application.ports.agents.note_writer import NoteWriterAgent
from resto.application.ports.agents.scenario_builder import ScenarioBuilderAgent
from resto.application.ports.network_query import NetworkQueryLoader
from resto.application.ports.repositories import (
    DemandRepository,
    NetworkRepository,
    NoteRepository,
    ResultRepository,
    ScenarioRepository,
    StudyRepository,
)
from resto.application.ports.tracing import Tracer
from resto.application.promoters.demand import DemandPromoter
from resto.application.promoters.expert_answer import ExpertAnswerPromoter
from resto.application.promoters.network import NetworkPromoter
from resto.application.promoters.notes import NotePromoter
from resto.application.promoters.report import ReportPromoter
from resto.application.promoters.reroute import ReroutePromoter
from resto.application.use_cases.build_scenario import BuildScenario
from resto.application.use_cases.run_simulation import RunSimulation
from resto.domain.constants import (
    DEFAULT_STUDY_MAX_AGENT_CALLS,
    DEFAULT_STUDY_MAX_SIMULATIONS,
    DEFAULT_STUDY_MAX_TOKENS,
)
from resto.domain.services.planner import PlanningContext
from resto.domain.value_objects.question import Question
from resto.domain.value_objects.study_plan import StudyPlan


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
    """Root of what the study writes. Only the composition root (`build_run_study`) reads it, to
    build the use cases; the Executor does not."""
    network_max_rounds: int
    """Network Author rounds for a step that sets none (`RESTO_NETWORK_MAX_ROUNDS`)."""
    calibration_max_rounds: int
    """Demand calibration rounds for a step that sets none (`RESTO_CALIBRATION_MAX_ROUNDS`)."""
    budget: StudyBudget = field(default_factory=StudyBudget)


@dataclass(frozen=True, slots=True)
class StudyAgents:
    parser: InputParserAgent
    network_author: NetworkAuthorAgent
    demand_generator: DemandGeneratorAgent
    scenario_builder: ScenarioBuilderAgent
    expert: ExpertAgent
    note_writer: NoteWriterAgent
    composer: ComposerAgent


Planner = Callable[[Question, PlanningContext], StudyPlan]
"""The planning function the Executor calls for each phase (`resto.domain.services.planner.
plan_study` in production). It raises `PlanningError` for a question it cannot plan. Injected so the
Executor's tests control the plan without an agent."""


@dataclass(frozen=True, slots=True)
class StudyDeps:
    agents: StudyAgents
    networks: NetworkRepository
    demands: DemandRepository
    scenarios: ScenarioRepository
    results: ResultRepository
    notes: NoteRepository
    """Where the notes stage stores what `note_promoter` returns."""
    studies: StudyRepository
    network_queries: NetworkQueryLoader
    """Loads the networks of the Expert's scope for `expert_answer_promoter`."""
    run_simulation: RunSimulation
    events: EventBus
    """Where the `StudyRecorder` publishes the study's domain events."""
    tracer: Tracer
    """The telemetry (`ModelCall`, `NoteWriterFailed`): emitted straight, not through `events`."""
    planner: Planner
    build_scenario: BuildScenario
    expert_answer_promoter: ExpertAnswerPromoter
    note_promoter: NotePromoter
    report_promoter: ReportPromoter
    network_promoter: NetworkPromoter
    """Promotes a created and a derived network (pending, E6.1). A `DraftRejected` means the draft
    was rejected (`StepError(agent)`, or `user_input` when it blames the user); a bare
    `ValueError` is also read as `agent`, any other exception as `infrastructure`
    (`failures.promote`). The same holds for the demand and reroute promoters."""
    demand_promoter: DemandPromoter
    """Pending, E7.1."""
    reroute_promoter: ReroutePromoter
    """Pending, E7.1."""
