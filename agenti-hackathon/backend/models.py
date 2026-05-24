from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


Severity = Literal["critical", "warning", "info"]
IncidentStatus = Literal["open", "investigating", "mitigated", "resolved", "escalated"]
AgentStatus = Literal["pending", "running", "complete", "partial", "failed"]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class TelemetryEvent:
    timestamp: str
    source: str
    metric_type: Literal["log", "metric", "trace", "deployment"]
    service_name: str
    severity: Severity
    payload: dict[str, Any]
    tags: dict[str, str]


@dataclass
class AgentFinding:
    agent: str
    status: AgentStatus
    summary: str
    confidence: float
    evidence: list[str] = field(default_factory=list)
    duration_ms: int = 0
    error: str | None = None


@dataclass
class RootCause:
    hypothesis: str
    confidence: float
    evidence: list[str]
    affected_services: list[str]
    alternatives: list[str] = field(default_factory=list)
    confidence_factors: dict[str, float] = field(default_factory=dict)


@dataclass
class Recommendation:
    id: str
    title: str
    command: str
    risk: Literal["low", "medium", "high"]
    rationale: str
    applied: bool = False
    safety_score: float = 0.0
    expected_impact: dict[str, str] = field(default_factory=dict)
    blast_radius: list[str] = field(default_factory=list)
    rollout_plan: list[str] = field(default_factory=list)
    verification_checks: list[str] = field(default_factory=list)


@dataclass
class RemediationAudit:
    recommendation_id: str
    title: str
    command: str
    applied_at: str
    result: str
    idempotency_key: str


@dataclass
class Incident:
    id: str
    title: str
    service: str
    severity: Literal["P0", "P1", "P2", "P3", "P4"]
    status: IncidentStatus
    started_at: str
    region: str
    team: str
    summary: str
    telemetry: list[TelemetryEvent]
    agent_findings: list[AgentFinding] = field(default_factory=list)
    root_causes: list[RootCause] = field(default_factory=list)
    recommendations: list[Recommendation] = field(default_factory=list)
    timeline: list[str] = field(default_factory=list)
    audit_log: list[RemediationAudit] = field(default_factory=list)
    updated_at: str = field(default_factory=utc_now)
    resolved_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def telemetry_event_from_dict(data: dict[str, Any]) -> TelemetryEvent:
    return TelemetryEvent(
        timestamp=str(data.get("timestamp", utc_now())),
        source=str(data.get("source", "unknown")),
        metric_type=data.get("metric_type", "log"),
        service_name=str(data.get("service_name", "unknown-service")),
        severity=data.get("severity", "info"),
        payload=dict(data.get("payload") or {}),
        tags=dict(data.get("tags") or {}),
    )


def agent_finding_from_dict(data: dict[str, Any]) -> AgentFinding:
    return AgentFinding(
        agent=str(data.get("agent", "Unknown Agent")),
        status=data.get("status", "failed"),
        summary=str(data.get("summary", "")),
        confidence=float(data.get("confidence", 0)),
        evidence=list(data.get("evidence") or []),
        duration_ms=int(data.get("duration_ms", 0)),
        error=data.get("error"),
    )


def root_cause_from_dict(data: dict[str, Any]) -> RootCause:
    return RootCause(
        hypothesis=str(data.get("hypothesis", "")),
        confidence=float(data.get("confidence", 0)),
        evidence=list(data.get("evidence") or []),
        affected_services=list(data.get("affected_services") or []),
        alternatives=list(data.get("alternatives") or []),
        confidence_factors={key: float(value) for key, value in dict(data.get("confidence_factors") or {}).items()},
    )


def recommendation_from_dict(data: dict[str, Any]) -> Recommendation:
    return Recommendation(
        id=str(data.get("id", "")),
        title=str(data.get("title", "")),
        command=str(data.get("command", "")),
        risk=data.get("risk", "low"),
        rationale=str(data.get("rationale", "")),
        applied=bool(data.get("applied", False)),
        safety_score=float(data.get("safety_score", 0)),
        expected_impact={str(key): str(value) for key, value in dict(data.get("expected_impact") or {}).items()},
        blast_radius=list(data.get("blast_radius") or []),
        rollout_plan=list(data.get("rollout_plan") or []),
        verification_checks=list(data.get("verification_checks") or []),
    )


def audit_from_dict(data: dict[str, Any]) -> RemediationAudit:
    return RemediationAudit(
        recommendation_id=str(data.get("recommendation_id", "")),
        title=str(data.get("title", "")),
        command=str(data.get("command", "")),
        applied_at=str(data.get("applied_at", utc_now())),
        result=str(data.get("result", "")),
        idempotency_key=str(data.get("idempotency_key", "")),
    )


def incident_from_dict(data: dict[str, Any]) -> Incident:
    return Incident(
        id=str(data.get("id", "")),
        title=str(data.get("title", "Untitled incident")),
        service=str(data.get("service", "unknown-service")),
        severity=data.get("severity", "P4"),
        status=data.get("status", "open"),
        started_at=str(data.get("started_at", utc_now())),
        region=str(data.get("region", "unknown-region")),
        team=str(data.get("team", "unknown-team")),
        summary=str(data.get("summary", "")),
        telemetry=[telemetry_event_from_dict(item) for item in list(data.get("telemetry") or [])],
        agent_findings=[agent_finding_from_dict(item) for item in list(data.get("agent_findings") or [])],
        root_causes=[root_cause_from_dict(item) for item in list(data.get("root_causes") or [])],
        recommendations=[recommendation_from_dict(item) for item in list(data.get("recommendations") or [])],
        timeline=list(data.get("timeline") or []),
        audit_log=[audit_from_dict(item) for item in list(data.get("audit_log") or [])],
        updated_at=str(data.get("updated_at", utc_now())),
        resolved_at=data.get("resolved_at"),
    )
