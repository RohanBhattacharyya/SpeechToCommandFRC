from __future__ import annotations

from dataclasses import asdict
import argparse
import json
from pathlib import Path
import queue
import signal
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .config import AppConfig
from .networktables import NetworkTablesPublisher
from .speech import SpeechCommandService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = PROJECT_ROOT / "static"


class AppState:
    def __init__(self) -> None:
        self.listeners: list[queue.Queue[dict]] = []
        self.lock = threading.Lock()
        self.publisher = NetworkTablesPublisher()
        self.service = SpeechCommandService(self.publisher, self.emit)
        self.publisher.configure(self.service.config)

    def emit(self, event: dict) -> None:
        with self.lock:
            listeners = list(self.listeners)
        for listener in listeners:
            listener.put(event)

    def add_listener(self) -> queue.Queue[dict]:
        listener: queue.Queue[dict] = queue.Queue()
        with self.lock:
            self.listeners.append(listener)
        listener.put(self.snapshot_event())
        return listener

    def remove_listener(self, listener: queue.Queue[dict]) -> None:
        with self.lock:
            if listener in self.listeners:
                self.listeners.remove(listener)

    def snapshot(self) -> dict[str, Any]:
        return {
            "config": asdict(self.service.config),
            "speech": self.service.status(),
            "networkTables": self.publisher.status(),
        }

    def snapshot_event(self) -> dict[str, Any]:
        return {"type": "state", **self.snapshot()}

    def close(self) -> None:
        self.service.stop()
        self.publisher.close()


STATE = AppState()


class Handler(BaseHTTPRequestHandler):
    server_version = "SpeechToCommandFRC/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._serve_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
        elif parsed.path == "/app.js":
            self._serve_file(STATIC_DIR / "app.js", "text/javascript; charset=utf-8")
        elif parsed.path == "/styles.css":
            self._serve_file(STATIC_DIR / "styles.css", "text/css; charset=utf-8")
        elif parsed.path == "/api/state":
            self._send_json(STATE.snapshot())
        elif parsed.path == "/api/events":
            self._serve_events()
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            body = self._read_json()
            if parsed.path == "/api/config":
                config = AppConfig(**body)
                config.commands = self._unique_commands(config.commands)
                STATE.service.update_config(config)
                self._send_json(STATE.snapshot())
            elif parsed.path == "/api/start":
                ok = STATE.service.start()
                self._send_json({"ok": ok, **STATE.snapshot()})
            elif parsed.path == "/api/stop":
                STATE.service.stop()
                self._send_json({"ok": True, **STATE.snapshot()})
            elif parsed.path == "/api/test":
                text = str(body.get("text", ""))
                matches = STATE.service.test_transcript(text)
                self._send_json({"ok": True, "matches": matches})
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except TypeError as exc:
            self._send_json({"ok": False, "error": f"Bad config: {exc}"}, HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

    def _serve_file(self, path: Path, content_type: str) -> None:
        try:
            content = path.read_bytes()
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_events(self) -> None:
        listener = STATE.add_listener()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        try:
            while True:
                try:
                    event = listener.get(timeout=30)
                    payload = f"data: {json.dumps(event)}\n\n"
                except queue.Empty:
                    payload = ": keepalive\n\n"
                self.wfile.write(payload.encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        finally:
            STATE.remove_listener(listener)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Expected a JSON object")
        return payload

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        content = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    @staticmethod
    def _unique_commands(commands: list[str]) -> list[str]:
        clean: list[str] = []
        seen: set[str] = set()
        for command in commands:
            stripped = str(command).strip()
            key = stripped.casefold()
            if stripped and key not in seen:
                clean.append(stripped)
                seen.add(key)
        return clean


def main() -> None:
    parser = argparse.ArgumentParser(description="Laptop speech command publisher for FRC NetworkTables")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)

    def shutdown(signum: int, frame: object) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"SpeechToCommandFRC running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    finally:
        STATE.close()


if __name__ == "__main__":
    main()
