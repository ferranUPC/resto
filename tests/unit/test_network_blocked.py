"""The autouse guard in the root conftest keeps `pytest` away from the real network."""

from __future__ import annotations

import socket

import pytest


def test_dns_lookup_of_an_external_host_is_blocked() -> None:
    with pytest.raises(RuntimeError, match="network blocked"):
        socket.getaddrinfo("openrouter.ai", 443)


def test_connecting_to_an_external_address_is_blocked() -> None:
    sock = socket.socket(socket.AF_INET)
    try:
        with pytest.raises(RuntimeError, match="network blocked"):
            sock.connect(("93.184.216.34", 443))
    finally:
        sock.close()


def test_loopback_stays_open() -> None:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        with socket.socket() as client:
            client.connect(server.getsockname())
