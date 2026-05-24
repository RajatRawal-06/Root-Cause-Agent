from __future__ import annotations

from backend.models import Incident, TelemetryEvent


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
    ]

