from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from threading import RLock

from backend.agents import MIN_AUTOMATION_CONFIDENCE
from backend.models import Incident, RemediationAudit, incident_from_dict, utc_now


DEFAULT_DB_PATH = Path(os.environ.get("INCIDENT_DB_PATH", Path(__file__).resolve().parents[1] / "data" / "incidents.db"))


class IncidentStore:
    def __init__(self, incidents: list[Incident] | None = None, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._init_db()
        if incidents:
            self.seed_if_empty(incidents)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=15)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS remediation_idempotency (
                    key TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    recommendation_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def seed_if_empty(self, incidents: list[Incident]) -> None:
        with self._lock, self._connect() as connection:
            count = connection.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
            if count:
                return
            for incident in incidents:
                self._upsert(connection, incident)

    def reset(self, incidents: list[Incident]) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM remediation_idempotency")
            connection.execute("DELETE FROM incidents")
            for incident in incidents:
                self._upsert(connection, incident)

    def _upsert(self, connection: sqlite3.Connection, incident: Incident) -> None:
        payload = json.dumps(incident.to_dict(), separators=(",", ":"))
        connection.execute(
            """
            INSERT INTO incidents (id, payload, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET payload = excluded.payload, updated_at = excluded.updated_at
            """,
            (incident.id, payload, incident.updated_at),
        )

    def list_incidents(self) -> list[Incident]:
        with self._lock, self._connect() as connection:
            rows = connection.execute("SELECT payload FROM incidents ORDER BY updated_at DESC").fetchall()
        return [incident_from_dict(json.loads(row[0])) for row in rows]

    def get_incident(self, incident_id: str) -> Incident | None:
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT payload FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        return incident_from_dict(json.loads(row[0])) if row else None

    def save_incident(self, incident: Incident) -> Incident:
        incident.updated_at = utc_now()
        with self._lock, self._connect() as connection:
            self._upsert(connection, incident)
        return incident_from_dict(incident.to_dict())

    def apply_recommendation(
        self,
        incident_id: str,
        recommendation_id: str,
        idempotency_key: str,
        min_confidence: float = MIN_AUTOMATION_CONFIDENCE,
    ) -> tuple[Incident | None, str | None]:
        if not idempotency_key:
            return None, "idempotency_key is required"

        with self._lock, self._connect() as connection:
            existing_key = connection.execute(
                "SELECT incident_id, recommendation_id FROM remediation_idempotency WHERE key = ?",
                (idempotency_key,),
            ).fetchone()
            row = connection.execute("SELECT payload FROM incidents WHERE id = ?", (incident_id,)).fetchone()
            if not row:
                return None, "incident not found"

            incident = incident_from_dict(json.loads(row[0]))
            if existing_key:
                if existing_key[0] != incident_id or existing_key[1] != recommendation_id:
                    return None, "idempotency_key was already used for a different remediation"
                return incident, None

            if not incident.root_causes:
                return None, "investigation must run before remediation"
            if incident.root_causes[0].confidence < min_confidence:
                return None, "root cause confidence is below remediation threshold"

            recommendation = next((item for item in incident.recommendations if item.id == recommendation_id), None)
            if not recommendation:
                return None, "recommendation not found"
            if recommendation.applied:
                return None, "recommendation already applied"

            recommendation.applied = True
            incident.status = "mitigated"
            incident.resolved_at = utc_now()
            incident.audit_log.insert(
                0,
                RemediationAudit(
                    recommendation_id=recommendation.id,
                    title=recommendation.title,
                    command=recommendation.command,
                    applied_at=utc_now(),
                    result="Simulated remediation accepted and recorded. No infrastructure command was executed.",
                    idempotency_key=idempotency_key,
                ),
            )
            incident.updated_at = utc_now()
            connection.execute(
                """
                INSERT INTO remediation_idempotency (key, incident_id, recommendation_id, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (idempotency_key, incident_id, recommendation_id, utc_now()),
            )
            self._upsert(connection, incident)
            return incident_from_dict(incident.to_dict()), None
