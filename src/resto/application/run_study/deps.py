"""What the step handlers (`steps`) need to run a plan step, built by the composition root
(`interface/dependencies.py`): their agents, repositories, use cases and promoters (the network,
demand and reroute ones pending until E6.1 and E7.1). The per-run values that are not collaborators
are `StudySettings`."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from resto.application.ports.agents.demand_generator import DemandGeneratorAgent
from resto.application.ports.agents.network_author import NetworkAuthorAgent
from resto.application.ports.agents.scenario_builder import ScenarioBuilderAgent
from resto.application.ports.repositories import (
    DemandRepository,
    NetworkRepository,
    ResultRepository,
    ScenarioRepository,
)
from resto.application.promoters.demand import DemandPromoter
from resto.application.promoters.network import NetworkPromoter
from resto.application.promoters.reroute import ReroutePromoter
from resto.application.run_study.spend import StudyBudget
from resto.application.use_cases.build_scenario import BuildScenario
from resto.application.use_cases.run_simulation import RunSimulation


@dataclass(frozen=True, slots=True)
class StudySettings:
    """What varies per study run and is not a collaborator (ADR-0030 follow-up)."""

    out_dir: Path
    """Root of what the study writes. Only the composition root (`build_run_study`) reads it, to
    build the use cases; `RunStudy` does not."""
    network_max_rounds: int
    """Network Author rounds for a step that sets none (`RESTO_NETWORK_MAX_ROUNDS`)."""
    calibration_max_rounds: int
    """Demand calibration rounds for a step that sets none (`RESTO_CALIBRATION_MAX_ROUNDS`)."""
    budget: StudyBudget = field(default_factory=StudyBudget)


@dataclass(frozen=True, slots=True)
class StepDeps:
    network_author: NetworkAuthorAgent
    demand_generator: DemandGeneratorAgent
    scenario_builder: ScenarioBuilderAgent
    networks: NetworkRepository
    demands: DemandRepository
    scenarios: ScenarioRepository
    results: ResultRepository
    run_simulation: RunSimulation
    build_scenario: BuildScenario
    network_promoter: NetworkPromoter
    """Promotes a created and a derived network (pending, E6.1). A `DraftRejected` means the draft
    was rejected (`StepError(agent)`, or `user_input` when it blames the user); a bare
    `ValueError` is also read as `agent`, any other exception as `infrastructure`
    (`failures.promote`). The same holds for the demand and reroute promoters."""
    demand_promoter: DemandPromoter
    """Pending, E7.1."""
    reroute_promoter: ReroutePromoter
    """Pending, E7.1."""
