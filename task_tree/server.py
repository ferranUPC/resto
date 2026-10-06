"""Local HTTP server for the task tree: binds to 127.0.0.1, re-reads the files on each request."""

from __future__ import annotations

import argparse
import contextlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

from task_tree.launch import Launcher, LaunchRejected, build_prompt, terminal_launcher
from task_tree.tree import build_tree, task_detail, ticket_detail

ROOT = Path(__file__).resolve().parent.parent
PAGE = Path(__file__).with_name("page.html")


def make_server(
    scratch: Path,
    tracker: Path,
    port: int = 0,
    plan: Path | None = None,
    launcher: Launcher = terminal_launcher,
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

        def do_POST(self) -> None:
            if self.path.split("?", 1)[0] != "/api/launch":
                self._send(404, "text/plain; charset=utf-8", b"not found")
                return
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
            content_type = (self.headers.get("Content-Type") or "").split(";")[0].strip()
            if host not in ("127.0.0.1", "localhost") or content_type != "application/json":
                # A browser cannot send this cross-origin without a preflight the server refuses,
                # and a rebound hostname fails the Host check.
                self._send(403, "text/plain; charset=utf-8", b"forbidden")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 0:
                    raise ValueError("negative Content-Length")
                body = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError("body must be an object")
                task_id, action, ticket = body.get("id"), body.get("action"), body.get("ticket")
                if not isinstance(task_id, str) or not isinstance(action, str):
                    raise ValueError("id and action are required strings")
                if ticket is not None and not isinstance(ticket, str):
                    raise ValueError("ticket must be a string")
                prompt = build_prompt(scratch, tracker, task_id, action, ticket)
            except (ValueError, LaunchRejected) as exc:
                self._send(400, "text/plain; charset=utf-8", str(exc).encode("utf-8"))
                return
            try:
                launcher(prompt, scratch.parent)
            except Exception as exc:
                self._send(500, "text/plain; charset=utf-8", f"launch failed: {exc}".encode())
                return
            self._send(200, "application/json", json.dumps({"prompt": prompt}).encode("utf-8"))

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
    server = make_server(
        ROOT / ".scratch",
        ROOT / "docs" / "progress-tracker.md",
        args.port,
        ROOT / "docs" / "tfm-work-plan.md",
    )
    print(f"Task tree at http://127.0.0.1:{server.server_port}/  (Ctrl+C to stop)")
    with contextlib.suppress(KeyboardInterrupt):
        server.serve_forever()
