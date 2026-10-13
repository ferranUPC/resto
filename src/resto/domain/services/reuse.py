"""What a study reuses instead of running or building again (ADR-0041 §6). The Executor loads the
stored values, these rules decide over them, and the Executor acts on the decision."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from resto.domain.entities.demand import Demand
from resto.domain.entities.network import Network
from resto.domain.entities.scenario import Scenario
from resto.domain.entities.simulation_result import RunMode, RunStatus, SimulationResult
from resto.domain.value_objects.outcomes import Found


def accepts_found_network(found: Found, stored: Network | None) -> bool:
    """A specialist's `Found` is accepted only when it names a stored network: `stored` is what the
    store holds under `found.id`, or none."""
    return stored is not None and stored.network_id == found.id


def accepts_found_demand(found: Found, stored: Demand | None, *, network_id: str) -> bool:
    """A specialist's `Found` is accepted only when it names a stored demand on the step's network
    `network_id`: `stored` is what the store holds under `found.id`, or none."""
    return stored is not None and stored.demand_id == found.id and stored.network_id == network_id


def reused_scenario_results(
    scenario: Scenario | None, stored: Iterable[SimulationResult]
) -> tuple[str, ...]:
    """The ids, by seed, of the ok results a `build_scenario` step reuses without calling the
    Scenario Builder (ADR-0037 §5): `scenario` is the one stored under the step's request hash, or
    none, and `stored` are its stored results. None means the scenario is built."""
    if scenario is None:
        return ()
    ok = sorted((r for r in stored if r.status is RunStatus.OK), key=lambda r: r.seed)
    return tuple(r.result_id for r in ok)


def reused_results(
    seeds: Sequence[int], stored: Iterable[SimulationResult]
) -> dict[int, SimulationResult]:
    """The stored result each of `seeds` reuses, so that a study never has a **Redundant
    simulation**. `stored` are the scenario's stored results: only an ok batch run stands for the
    run a `run_simulation` step asks for. A failed one may be run again."""
    wanted = set(seeds)
    return {
        r.seed: r
        for r in stored
        if r.seed in wanted and r.status is RunStatus.OK and r.mode is RunMode.BATCH
    }


def seeds_to_run(seeds: Sequence[int], stored: Iterable[SimulationResult]) -> tuple[int, ...]:
    """The seeds of `seeds`, in their order, that `stored` has no reusable result for."""
    reused = reused_results(seeds, stored)
    return tuple(s for s in seeds if s not in reused)
