"""`FakeSetup`: a golden path run over the shared `World` with scripted agents."""

from __future__ import annotations

import tempfile
from collections.abc import Mapping
from pathlib import Path

from tests.unit.application._world import World

from golden.framework.expected import GoldenPath
from golden.framework.setup import Run
from golden.framework.simulations import Stored
from golden.setups.fake import scripts
from golden.setups.fake.script import AgentScript
from resto.domain.entities.study import Study

REPETITIONS = 3


class FakeSetup:
    def __init__(self, scripts_by_path: Mapping[str, AgentScript] | None = None) -> None:
        """`scripts_by_path` replaces the discovered scripts; tests use it for throwaway paths."""
        self._scripts = scripts_by_path

    @property
    def repetitions(self) -> int:
        return REPETITIONS

    @property
    def compare_repetitions(self) -> bool:
        return True

    def _script(self, path: GoldenPath) -> AgentScript:
        available = self._scripts if self._scripts is not None else scripts.discover()
        try:
            return available[path.name]
        except KeyError:
            raise LookupError(
                f"no agent script for golden path {path.name!r}: "
                f"add golden/setups/fake/scripts/{path.name}.py defining SCRIPT"
            ) from None

    def run(self, path: GoldenPath) -> Run:
        script = self._script(path)
        with tempfile.TemporaryDirectory() as tmp:
            world = World(Path(tmp), **script.world_args())
            for stored in path.prior.stored:
                world.store_scenario(stored.interventions, stored.seeds)
            study = world.run_study().execute(path.request)
            return Run(study, tuple(world.tracer.events), _stored(world, study))


def _stored(world: World, study: Study) -> Stored:
    """The scenarios, results and demands the study's experiments point to."""
    experiments = [e for phase in study.phases for e in phase.experiments]
    scenarios = {e.scenario_id: s for e in experiments if (s := world.scenarios.get(e.scenario_id))}
    results = {
        r: found
        for e in experiments
        for r in e.result_ids
        if (found := world.results.get(r)) is not None
    }
    demands = {s.demand_id: d for s in scenarios.values() if (d := world.demands.get(s.demand_id))}
    return Stored(scenarios, results, demands)
