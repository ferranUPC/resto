"""Local HTTP server for the task tree: binds to 127.0.0.1, re-reads the files on each request."""

from __future__ import annotations

import argparse
import contextlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

from task_tree.tree import build_tree, task_detail, ticket_detail

ROOT = Path(__file__).resolve().parent.parent
PAGE = Path(__file__).with_name("page.html")


def make_server(
    scratch: Path, tracker: Path, port: int = 0, plan: Path | None = None
) -> ThreadingHTTPServer:
    plan_path = plan or tracker.with_name("tfm-work-plan.md")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path == "/":
                self._send(200, "text/html; charset=utf-8", PAGE.read_bytes())
            elif path == "/api/tree":
                body = json.dumps(build_tree(scratch, tracker, plan_path)).encode("utf-8")
                self._send(200, "application/json", body)
            elif path.startswith("/api/task/"):
                parts = [unquote(p) for p in path[len("/api/task/") :].split("/")]
                if len(parts) == 1:
                    detail = task_detail(scratch, tracker, plan_path, parts[0])
                elif len(parts) == 3 and parts[1] == "ticket":
                    detail = ticket_detail(scratch, tracker, parts[0], parts[2])
                else:
                    detail = None
                if detail is None:
                    self._send(404, "text/plain; charset=utf-8", b"not found")
                else:
                    self._send(200, "application/json", json.dumps(detail).encode("utf-8"))
            else:
                self._send(404, "text/plain; charset=utf-8", b"not found")

        def _send(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the RESTO task tree on 127.0.0.1.")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = make_server(ROOT / ".scratch", ROOT / "docs" / "progress-tracker.md", args.port,
                         ROOT / "docs" / "tfm-work-plan.md")
    print(f"Task tree at http://127.0.0.1:{server.server_port}/  (Ctrl+C to stop)")
    with contextlib.suppress(KeyboardInterrupt):
        server.serve_forever()
