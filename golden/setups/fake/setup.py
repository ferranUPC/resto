"""`FakeSetup`: a golden path run over the shared `World` with scripted agents."""

from __future__ import annotations

import tempfile
from collections.abc import Mapping
from pathlib import Path

from tests.unit.application._world import World

from golden.framework.expected import GoldenPath
from golden.framework.setup import Run
from golden.setups.fake import scripts
from golden.setups.fake.script import AgentScript
from resto.application.use_cases.run_study import run_study

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
            study = run_study(path.request, world.deps, world.settings)
            return Run(study, tuple(world.tracer.events))
