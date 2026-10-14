"""Harness around a generated `script.py` (ADR-0044): starts the TraCI session, executes the script
file, closes the session and writes the applied actions as JSON into the run directory.

The script ends in `run()` and never calls `start` or `close`; the session's lifecycle belongs to
the harness. `OnlineHarness` is the real run; `DryRunHarness` rehearses the script for the build's
check stage: `run()` is limited to `DRY_RUN_STEPS` steps, then every condition is evaluated once and
every action applied once, whatever its trigger. The session closes and nothing is written.

The online runner starts a harness as a subprocess (`python -m resto.adapters.sumo.script_harness`)
and sends a `HarnessRequest` as JSON on stdin, so `traci_api`'s global state starts clean each run
and a crash does not take the study down. On an exception the entry point prints the traceback to
stderr and exits non-zero.
"""

from __future__ import annotations

import runpy
import sys
import traceback
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from resto import traci_api
from resto.adapters.sumo import traci_api as harness_hooks
from resto.adapters.sumo.constants import APPLIED_ACTIONS_FILE, DRY_RUN_STEPS
from resto.application.schemas import adapter_for
from resto.domain.value_objects.applied_action import AppliedAction

_ACTIONS = adapter_for(tuple[AppliedAction, ...])


class OnlineHarness:
    """Starts SUMO with `sumo_command`, executes the script, closes the session and writes the
    applied actions. `end` is the run cfg's end time: `run()` stops there, as batch SUMO does.
    `on_start` is a test hook: it runs after the session starts and before the script, for a test
    that registers its own rules to read state back."""

    def __init__(
        self,
        sumo_command: Sequence[str],
        end: float | None = None,
        on_start: Callable[[], None] | None = None,
    ) -> None:
        self._sumo_command = list(sumo_command)
        self._end = end
        self._on_start = on_start

    def run(self, script: Path, out_dir: Path) -> None:
        """Raises whatever the script raises; the session is closed first and no file is written."""
        actions = self._execute(script)
        (out_dir / APPLIED_ACTIONS_FILE).write_bytes(_ACTIONS.dump_json(actions))

    def _execute(self, script: Path) -> tuple[AppliedAction, ...]:
        traci_api.start(self._sumo_command)
        try:
            if self._on_start is not None:
                self._on_start()
            if self._end is not None:
                harness_hooks.set_end_time(self._end)
            self._before_script()
            runpy.run_path(str(script), run_name="__main__")
            self._after_script()
            return traci_api.applied_actions()
        finally:
            traci_api.close()

    def _before_script(self) -> None:
        """Nothing for a real run."""

    def _after_script(self) -> None:
        """Nothing for a real run."""


class DryRunHarness(OnlineHarness):
    """Rehearses the script: `DRY_RUN_STEPS` steps, every rule forced once, nothing written."""

    def run(self, script: Path, out_dir: Path) -> None:
        self._execute(script)

    def _before_script(self) -> None:
        harness_hooks.set_step_limit(DRY_RUN_STEPS)

    def _after_script(self) -> None:
        harness_hooks.force_all_rules()


@dataclass(frozen=True)
class HarnessRequest:
    """What the launcher sends the harness subprocess as JSON on stdin."""

    sumo_command: tuple[str, ...]
    script: Path
    out_dir: Path
    end: float | None = None
    dry_run: bool = False

    def harness(self) -> OnlineHarness:
        return (DryRunHarness if self.dry_run else OnlineHarness)(self.sumo_command, self.end)


REQUEST = adapter_for(HarnessRequest)


def read_applied_actions(out_dir: Path) -> tuple[AppliedAction, ...]:
    """The actions `OnlineHarness.run` wrote into `out_dir`.

    Raises:
        FileNotFoundError: the harness did not get to write the file.
    """
    result: tuple[AppliedAction, ...] = _ACTIONS.validate_json(
        (out_dir / APPLIED_ACTIONS_FILE).read_bytes()
    )
    return result


if __name__ == "__main__":
    try:
        request: HarnessRequest = REQUEST.validate_json(sys.stdin.read())
        request.harness().run(request.script, request.out_dir)
    except BaseException:  # noqa: BLE001 - whatever the script did, the launcher reads stderr
        traceback.print_exc()
        sys.exit(1)
