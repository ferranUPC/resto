"""Root pytest configuration shared by `tests/` and `conformance/`.

One session-wide guard: the SUMO binary on PATH must be the pinned `resto.domain.constants.
SUMO_VERSION`. Every `SimulationResult.sumo_version` is asserted against that constant, and a
different SUMO produces non-reproducible `tripinfo`/`edgedata` output (ADR-0010) - so a mismatch
must fail the run loudly at collection time, not surface as a puzzling test failure later. A
`SUMO_HOME` pointing at some other install is the usual way versions get mixed (CLAUDE.md), so
it is reported as a warning when set, even if the version happens to match today.
"""

from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import warnings
from typing import Any

import pytest

from resto.domain.constants import SUMO_VERSION


def _installed_sumo_version() -> str | None:
    binary = shutil.which("sumo")
    if binary is None:
        return None
    output = subprocess.run([binary, "--version"], capture_output=True, text=True, check=False)
    match = re.search(r"\b(\d+\.\d+\.\d+)\b", output.stdout)
    return match.group(1) if match else None


@pytest.fixture(scope="session", autouse=True)
def _pinned_sumo_version() -> None:
    installed = _installed_sumo_version()
    if installed is None:
        pytest.fail("no `sumo` binary on PATH - activate the `resto` env (eclipse-sumo is pinned)")
    if installed != SUMO_VERSION:
        pytest.fail(
            f"sumo on PATH is {installed}, but resto pins {SUMO_VERSION} "
            "(ADR-0010) - check SUMO_HOME / PATH for a stray install"
        )
    if os.environ.get("SUMO_HOME"):
        warnings.warn(
            f"SUMO_HOME is set ({os.environ['SUMO_HOME']}); the pinned PyPI SUMO needs it unset "
            "so binaries and Python bindings cannot drift apart (see CLAUDE.md)",
            stacklevel=1,
        )


_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", ""}


@pytest.fixture(autouse=True)
def _no_external_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any test that opens a non-loopback connection (no OpenRouter call from `pytest`).

    Real paid calls are reserved for explicit evaluation runs (docs/llm-cost-policy.md). Loopback
    stays open: TraCI and the MCP in-process servers talk over localhost sockets.
    """
    real_connect = socket.socket.connect
    real_getaddrinfo = socket.getaddrinfo

    def guarded_connect(self: socket.socket, address: Any) -> None:
        if self.family in (socket.AF_INET, socket.AF_INET6) and address[0] not in _LOOPBACK_HOSTS:
            raise RuntimeError(f"network blocked in tests: connect to {address!r}")
        real_connect(self, address)

    def guarded_getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(host, str) and host not in _LOOPBACK_HOSTS:
            raise RuntimeError(f"network blocked in tests: DNS lookup of {host!r}")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
