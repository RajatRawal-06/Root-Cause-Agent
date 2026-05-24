from __future__ import annotations

from backend.models import (
    Incident,
    TelemetryEvent,
    AgentFinding,
    RootCause,
    Recommendation,
    RemediationAudit,
)


def build_seed_incidents() -> list[Incident]:
    return [
        Incident(
            id="inc-2026-0524-001",
            title="Checkout API latency and elevated 5xx rate",
            service="checkout-api",
            severity="P1",
            status="open",
            started_at="2026-05-24T06:31:00+00:00",
            region="ap-south-1",
            team="payments",
            summary="Latency crossed the SLO threshold after a checkout-api deployment.",
            telemetry=[
                TelemetryEvent(
                    timestamp="2026-05-24T06:29:10+00:00",
                    source="github",
                    metric_type="deployment",
                    service_name="checkout-api",
                    severity="info",
                    payload={"version": "v2.4.0", "change": "reduced db_pool_max from 100 to 50"},
                    tags={"env": "prod", "region": "ap-south-1", "team": "payments"},
                ),
                TelemetryEvent(
                    timestamp="2026-05-24T06:31:20+00:00",
                    source="prometheus",
                    metric_type="metric",
                    service_name="checkout-api",
                    severity="critical",
                    payload={"latency_p95_ms": 1850, "baseline_p95_ms": 420, "error_rate": 0.128},
                    tags={"env": "prod", "region": "ap-south-1", "team": "payments"},
                ),
                TelemetryEvent(
                    timestamp="2026-05-24T06:31:39+00:00",
                    source="loki",
                    metric_type="log",
                    service_name="checkout-api",
                    severity="critical",
                    payload={"message": "database connection timeout waiting for pool slot", "count": 438},
                    tags={"env": "prod", "region": "ap-south-1", "team": "payments"},
                ),
                TelemetryEvent(
                    timestamp="2026-05-24T06:32:05+00:00",
                    source="tempo",
                    metric_type="trace",
                    service_name="checkout-api",
                    severity="warning",
                    payload={"slowest_span": "postgres.reserve_inventory", "duration_ms": 1430},
                    tags={"env": "prod", "region": "ap-south-1", "team": "payments"},
                ),
            ],
        ),
        Incident(
            id="inc-2026-0524-002",
            title="User service auth failures in EU region",
            service="user-service",
            severity="P2",
            status="open",
            started_at="2026-05-24T05:48:00+00:00",
            region="eu-west-1",
            team="identity",
            summary="Authentication failures increased after a secret rotation event.",
            telemetry=[
                TelemetryEvent(
                    timestamp="2026-05-24T05:45:00+00:00",
                    source="k8s",
                    metric_type="deployment",
                    service_name="user-service",
                    severity="info",
                    payload={"change": "secret rotation for jwt-public-key"},
                    tags={"env": "prod", "region": "eu-west-1", "team": "identity"},
                ),
                TelemetryEvent(
                    timestamp="2026-05-24T05:48:18+00:00",
                    source="datadog",
                    metric_type="metric",
                    service_name="user-service",
                    severity="warning",
                    payload={"auth_failure_rate": 0.072, "baseline_failure_rate": 0.009},
                    tags={"env": "prod", "region": "eu-west-1", "team": "identity"},
                ),
                TelemetryEvent(
                    timestamp="2026-05-24T05:48:43+00:00",
                    source="elk",
                    metric_type="log",
                    service_name="user-service",
                    severity="warning",
                    payload={"message": "jwt signature verification failed", "count": 211},
                    tags={"env": "prod", "region": "eu-west-1", "team": "identity"},
                ),
            ],
        ),
        Incident(
            id="inc-2026-0524-003",
            title="Redis memory saturation in cache cluster",
            service="cache-service",
            severity="P3",
            status="mitigated",
            started_at="2026-05-24T04:12:00+00:00",
            region="us-east-1",
            team="platform",
            summary="Redis cluster hit maxmemory limit causing eviction failures. Mitigated by dynamic memory limit expansion.",
            telemetry=[
                TelemetryEvent(
                    timestamp="2026-05-24T04:08:10+00:00",
                    source="prometheus",
                    metric_type="metric",
                    service_name="cache-service",
                    severity="critical",
                    payload={"redis_memory_utilization": 0.99, "redis_evictions": 4120},
                    tags={"env": "prod", "region": "us-east-1", "team": "platform"},
                ),
                TelemetryEvent(
                    timestamp="2026-05-24T04:10:00+00:00",
                    source="loki",
                    metric_type="log",
                    service_name="cache-service",
                    severity="critical",
                    payload={"message": "OOM command not allowed when used memory > 'maxmemory'", "count": 182},
                    tags={"env": "prod", "region": "us-east-1", "team": "platform"},
                ),
            ],
            agent_findings=[
                AgentFinding(
                    agent="Alert Intake Agent",
                    status="complete",
                    summary="P3 incident routed to platform team.",
                    confidence=0.58,
                    evidence=["Service=cache-service", "Region=us-east-1", "Team=platform"],
                ),
                AgentFinding(
                    agent="Logs Intelligence Agent",
                    status="complete",
                    summary="Identified Redis maxmemory error signature.",
                    confidence=0.9,
                    evidence=["182x OOM command not allowed when used memory > 'maxmemory'"],
                ),
                AgentFinding(
                    agent="Metrics Analysis Agent",
                    status="complete",
                    summary="Redis memory utilization reached 99%.",
                    confidence=0.95,
                    evidence=["Redis memory utilization reached 99.0%"],
                ),
                AgentFinding(
                    agent="Correlation Engine Agent",
                    status="complete",
                    summary="Built chronological incident context graph.",
                    confidence=0.95,
                    evidence=["2 correlated events inside investigation window", "strongest agent confidence 0.95"],
                ),
                AgentFinding(
                    agent="Root Cause Analysis Agent",
                    status="complete",
                    summary="Generated RCA hypothesis with calibrated evidence factors.",
                    confidence=0.92,
                    evidence=["Redis memory utilization reached 99.0%", "182x OOM command not allowed when used memory > 'maxmemory'"],
                ),
                AgentFinding(
                    agent="Recommendation Agent",
                    status="complete",
                    summary="Generated blast-radius-aware remediation plan with verification gates.",
                    confidence=0.95,
                    evidence=["Dynamically expand cache memory limit safety score 0.95"],
                ),
            ],
            root_causes=[
                RootCause(
                    hypothesis="Redis cache eviction failure due to maxmemory saturation",
                    confidence=0.92,
                    evidence=["Redis memory utilization 99%", "OOM command errors in logs"],
                    affected_services=["cache-service", "catalog-api"],
                    alternatives=["Cache eviction policy misconfiguration", "Downstream service query storm"],
                    confidence_factors={
                        "deployment_correlation": 0.2,
                        "log_match": 0.9,
                        "metric_anomaly": 0.95,
                        "trace_support": 0.2,
                        "agent_agreement": 0.92,
                    },
                )
            ],
            recommendations=[
                Recommendation(
                    id="inc-2026-0524-003-rec-scale",
                    title="Dynamically expand cache memory limit",
                    command="redis-cli config set maxmemory 4gb",
                    risk="low",
                    rationale="Instantly resolves eviction blockages and OOM states by expanding capacity.",
                    applied=True,
                    safety_score=0.95,
                    expected_impact={
                        "eviction_failures": "100% reduction",
                        "cache_hit_rate": "Stabilizes back to 94%",
                    },
                    blast_radius=[
                        "Node memory capacity must remain below 85% host physical RAM limit"
                    ],
                    rollout_plan=[
                        "Verify current host free RAM > 1.5GB",
                        "Increase maxmemory setting to 4GB dynamically via config set",
                    ],
                    verification_checks=[
                        "redis-cli info memory | grep maxmemory",
                        "Monitor eviction alerts drop to 0 for 5 minutes",
                    ],
                )
            ],
            timeline=[
                "2026-05-24T04:08:10+00:00 - prometheus reported metric signal for cache-service",
                "2026-05-24T04:10:00+00:00 - loki reported log signal for cache-service",
            ],
            audit_log=[
                RemediationAudit(
                    recommendation_id="inc-2026-0524-003-rec-scale",
                    title="Dynamically expand cache memory limit",
                    command="redis-cli config set maxmemory 4gb",
                    applied_at="2026-05-24T04:22:00+00:00",
                    result="Simulated remediation accepted and recorded. Cache memory ceiling expanded to 4GB.",
                    idempotency_key="demo-key-redis-scale",
                )
            ],
            resolved_at="2026-05-24T04:22:00+00:00",
        ),
    ]

