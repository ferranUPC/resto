"""A loopback HTTP server that answers with saved responses and records each request, standing
in for Nominatim and Overpass (the root `conftest` leaves only loopback open)."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).parent / "fixtures"


@dataclass(frozen=True)
class Reply:
    body: bytes
    status: int = 200
    content_type: str = "application/json"
    delay_s: float = 0.0

    @staticmethod
    def fixture(name: str, **kwargs: Any) -> Reply:
        return Reply((FIXTURES / name).read_bytes(), **kwargs)


@dataclass(frozen=True)
class Received:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes
    at: float


@dataclass
class FakeService:
    url: str
    replies: list[Reply] = field(default_factory=list)
    received: list[Received] = field(default_factory=list)

    def answer(self, *replies: Reply) -> None:
        """Queue replies; the last one repeats once the queue is spent."""
        self.replies.extend(replies)


@contextmanager
def fake_service() -> Iterator[FakeService]:
    service = FakeService(url="")

    class Handler(BaseHTTPRequestHandler):
        def _handle(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            service.received.append(
                Received(
                    self.command,
                    self.path,
                    {k.lower(): v for k, v in self.headers.items()},
                    body,
                    time.monotonic(),
                )
            )
            reply = service.replies[min(len(service.received), len(service.replies)) - 1]
            if reply.delay_s:
                time.sleep(reply.delay_s)
            try:
                self.send_response(reply.status)
                self.send_header("Content-Type", reply.content_type)
                self.send_header("Content-Length", str(len(reply.body)))
                self.end_headers()
                self.wfile.write(reply.body)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the client gave up (timeout test)

        do_GET = _handle  # noqa: N815
        do_POST = _handle  # noqa: N815

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    service.url = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield service
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
