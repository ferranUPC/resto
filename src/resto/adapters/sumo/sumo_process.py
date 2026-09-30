"""The one place that launches SUMO tools (refactor r6).

`launch` runs a tool (`sumo`, `duarouter`, ...) and returns a `LaunchResult`. A failure to start
or a non-zero exit is a result with `ok` false and a message, never an exception, so each caller
translates it to its own step error. The one exception is a SUMO version other than
`SUMO_VERSION`: the first launch of a tool in a process runs `<tool> --version`, caches what it
reads, and raises `SumoVersionError` before launching anything if it differs. There is no
warning mode, because other versions can produce non-reproducible output (CLAUDE.md).

The seed is a required argument and the module decides where it goes. `sumo` reads it from the
run configuration, which the caller renders, so nothing is added to its command line. Every other
tool gets `--seed <n>`.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from resto.domain.constants import SUMO_VERSION

_SEED_IN_CONFIG = frozenset({"sumo"})
_VERSION_RE = re.compile(r"\b(\d+\.\d+\.\d+)\b")

_version_cache: dict[str, str] = {}


class SumoVersionError(RuntimeError):
    """The SUMO binary on the PATH is not the pinned version."""


@dataclass(frozen=True)
class LaunchResult:
    ok: bool
    message: str
    files: tuple[Path, ...] = ()


def launch(tool: str, args: Sequence[str], cwd: Path, seed: int) -> LaunchResult:
    """Runs `tool` with `args` in `cwd`; `files` are the files the tool created or changed there.

    Raises:
        SumoVersionError: `tool --version` is not `SUMO_VERSION`.
    """
    if tool not in _version_cache:
        try:
            _probe_version(tool, cwd)
        except _ProbeFailed as failure:
            return LaunchResult(ok=False, message=str(failure))
    _require_pinned(tool)

    command = [tool, *args]
    if tool not in _SEED_IN_CONFIG:
        command += ["--seed", str(seed)]
    before = _snapshot(cwd)
    try:
        proc = subprocess.run(command, capture_output=True, text=True, cwd=cwd)
    except OSError as exc:
        return LaunchResult(ok=False, message=str(exc))
    if proc.returncode != 0:
        return LaunchResult(ok=False, message=_failure_message(tool, proc))
    after = _snapshot(cwd)
    changed = tuple(sorted(p for p, stamp in after.items() if before.get(p) != stamp))
    return LaunchResult(ok=True, message="", files=changed)


def checked_version(tool: str) -> str:
    """The version of `tool`, read once per process and known to be `SUMO_VERSION`.

    Raises:
        SumoVersionError: `tool` cannot be run, or its version is not `SUMO_VERSION`.
    """
    if tool not in _version_cache:
        try:
            _probe_version(tool, None)
        except _ProbeFailed as failure:
            raise SumoVersionError(f"cannot read the version of {tool}: {failure}") from failure
    _require_pinned(tool)
    return _version_cache[tool]


class _ProbeFailed(Exception):
    """`<tool> --version` could not run or exited non-zero; the text is the reason."""


def _probe_version(tool: str, cwd: Path | None) -> None:
    """Runs `<tool> --version` and caches what it reads."""
    try:
        proc = subprocess.run([tool, "--version"], capture_output=True, text=True, cwd=cwd)
    except OSError as exc:
        raise _ProbeFailed(str(exc)) from exc
    if proc.returncode != 0:
        raise _ProbeFailed(_failure_message(tool, proc))
    _version_cache[tool] = _read_version(tool, proc.stdout + proc.stderr)


def _require_pinned(tool: str) -> None:
    if _version_cache[tool] != SUMO_VERSION:
        raise SumoVersionError(
            f"{tool} is version {_version_cache[tool]}, this project requires {SUMO_VERSION}"
        )


def _read_version(tool: str, output: str) -> str:
    match = _VERSION_RE.search(output.strip().split("\n", 1)[0])
    if match is None:
        raise SumoVersionError(f"cannot read the version of {tool} from: {output.strip()[:200]!r}")
    return match.group(1)


def _snapshot(directory: Path) -> dict[Path, tuple[int, int]]:
    stamps = {}
    for path in directory.rglob("*"):
        if path.is_file():
            stat = path.stat()
            stamps[path] = (stat.st_mtime_ns, stat.st_size)
    return stamps


def _failure_message(tool: str, proc: subprocess.CompletedProcess[str]) -> str:
    """SUMO's own error lines, without the warnings that precede them; else all of stderr; else
    the exit code."""
    errors = [line for line in proc.stderr.splitlines() if line.startswith("Error")]
    message = "\n".join(errors) if errors else proc.stderr.strip()
    return message or f"{tool} exited with code {proc.returncode}"
