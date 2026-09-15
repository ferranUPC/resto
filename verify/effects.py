"""The `verify_*` functions themselves (work-plan E2.4, DoD §4.5) plus the one piece of test
machinery every `signal_program` check needs: a re-run of the scenario with an extra
`SaveTLSSwitchTimes` additional file, since that log is not part of what the Scenario Builder
writes (it is a verification-time concern, not a simulation input) - `run_with_tls_switch_log`
does that re-run.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from resto.adapters.sumo.outputs import EdgeInterval, TlsSwitch, parse_tls_switches
from resto.adapters.sumo.writers.sumocfg import (
    SumocfgFileWriter,
    parse_settings,
    with_additional,
)
from resto.application.ports.sumo import RunOutput, SumoRunner
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.time_window import TimeWindow


@dataclass(frozen=True, slots=True)
class EffectResult:
    """Whether one intervention's observable effect matched the DoD §4.5 bar, and why."""

    ok: bool
    reason: str


def _interval(
    edgedata: tuple[EdgeInterval, ...], edge_id: str, window: TimeWindow
) -> EdgeInterval:
    """The one `EdgeInterval` for `edge_id` whose own `[begin, end)` exactly equals `window`.

    Raises:
        ValueError: no interval lines up with `window` exactly - the Runner's fixed
            `EDGEDATA_PERIOD_S` (currently 300s) does not divide the intervention's own window,
            so no single interval's flow can be attributed to "inside the window" alone (see
            this package's `__init__.py`). Pick a window aligned to that period, or re-run with a
            finer edgedata period, rather than trust a misaligned reading.
    """
    matches = [
        i
        for i in edgedata
        if i.edge_id == edge_id and i.begin == window.start and i.end == window.end
    ]
    if not matches:
        raise ValueError(
            f"no edgedata interval for {edge_id!r} spans exactly [{window.start}, {window.end}) "
            "- window is not aligned to the edgedata period"
        )
    return matches[0]


def _outside_intervals(
    edgedata: tuple[EdgeInterval, ...], edge_id: str, window: TimeWindow
) -> tuple[EdgeInterval, ...]:
    return tuple(
        i
        for i in edgedata
        if i.edge_id == edge_id and not (i.begin == window.start and i.end == window.end)
    )


def verify_edge_flow(
    edgedata: tuple[EdgeInterval, ...], edge_id: str, window: TimeWindow
) -> EffectResult:
    """`lane_closure`/`edge_closure`'s shared bar (DoD §4.5): zero flow through `edge_id` during
    `window`, nonzero in at least one interval outside it (proves the closure had an effect at
    all, not just that the edge happens to be unused)."""
    inside = _interval(edgedata, edge_id, window)
    if inside.entered != 0 or inside.sampled_seconds != 0:
        return EffectResult(
            ok=False,
            reason=f"{edge_id} carried traffic inside the window: entered={inside.entered}",
        )
    outside = _outside_intervals(edgedata, edge_id, window)
    if not any(o.entered > 0 for o in outside):
        return EffectResult(
            ok=False, reason=f"{edge_id} carried no traffic outside the window either"
        )
    return EffectResult(ok=True, reason="zero flow inside the window, nonzero outside")


def verify_completion_rate(departed: int, scheduled: int, threshold: float = 0.90) -> EffectResult:
    """DoD §4.5's `lane_closure` "≥ 90 % rerouted" bar, approximated as the fraction of every
    vehicle scheduled in the scenario's demand that still departed (a proxy: it is cheap to
    compute from `Kpis.departed` alone, without a second baseline run, at the cost of counting
    the *whole* scenario's completion rather than only the vehicles that would have used the
    closed edge specifically - the bank-level DoD threshold this feeds is itself an aggregate,
    not a proof obligation for this one number)."""
    if scheduled == 0:
        raise ValueError("scheduled must be > 0")
    rate = departed / scheduled
    ok = rate >= threshold
    return EffectResult(
        ok=ok, reason=f"{departed}/{scheduled} departed ({rate:.0%}, need >={threshold:.0%})"
    )


def count_scheduled_vehicles(route_or_trips_path: Path, before: float | None = None) -> int:
    """Number of `<vehicle>`/`<trip>` elements in a routes or trips file, counting only those
    with `depart < before` when given - a run's own `end` truncates which of the file's vehicles
    it ever attempts to insert, so `verify_completion_rate`'s `scheduled` must be scoped the same
    way or it understates the completion rate for any run shorter than the full demand file."""
    root = ET.parse(route_or_trips_path).getroot()
    elements = root.findall("vehicle") + root.findall("trip")
    if before is None:
        return len(elements)
    return sum(1 for e in elements if float(e.get("depart", "0")) < before)


def verify_speed_limit(
    edgedata: tuple[EdgeInterval, ...],
    edge_id: str,
    window: TimeWindow,
    limit_mps: float,
    tolerance: float = 0.10,
) -> EffectResult:
    """`speed_limit`'s DoD §4.5 bar: mean speed on `edge_id` during `window` at or below
    `limit_mps * (1 + tolerance)`."""
    inside = _interval(edgedata, edge_id, window)
    if inside.speed is None:
        raise ValueError(f"{edge_id} carried no traffic inside the window - nothing to measure")
    ceiling = limit_mps * (1 + tolerance)
    ok = inside.speed <= ceiling
    return EffectResult(
        ok=ok, reason=f"mean speed {inside.speed:.2f} m/s (ceiling {ceiling:.2f})"
    )


def _overlap(switch: TlsSwitch, window: TimeWindow) -> float:
    return max(0.0, min(switch.end, window.end) - max(switch.begin, window.start))


def verify_signal_program(
    tls_switches: tuple[TlsSwitch, ...],
    tls_id: str,
    window: TimeWindow,
    program_id: str,
    original_program_id: str,
    majority: float = 0.5,
) -> EffectResult:
    """`signal_program`'s DoD §4.5 bar ("phases match"): `program_id` covers most of `window`,
    and `original_program_id` is active again at some point after it.

    A WAUT can only switch at a phase boundary (ADR-0007), so the *actual* active-program span
    is snapped a little later than `window.start` and a little later than `window.end` too - an
    exact `[window.start, window.end)` match would wrongly fail on that snap (found empirically
    while building this check, see this package's `__init__.py`). `majority` coverage of the
    window, rather than 100%, absorbs that without pretending to sub-second precision.
    """
    relevant = tuple(s for s in tls_switches if s.tls_id == tls_id)
    duration = window.end - window.start
    covered = sum(_overlap(s, window) for s in relevant if s.program_id == program_id)
    coverage = covered / duration if duration else 0.0
    if coverage < majority:
        return EffectResult(
            ok=False, reason=f"{program_id} covered only {coverage:.0%} of the window"
        )
    reverted = any(s.program_id == original_program_id and s.begin >= window.end for s in relevant)
    if not reverted:
        return EffectResult(
            ok=False, reason=f"never reverted to {original_program_id!r} after the window"
        )
    return EffectResult(
        ok=True, reason=f"{program_id} covered {coverage:.0%} of the window, reverted after"
    )


def verify_demand_scale(
    departed: int, expected_trip_count: int, tolerance: float = 0.05
) -> EffectResult:
    """`demand_scale`'s DoD §4.5 bar: departed count within `tolerance` of the scaled trip
    count (`round(original_count * factor)`, `SumoDemandScaler`'s own target)."""
    if expected_trip_count == 0:
        raise ValueError("expected_trip_count must be > 0")
    error = abs(departed - expected_trip_count) / expected_trip_count
    ok = error <= tolerance
    return EffectResult(
        ok=ok, reason=f"departed={departed}, expected={expected_trip_count} ({error:.1%} error)"
    )


def write_tls_switch_log(out_dir: Path, tls_id: str, dest_name: str = "tls_switch.xml") -> Path:
    """A `<timedEvent type="SaveTLSSwitchTimes">` additional file for `tls_id` - not something
    the Scenario Builder ever writes (`additional_file.xsd`'s `timedEventType`); only
    verification needs to observe program switches, so only verification asks for the log."""
    root = ET.Element("additional")
    ET.SubElement(root, "timedEvent", type="SaveTLSSwitchTimes", source=tls_id, dest=dest_name)
    path = out_dir / "tls_switch_log.add.xml"
    ET.indent(root, space="    ")
    path.write_text(ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")
    return path


def run_with_tls_switch_log(
    runner: SumoRunner, sumocfg: ArtifactRef, tls_id: str, seed: int, out_dir: Path
) -> tuple[RunOutput, tuple[TlsSwitch, ...]]:
    """Re-runs `sumocfg` with an extra `SaveTLSSwitchTimes` additional file for `tls_id`, and
    parses the resulting log - the one piece of E2.4 setup a `signal_program` check needs beyond
    what `run_batch` already produces."""
    log_path = write_tls_switch_log(out_dir, tls_id)
    settings = with_additional(parse_settings(sumocfg.path), log_path)
    logged_cfg = SumocfgFileWriter().write(settings, out_dir, "scenario_with_log.sumocfg")
    output = runner.run_batch(logged_cfg, seed, out_dir / "run")
    if not output.ok:
        return output, ()
    switch_log = out_dir / "tls_switch.xml"
    return output, parse_tls_switches(switch_log)
