"""CLI entrypoint and composition root (ADR-0025 §6): the one place where the Executor's agent
ports meet their implementations and the infrastructure is bound.

Agents that do not exist yet — Input Parser (E5.1), Coordinator (E5.2), Output Composer (E5.4),
Network Author (E6.1), Demand Generator (E6.2) — and the promotions of their drafts are placeholders
that raise `NotImplementedError`. With no parser a request ends in `ParserFailed` before any model
call, and the CLI reports it without creating a Study.

    python -m resto.interface.cli.main "how congested is the peak?" [--mode forced]
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

from resto.adapters.llm.agents.expert import ExpertPort, NoteWriterPort
from resto.adapters.llm.agents.scenario_builder import ScenarioBuilderPort
from resto.adapters.persistence.memory import InMemoryStudyRepository
from resto.adapters.persistence.sqlite.repositories import SqliteDatabase
from resto.adapters.sumo.demand import SumoDemandTools
from resto.adapters.sumo.demand_scaling import SumoDemandScaler
from resto.adapters.sumo.netxml import SumolibNetworkQuery
from resto.adapters.sumo.runner import SubprocessSumoRunner
from resto.adapters.sumo.writers.rerouter import RerouterWriter
from resto.adapters.sumo.writers.sumocfg import SumocfgFileWriter
from resto.adapters.sumo.writers.tls_program import TlsProgramWriter
from resto.adapters.sumo.writers.vss import VssWriter
from resto.adapters.tracing.jsonl import JsonlTracer
from resto.application.ports.llm import Budget, ToolAgent
from resto.application.ports.tracing import Tracer
from resto.application.use_cases.run_study import (
    ParserFailed,
    StudyAgents,
    StudyDeps,
    StudyPromotions,
    run_study,
)
from resto.domain.entities.study import StudyStatus
from resto.domain.value_objects.question import Mode

AGENT_SECONDS = 300.0


class _Pending:
    """An agent port, or a promotion, whose implementation is a later task."""

    def __init__(self, what: str, task_id: str) -> None:
        self._what = what
        self._task_id = task_id

    def __call__(self, *args: object) -> NoReturn:
        raise NotImplementedError(f"the {self._what} is not implemented yet ({self._task_id})")

    parse = plan = author = generate = compose = __call__


def build_deps(
    *, db: SqliteDatabase, agent: ToolAgent, budget: Budget, tracer: Tracer, out_dir: Path
) -> StudyDeps:
    """Studies are kept in memory: there is no persistent `StudyRepository` yet, and the SQLite
    database is the DatabaseMCP reference backend, which does not hold them (ADR-0002).
    `has_historical_demand` stays false until capability negotiation is wired (E5.6)."""
    return StudyDeps(
        agents=StudyAgents(
            parser=_Pending("Input Parser", "E5.1"),
            coordinator=_Pending("Coordinator", "E5.2"),
            network_author=_Pending("Network Author", "E6.1"),
            demand_generator=_Pending("Demand Generator", "E6.2"),
            scenario_builder=ScenarioBuilderPort(
                agent=agent,
                budget=budget,
                networks=db.networks,
                demands=db.demands,
                network_query_factory=SumolibNetworkQuery,
                rerouter_writer=RerouterWriter(),
                vss_writer=VssWriter(),
                tls_program_writer=TlsProgramWriter(),
                sumocfg_writer=SumocfgFileWriter(),
                demand_scaler=SumoDemandScaler(),
                duarouter=SumoDemandTools(),
                out_dir=out_dir / "builder",
            ),
            expert=ExpertPort(
                agent=agent,
                budget=budget,
                networks=db.networks,
                results=db.results,
                scenarios=db.scenarios,
                notes=db.notes,
                network_query_factory=SumolibNetworkQuery,
            ),
            note_writer=NoteWriterPort(agent=agent, budget=budget),
            composer=_Pending("Output Composer", "E5.4"),
        ),
        promotions=StudyPromotions(
            network=_Pending("network promotion", "E6.1"),
            demand=_Pending("demand promotion", "E6.2"),
            reroute=_Pending("reroute_demand", "E6.2"),
            report=_Pending("compose_report promotion", "E5.4"),
        ),
        networks=db.networks,
        demands=db.demands,
        scenarios=db.scenarios,
        results=db.results,
        notes=db.notes,
        studies=InMemoryStudyRepository(),
        runner=SubprocessSumoRunner(),
        network_query_factory=SumolibNetworkQuery,
        tracer=tracer,
        out_dir=out_dir,
    )


def main(argv: Sequence[str] | None = None, *, deps: StudyDeps | None = None) -> int:
    """`deps` replaces the real wiring (tests)."""
    parser = argparse.ArgumentParser(prog="resto", description="Run one RESTO study.")
    parser.add_argument("text", help="the question, in natural language")
    parser.add_argument("--mode", choices=[m.value for m in Mode], default=None)
    parser.add_argument("--db", type=Path, default=Path("resto.sqlite"))
    parser.add_argument("--out", type=Path, default=Path("runs"))
    args = parser.parse_args(argv)
    mode = Mode(args.mode) if args.mode else None

    db: SqliteDatabase | None = None
    if deps is None:
        from resto.adapters.llm.anthropic_client import OpenRouterToolAgent
        from resto.adapters.llm.config import MissingApiKeyError, load_llm_config

        try:
            config = load_llm_config()
        except MissingApiKeyError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        db = SqliteDatabase(args.db)
        budget = Budget(config.max_steps, config.max_output_tokens, AGENT_SECONDS)
        tracer = JsonlTracer(args.out / "traces")
        agent = OpenRouterToolAgent(config, tracer=tracer)
        deps = build_deps(db=db, agent=agent, budget=budget, tracer=tracer, out_dir=args.out)
    try:
        study = run_study(args.text, deps, mode=mode)
    except ParserFailed as e:
        print(f"error: no study was created: {e}", file=sys.stderr)
        return 1
    finally:
        if db is not None:
            db.close()
    print(f"study {study.study_id}: {study.status}")
    return 0 if study.status is StudyStatus.COMPLETED else 1


if __name__ == "__main__":
    sys.exit(main())
