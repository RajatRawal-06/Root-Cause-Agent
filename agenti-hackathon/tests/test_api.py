from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
TEST_DATA = ROOT / ".test-data"
TEST_DATA.mkdir(exist_ok=True)


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class ApiWorkflowTest(unittest.TestCase):
    process: subprocess.Popen[str]
    base_url: str
    temp_dir: TemporaryDirectory[str]

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = TemporaryDirectory(dir=TEST_DATA)
        port = free_port()
        cls.base_url = f"http://127.0.0.1:{port}"
        env = os.environ.copy()
        env["PORT"] = str(port)
        env["INCIDENT_DB_PATH"] = str(Path(cls.temp_dir.name) / "incidents.db")
        cls.process = subprocess.Popen(
            [sys.executable, "backend/server.py"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                cls.get_json("/api/health")
                return
            except Exception:
                time.sleep(0.2)
        stdout, stderr = cls.process.communicate(timeout=1)
        raise RuntimeError(f"server did not start\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.process.terminate()
        try:
            cls.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.process.kill()
        cls.temp_dir.cleanup()

    @classmethod
    def get_json(cls, path: str) -> dict:
        with urlopen(f"{cls.base_url}{path}", timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    @classmethod
    def post_json(cls, path: str, payload: dict | None = None) -> dict:
        data = json.dumps(payload or {}).encode("utf-8")
        request = Request(
            f"{cls.base_url}{path}",
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    @classmethod
    def post_raw(cls, path: str, payload: bytes) -> dict:
        request = Request(
            f"{cls.base_url}{path}",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_health_ready_and_metrics(self) -> None:
        self.assertEqual(self.get_json("/api/health")["status"], "ok")
        self.assertEqual(self.get_json("/api/ready")["status"], "ready")
        self.assertEqual(self.get_json("/api/metrics")["storage"], "sqlite")

    def test_investigate_and_remediate_flow(self) -> None:
        snapshot = self.get_json("/api/incidents")
        incident_id = snapshot["incidents"][0]["id"]

        investigated = self.post_json(f"/api/incidents/{incident_id}/investigate")
        recommendation_id = investigated["recommendations"][0]["id"]
        self.assertGreaterEqual(investigated["root_causes"][0]["confidence"], 0.8)
        self.assertGreaterEqual(investigated["recommendations"][0]["safety_score"], 0.8)
        self.assertIn("blast_radius", investigated["recommendations"][0])
        self.assertIn("rollout_plan", investigated["recommendations"][0])
        self.assertIn("verification_checks", investigated["recommendations"][0])

        remediated = self.post_json(
            "/api/remediate",
            {
                "incident_id": incident_id,
                "recommendation_id": recommendation_id,
                "idempotency_key": "api-test-key",
            },
        )
        repeated = self.post_json(
            "/api/remediate",
            {
                "incident_id": incident_id,
                "recommendation_id": recommendation_id,
                "idempotency_key": "api-test-key",
            },
        )

        self.assertEqual(remediated["status"], "mitigated")
        self.assertEqual(len(remediated["audit_log"]), 1)
        self.assertEqual(len(repeated["audit_log"]), 1)
        with self.assertRaises(HTTPError) as reused_key:
            self.post_json(
                "/api/remediate",
                {
                    "incident_id": incident_id,
                    "recommendation_id": investigated["recommendations"][1]["id"],
                    "idempotency_key": "api-test-key",
                },
            )
        self.assertEqual(reused_key.exception.code, 409)
        with self.assertRaises(HTTPError) as duplicate:
            self.post_json(
                "/api/remediate",
                {
                    "incident_id": incident_id,
                    "recommendation_id": recommendation_id,
                    "idempotency_key": "api-test-key-2",
                },
            )
        self.assertEqual(duplicate.exception.code, 409)

    def test_invalid_remediation_body_returns_400(self) -> None:
        with self.assertRaises(HTTPError) as context:
            self.post_json("/api/remediate", {"incident_id": "inc-2026-0524-001"})
        self.assertEqual(context.exception.code, 400)
        with self.assertRaises(HTTPError) as non_string:
            self.post_json(
                "/api/remediate",
                {
                    "incident_id": "inc-2026-0524-001",
                    "recommendation_id": ["not", "a", "string"],
                    "idempotency_key": "api-validation-key",
                },
            )
        self.assertEqual(non_string.exception.code, 400)
        with self.assertRaises(HTTPError) as malformed:
            self.post_raw("/api/remediate", b"{not-json")
        self.assertEqual(malformed.exception.code, 400)
        with self.assertRaises(HTTPError) as scalar:
            self.post_raw("/api/remediate", b"[]")
        self.assertEqual(scalar.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
