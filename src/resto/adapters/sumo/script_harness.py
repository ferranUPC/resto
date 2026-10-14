"""Harness around a generated `script.py` (ADR-0044): starts the TraCI session, executes the script
file, closes the session and writes the applied actions as JSON into the run directory.

The script ends in `run()` and never calls `start` or `close`; the session's lifecycle belongs to
this module. `python -m resto.adapters.sumo.script_harness <script> <out_dir> <sumo command...>` is
the entry point the online runner starts as a subprocess, so `traci_api`'s global state starts clean
each run and a crash does not take the study down. On an exception it prints the traceback to stderr
and exits non-zero. The applied actions are written only after the script finished.
"""

from __future__ import annotations

import runpy
import sys
import traceback
from collections.abc import Callable, Sequence
from pathlib import Path

from resto import traci_api
from resto.application.schemas import adapter_for
from resto.domain.value_objects.applied_action import AppliedAction

APPLIED_ACTIONS_FILE = "applied_actions.json"

_ACTIONS = adapter_for(tuple[AppliedAction, ...])


def run_script(
    sumo_cmd: Sequence[str],
    script_path: Path,
    out_dir: Path,
    setup: Callable[[], None] | None = None,
) -> None:
    """Starts SUMO with `sumo_cmd`, executes `script_path`, closes the session and writes
    `out_dir/APPLIED_ACTIONS_FILE`. `setup` runs after the session starts and before the script,
    for a caller that registers its own rules (tests read state back that way).

    Raises whatever the script raises; the session is closed first and no file is written.
    """
    traci_api.start(list(sumo_cmd))
    try:
        if setup is not None:
            setup()
        runpy.run_path(str(script_path), run_name="__main__")
        actions = traci_api.applied_actions()
    finally:
        traci_api.close()
    (out_dir / APPLIED_ACTIONS_FILE).write_bytes(_ACTIONS.dump_json(actions))


def read_applied_actions(out_dir: Path) -> tuple[AppliedAction, ...]:
    """The actions `run_script` wrote into `out_dir`.

    Raises:
        FileNotFoundError: the harness did not get to write the file.
    """
    result: tuple[AppliedAction, ...] = _ACTIONS.validate_json(
        (out_dir / APPLIED_ACTIONS_FILE).read_bytes()
    )
    return result


def main(argv: Sequence[str]) -> int:
    if len(argv) < 3:
        print("usage: script_harness <script> <out_dir> <sumo command...>", file=sys.stderr)
        return 2
    script, out_dir, *sumo_cmd = argv
    try:
        run_script(sumo_cmd, Path(script), Path(out_dir))
    except BaseException:  # noqa: BLE001 - whatever the script did, the runner reads stderr
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
