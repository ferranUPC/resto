"""A minimal golden path through `RunStudy` that ends in a `Network` from `obtain_network`
(E6.1/08).

The study names a network that is not stored ("a 3 by 3 grid"). The Network Author, its tools,
`netgenerate`, the promoter and its replay are the production ones (SUMO 1.27.1); only the model
is scripted, and the OSM source and geocoder are fakes that the path never reaches. The path
asserts the outcome (ADR-0043): the study completes, uses the expected network and simulates
nothing. It does not say which tools the agent called.

It lives beside the unit tests and not in `golden/paths`: `golden.run --setup fake` runs on
`World`'s fake promoters, which cannot produce a real network. The reference id is the content
hash of a 3 by 3 grid written by the pinned SUMO (ADR-0010); a SUMO upgrade regenerates it.
"""

from __future__ import annotations

from pathlib import Path

import sumolib.net
from golden.framework import (
    ExpectedOutcome,
    ExpectedResolution,
    GoldenPath,
    Run,
    SameNetworkId,
    SimulationsExpectation,
    check,
)

from resto.domain.entities.study import StudyResolution
from resto.domain.value_objects.network_source import GridNetwork
from tests.unit.application.run_study.test_network_author_steps import (
    Setup,
    grid_script,
    obtain_plan,
)

GRID_3X3_ID = "507b98c9b8d32748049c808600571243998e209788e3d7891f53a8c900207e4a"

PATH = GoldenPath(
    name="network-author-minimal",
    request="a 3 by 3 grid",
    expected=ExpectedOutcome(
        resolution=ExpectedResolution(StudyResolution.COMPLETED),
        network=SameNetworkId(GRID_3X3_ID),
        simulations=SimulationsExpectation((), max_new=0),
    ),
)


class RealNetworkSetup:
    """Runs the path over the real Network Author with a scripted model. Deterministic, so the
    repetitions must also equal each other."""

    repetitions = 2
    compare_repetitions = True

    def __init__(self, tmp_path: Path) -> None:
        self._tmp = tmp_path
        self.setups: list[Setup] = []

    def run(self, path: GoldenPath) -> Run:
        setup = Setup(
            self._tmp / f"repetition-{len(self.setups)}",
            grid_script,
            plan=obtain_plan(path.request),
        )
        self.setups.append(setup)
        study = setup.run()
        return Run(study, tuple(setup.world.tracer.events))


def test_a_named_grid_becomes_a_network_by_the_production_path(tmp_path: Path) -> None:
    setup = RealNetworkSetup(tmp_path)

    diff = check(setup, PATH)

    assert diff.ok, diff.render()
    world = setup.setups[0].world
    network = world.networks.get(GRID_3X3_ID)
    assert network is not None and network.recipe.source == GridNetwork(3, 3)
    assert len(sumolib.net.readNet(str(network.net_xml.path)).getNodes()) >= 9
