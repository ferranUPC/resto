"""The network, demand and reroute promoters are pending until E6.1 and E7.1: each raises the
`NotImplementedError` the Executor reports as an infrastructure failure."""

from __future__ import annotations

from typing import Any

import pytest

from resto.application.ports.llm import AgentRun, StopReason
from resto.application.promoters.demand import DemandPromoter
from resto.application.promoters.network import NetworkPromoter
from resto.application.promoters.reroute import ReroutePromoter
from resto.domain.value_objects.step_record import Usage
from resto.domain.value_objects.tasks import ObtainDemandTask, ObtainNetworkTask
from tests.unit.domain._samples import demand, network

RUN: AgentRun[Any] = AgentRun(
    output=None, tool_calls=(), usage=Usage(), stop_reason=StopReason.OUTPUT
)


def test_the_network_promotion_is_pending_until_e6_1() -> None:
    task = ObtainNetworkTask(network_ref="dev-net", max_rounds=1)

    with pytest.raises(NotImplementedError, match=r"the network promotion .* \(E6\.1\)"):
        NetworkPromoter().promote(RUN, task)


def test_the_demand_promotion_is_pending_until_e7_1() -> None:
    task = ObtainDemandTask(network_id="abc123", seed=0, max_calibration_rounds=1)

    with pytest.raises(NotImplementedError, match=r"the demand promotion .* \(E7\.1\)"):
        DemandPromoter().promote(RUN, task)


def test_the_reroute_promotion_is_pending_until_e7_1() -> None:
    with pytest.raises(NotImplementedError, match=r"the reroute_demand .* \(E7\.1\)"):
        ReroutePromoter().promote(demand(), network())
