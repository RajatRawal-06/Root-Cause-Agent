from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import socketserver
import struct
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.agents import InvestigationPipeline
from backend.sample_data import build_seed_incidents
from backend.store import IncidentStore
from backend.validation import RequestValidationError, parse_json_body, parse_remediation_request


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "8000"))
REMEDIATION_MIN_CONFIDENCE = float(os.environ.get("REMEDIATION_MIN_CONFIDENCE", "0.80"))

store = IncidentStore(build_seed_incidents())
pipeline = InvestigationPipeline()
clients: set["WebSocketClient"] = set()
clients_lock = threading.RLock()


def json_bytes(payload: object) -> bytes:
    return json.dumps(payload, indent=2).encode("utf-8")


def snapshot() -> dict[str, object]:
    incidents = [incident.to_dict() for incident in store.list_incidents()]
    return {
        "type": "snapshot",
        "incidents": incidents,
        "stats": {
            "total": len(incidents),
            "open": sum(1 for item in incidents if item["status"] == "open"),
            "investigating": sum(1 for item in incidents if item["status"] == "investigating"),
            "mitigated": sum(1 for item in incidents if item["status"] == "mitigated"),
            "critical": sum(1 for item in incidents if item["severity"] in {"P0", "P1"}),
            "needs_attention": sum(1 for item in incidents if item["status"] in {"open", "investigating"} and item["severity"] in {"P0", "P1", "P2"}),
        },
    }


def metrics() -> dict[str, object]:
    current = snapshot()["stats"]
    return {
        "service": "ai-incident-root-cause-analyzer",
        "storage": "sqlite",
        "websocket_clients": len(clients),
        "incidents": current,
    }


def broadcast(payload: dict[str, object]) -> None:
    data = json.dumps(payload).encode("utf-8")
    with clients_lock:
        stale: list[WebSocketClient] = []
        for client in clients:
            try:
                client.send(data)
            except OSError:
                stale.append(client)
        for client in stale:
            clients.discard(client)


class WebSocketClient:
    def __init__(self, request: BaseHTTPRequestHandler) -> None:
        self.request = request
        self.wfile = request.wfile
        self.rfile = request.rfile

    def send(self, payload: bytes) -> None:
        header = bytearray([0x81])
        length = len(payload)
        if length < 126:
            header.append(length)
        elif length <= 65535:
            header.append(126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(127)
            header.extend(struct.pack("!Q", length))
        self.wfile.write(header + payload)
        self.wfile.flush()

    def wait_until_closed(self) -> None:
        while True:
            byte = self.rfile.read(1)
            if not byte:
                break
            opcode = byte[0] & 0x0F
            length_byte = self.rfile.read(1)
            if not length_byte:
                break
            length = length_byte[0] & 0x7F
            if length == 126:
                length = struct.unpack("!H", self.rfile.read(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self.rfile.read(8))[0]
            masked = bool(length_byte[0] & 0x80)
            mask = self.rfile.read(4) if masked else b""
            payload = self.rfile.read(length)
            if masked:
                payload = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
            if opcode == 0x8:
                break


class Handler(BaseHTTPRequestHandler):
    server_version = "IncidentRCA/1.0"

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/ws":
            self.handle_websocket()
            return
        if parsed.path == "/api/health":
            self.send_json({"status": "ok", "service": "ai-incident-root-cause-analyzer"})
            return
        if parsed.path == "/api/ready":
            self.send_json({"status": "ready", "storage": "sqlite", "incident_count": len(store.list_incidents())})
            return
        if parsed.path == "/api/metrics":
            self.send_json(metrics())
            return
        if parsed.path == "/api/incidents":
            self.send_json(snapshot())
            return
        if parsed.path.startswith("/api/incidents/"):
            incident_id = parsed.path.rsplit("/", 1)[-1]
            incident = store.get_incident(incident_id)
            if incident:
                self.send_json(incident.to_dict())
            else:
                self.send_json({"error": "incident not found"}, HTTPStatus.NOT_FOUND)
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/demo/reset":
            store.reset(build_seed_incidents())
            broadcast(snapshot())
            self.send_json(snapshot())
            return
        if parsed.path.startswith("/api/incidents/") and parsed.path.endswith("/investigate"):
            incident_id = parsed.path.split("/")[-2]
            incident = store.get_incident(incident_id)
            if not incident:
                self.send_json({"error": "incident not found"}, HTTPStatus.NOT_FOUND)
                return
            updated = pipeline.run(incident)
            store.save_incident(updated)
            broadcast(snapshot())
            self.send_json(updated.to_dict())
            return
        if parsed.path == "/api/remediate":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = parse_json_body(self.rfile.read(length))
                request = parse_remediation_request(body)
            except RequestValidationError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            incident, error = store.apply_recommendation(
                request.incident_id,
                request.recommendation_id,
                request.idempotency_key,
                min_confidence=REMEDIATION_MIN_CONFIDENCE,
            )
            if error:
                status = HTTPStatus.NOT_FOUND if "not found" in error else HTTPStatus.CONFLICT
                self.send_json({"error": error}, status)
                return
            broadcast(snapshot())
            self.send_json(incident.to_dict() if incident else {"error": "incident not found"}, HTTPStatus.OK)
            return
        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(data)

    def serve_static(self, path: str) -> None:
        target = FRONTEND / ("index.html" if path in {"", "/"} else path.lstrip("/"))
        if not target.exists() or not target.resolve().is_relative_to(FRONTEND.resolve()):
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        data = target.read_bytes()
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def handle_websocket(self) -> None:
        key = self.headers.get("Sec-WebSocket-Key")
        if not key:
            self.send_error(HTTPStatus.BAD_REQUEST)
            return
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        self.send_response(HTTPStatus.SWITCHING_PROTOCOLS)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        client = WebSocketClient(self)
        with clients_lock:
            clients.add(client)
        try:
            client.send(json.dumps(snapshot()).encode("utf-8"))
            client.wait_until_closed()
        finally:
            with clients_lock:
                clients.discard(client)


class ThreadingServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def heartbeat() -> None:
    while True:
        time.sleep(4)
        broadcast(snapshot())


def main() -> None:
    threading.Thread(target=heartbeat, daemon=True).start()
    with ThreadingServer((HOST, PORT), Handler) as httpd:
        print(f"AI Incident Root Cause Analyzer running at http://{HOST}:{PORT}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
