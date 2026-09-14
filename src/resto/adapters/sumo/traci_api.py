"""Real implementation behind `resto.traci_api` (DoD §4.9, work-plan E1.2, ADR-0005).

Global module state, deliberately not a class: this is the module Builder-authored scripts call
bare (`close_lane("B0C0_1")`), the same way the `traci` package itself is a global-connection
module - there is no object to thread through a generated script. `start()` opens a TraCI session
and resets `applied_actions`/registered rules; `close()` ends it. The Simulation Runner (E2.5)
calls `start()`/`close()` around executing a script; a script itself only ever calls the
primitives and the declarative helpers below.

Every primitive raises `traci.TraCIException` on an unknown edge/lane/TLS id - a thin passthrough
to TraCI, same convention as `adapters/sumo/netxml.py`'s `KeyError`. Every mutating primitive
(`close_lane`, `open_lane`, `set_speed`, `set_tls_program`) logs one `AppliedAction` with
`origin = CODE` when called directly, `origin = RULE` when fired by `run()` from an `at_time`/
`when` registration. `step` is not logged - it advances the clock, it is not an intervention.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from typing import Any

import traci

from resto.domain.value_objects.applied_action import ActionOrigin, AppliedAction
from resto.domain.value_objects.traci_script import DeclaredRule

_applied_actions: list[AppliedAction] = []
_at_time_rules: list[list[Any]] = []  # each: [t, action, fired]
_when_rules: list[list[Any]] = []  # each: [condition, action, was_true]
_current_origin: ActionOrigin = ActionOrigin.CODE
_lane_permission_snapshots: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {}


def start(sumo_cmd: list[str]) -> None:
    """Opens a TraCI session, e.g. `start(["sumo", "--net-file", "n.net.xml", ...])`.

    Resets `applied_actions()`, every `at_time`/`when` registration, and every pending
    `close_lane` permission snapshot (see `open_lane`).
    """
    global _applied_actions, _at_time_rules, _when_rules, _current_origin
    global _lane_permission_snapshots
    _applied_actions = []
    _at_time_rules = []
    _when_rules = []
    _current_origin = ActionOrigin.CODE
    _lane_permission_snapshots = {}
    traci.start(sumo_cmd)


def close() -> None:
    """Ends the current TraCI session."""
    traci.close()


def applied_actions() -> tuple[AppliedAction, ...]:
    return tuple(_applied_actions)


def _log(action: str, params: Mapping[str, Any]) -> None:
    _applied_actions.append(
        AppliedAction(
            step=int(traci.simulation.getTime()),
            action=action,
            origin=_current_origin,
            params=dict(params),
        )
    )


# --- primitives (work-plan E1.2) --------------------------------------------------------


def close_lane(lane_id: str) -> None:
    """Disallows every vehicle class on `lane_id`, remembering its prior permissions so a
    later `open_lane` can restore them exactly (a bus-only lane reopens bus-only, not wide open).
    Only the first `close_lane` of a given `lane_id` in a session snapshots anything - a second
    `close_lane` without an intervening `open_lane` is a no-op on the snapshot, so it can't
    overwrite the true original with the already-closed state.

    Example: close_lane("B0C0_1")

    Raises:
        traci.TraCIException: `lane_id` is not known.
    """
    if lane_id not in _lane_permission_snapshots:
        _lane_permission_snapshots[lane_id] = (
            traci.lane.getAllowed(lane_id),
            traci.lane.getDisallowed(lane_id),
        )
    traci.lane.setDisallowed(lane_id, ["all"])
    _log("close_lane", {"lane_id": lane_id})


def open_lane(lane_id: str) -> None:
    """Restores `lane_id`'s permissions to whatever they were before the last `close_lane` in
    this session (verified against SUMO 1.27.1: snapshot + `setAllowed`/`setDisallowed` round-
    trips both an unrestricted lane and a bespoke one, e.g. bus-only, exactly). If `lane_id` was
    never closed in this session, resets it to no restriction instead.

    Example: open_lane("B0C0_1")

    Raises:
        traci.TraCIException: `lane_id` is not known.
    """
    allowed, disallowed = _lane_permission_snapshots.pop(lane_id, ((), ()))
    if allowed:
        traci.lane.setAllowed(lane_id, list(allowed))
    elif disallowed:
        traci.lane.setDisallowed(lane_id, list(disallowed))
    else:
        traci.lane.setDisallowed(lane_id, [])
    _log("open_lane", {"lane_id": lane_id})


def set_speed(edge_id: str, speed: float) -> None:
    """Sets the max speed (m/s) of every lane on `edge_id`.

    Example: set_speed("C0D0", 5.0)

    Raises:
        traci.TraCIException: `edge_id` is not known.
    """
    traci.edge.setMaxSpeed(edge_id, speed)
    _log("set_speed", {"edge_id": edge_id, "speed": speed})


def set_tls_program(tls_id: str, program_id: str) -> None:
    """Switches `tls_id` to program `program_id`.

    Example: set_tls_program("A2", "0")

    Raises:
        traci.TraCIException: `tls_id` or `program_id` is not known.
    """
    traci.trafficlight.setProgram(tls_id, program_id)
    _log("set_tls_program", {"tls_id": tls_id, "program_id": program_id})


def get_edge_occupancy(edge_id: str) -> float:
    """Fraction (0-1) of `edge_id` occupied by vehicles over the last simulation step.

    Example: get_edge_occupancy("C0D0") -> 0.12

    Raises:
        traci.TraCIException: `edge_id` is not known.
    """
    return traci.edge.getLastStepOccupancy(edge_id)


def get_edge_speed(edge_id: str) -> float:
    """Mean vehicle speed (m/s) on `edge_id` over the last simulation step.

    Example: get_edge_speed("C0D0") -> 9.2

    Raises:
        traci.TraCIException: `edge_id` is not known.
    """
    return traci.edge.getLastStepMeanSpeed(edge_id)


def get_vehicle_count(edge_id: str) -> int:
    """Number of vehicles on `edge_id` over the last simulation step.

    Example: get_vehicle_count("C0D0") -> 3

    Raises:
        traci.TraCIException: `edge_id` is not known.
    """
    return traci.edge.getLastStepVehicleNumber(edge_id)


def step(n: int = 1) -> None:
    """Advances the simulation by `n` steps. Not logged to `applied_actions` - clock
    advancement is not an intervention.

    Example: step()  # one step; step(10) for ten
    """
    for _ in range(n):
        traci.simulationStep()


# --- declarative registration (ADR-0005) ------------------------------------------------


def at_time(t: float, action: Callable[[], Any]) -> None:
    """Registers `action` to fire once, the first time `run()` observes simulation time >= t.

    Example: at_time(3600, lambda: close_lane("B0C0_1"))
    """
    _at_time_rules.append([t, action, False])


def when(condition: Callable[[], bool], action: Callable[[], Any]) -> None:
    """Registers `action` to fire on the rising edge of `condition` (False -> True) while
    `run()` is stepping - once per crossing, not on every step `condition` stays True.

    Example: when(lambda: get_edge_occupancy("C0D0") > 0.8, lambda: set_speed("C0D0", 5.0))
    """
    _when_rules.append([condition, action, False])


def registered_rules() -> tuple[DeclaredRule, ...]:
    """`DeclaredRule`s for every current `at_time`/`when` registration.

    Feeds `TraciScript.declared_rules`.
    """
    rules = [
        DeclaredRule(trigger=f"at_time({t})", action=_describe(action))
        for t, action, _fired in _at_time_rules
    ]
    rules += [
        DeclaredRule(trigger=_describe(condition), action=_describe(action))
        for condition, action, _was_true in _when_rules
    ]
    return tuple(rules)


def _describe(fn: Callable[..., Any]) -> str:
    """A description of `fn`, never `repr()` (bakes in a memory address, breaking the authoring-
    determinism criterion: identical script, 3 runs -> identical `declared_rules[]`).

    Named functions: `inspect.getsource` is unambiguous - a `def` is exactly one function - so
    the full source is used. Lambdas are different: `inspect.getsource` returns the *whole source
    line*, which is wrong whenever two lambdas share a line (`when(lambda: ..., lambda: ...)`,
    exactly the style ADR-0005's own examples use) - both would get identical, misleading text.
    Falls back to a `file:line` marker for those instead; prefer named functions over lambdas in
    a script wherever the registered rule matters to an audit trail.
    """
    name = getattr(fn, "__name__", "<anonymous>")
    if name != "<lambda>":
        try:
            return inspect.getsource(fn).strip()
        except (OSError, TypeError):
            return name
    code = fn.__code__
    return f"<lambda {code.co_filename}:{code.co_firstlineno}>"


def _fire(action: Callable[[], Any]) -> None:
    global _current_origin
    _current_origin = ActionOrigin.RULE
    try:
        action()
    finally:
        _current_origin = ActionOrigin.CODE


def run(until: float | None = None) -> None:
    """Steps the simulation, firing registered `at_time`/`when` rules, until `until` (simulation
    time) is reached - or, if `until` is None, until no more vehicles are expected
    (`traci.simulation.getMinExpectedNumber() == 0`).

    Example: run(until=3600)  # or run() to drain the route file
    """
    while _should_continue(until):
        step()
        now = traci.simulation.getTime()
        for rule in _at_time_rules:
            t, action, fired = rule
            if not fired and now >= t:
                rule[2] = True
                _fire(action)
        for rule in _when_rules:
            condition, action, was_true = rule
            is_true = bool(condition())
            if is_true and not was_true:
                _fire(action)
            rule[2] = is_true


def _should_continue(until: float | None) -> bool:
    if until is not None:
        return traci.simulation.getTime() < until
    return traci.simulation.getMinExpectedNumber() > 0
