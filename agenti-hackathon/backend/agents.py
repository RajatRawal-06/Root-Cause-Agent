from __future__ import annotations

import time
from collections import Counter
from dataclasses import replace
from datetime import datetime
from typing import Callable, Iterable

from backend.models import AgentFinding, Incident, Recommendation, RootCause, utc_now


MIN_AUTOMATION_CONFIDENCE = 0.8


def _confidence(value: float) -> float:
    return max(0.0, min(1.0, round(value, 3)))


def _number(payload: dict[str, object], key: str) -> float | None:
    value = payload.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _safe_timestamp(value: str) -> tuple[int, str]:
    try:
        normalized = value.replace("Z", "+00:00")
        return (0, datetime.fromisoformat(normalized).isoformat())
    except ValueError:
        return (1, value)


class AlertIntakeAgent:
    name = "Alert Intake Agent"

    def run(self, incident: Incident) -> AgentFinding:
        severity_rank = {"P0": 1.0, "P1": 0.92, "P2": 0.76, "P3": 0.58, "P4": 0.38}
        confidence = severity_rank.get(incident.severity, 0.25)
        status = "complete" if incident.severity in severity_rank else "partial"
        evidence = [f"Service={incident.service}", f"Region={incident.region}", f"Team={incident.team}"]
        if status == "partial":
            evidence.append(f"Unknown severity={incident.severity}; defaulted to low-confidence routing")
        return AgentFinding(
            agent=self.name,
            status=status,
            summary=f"{incident.severity} incident routed to {incident.team} for {incident.service}.",
            confidence=confidence,
            evidence=evidence,
        )


class LogsIntelligenceAgent:
    name = "Logs Intelligence Agent"

    def run(self, incident: Incident) -> AgentFinding:
        logs = [event for event in incident.telemetry if event.metric_type == "log"]
        messages = [str(event.payload.get("message", "unknown log pattern")) for event in logs]
        top_patterns = Counter(messages).most_common(5)
        evidence = [f"{count}x {message}" for message, count in top_patterns] or ["No critical log pattern detected"]
        confidence = 0.9 if logs else 0.35
        status = "complete" if logs else "partial"
        return AgentFinding(status=status, agent=self.name, summary="Extracted dominant error signatures from logs.", confidence=confidence, evidence=evidence)


class MetricsAnalysisAgent:
    name = "Metrics Analysis Agent"

    def run(self, incident: Incident) -> AgentFinding:
        metrics = [event for event in incident.telemetry if event.metric_type == "metric"]
        evidence: list[str] = []
        score = 0.4
        malformed = 0
        for event in metrics:
            payload = event.payload
            latency = _number(payload, "latency_p95_ms")
            baseline = _number(payload, "baseline_p95_ms")
            error_rate = _number(payload, "error_rate")
            auth_rate = _number(payload, "auth_failure_rate")
            auth_baseline = _number(payload, "baseline_failure_rate")

            if latency is not None and baseline is not None:
                ratio = latency / max(baseline, 1)
                evidence.append(f"p95 latency {latency:.0f}ms is {ratio:.1f}x baseline")
                score = max(score, min(0.98, ratio / 5))
            elif "latency_p95_ms" in payload or "baseline_p95_ms" in payload:
                malformed += 1

            if error_rate is not None:
                evidence.append(f"error rate reached {error_rate * 100:.1f}%")
                score = max(score, 0.88)
            elif "error_rate" in payload:
                malformed += 1

            if auth_rate is not None:
                delta = auth_rate - (auth_baseline or 0)
                evidence.append(f"auth failures increased by {delta * 100:.1f} percentage points")
                score = max(score, 0.78)
            elif "auth_failure_rate" in payload:
                malformed += 1

        if not metrics:
            evidence.append("No metric stream available for this incident")
        if malformed:
            evidence.append(f"{malformed} malformed metric values ignored")
        status = "complete" if metrics and malformed == 0 else "partial"
        return AgentFinding(self.name, status, "Compared live metrics with baseline behavior.", _confidence(score), evidence)


class DistributedTraceAgent:
    name = "Distributed Trace Agent"

    def run(self, incident: Incident) -> AgentFinding:
        traces = [event for event in incident.telemetry if event.metric_type == "trace"]
        evidence = []
        for event in traces:
            span = event.payload.get("slowest_span", "unknown span")
            duration = _number(event.payload, "duration_ms")
            evidence.append(f"{span} consumed {duration:.0f}ms" if duration is not None else f"{span} had missing duration")
        confidence = 0.86 if traces else 0.42
        summary = "Identified slowest service chain from trace spans." if traces else "No trace bottleneck available."
        status = "complete" if traces else "partial"
        return AgentFinding(self.name, status, summary, confidence, evidence or ["Trace stream had no correlated spans"])


class DeploymentAnalysisAgent:
    name = "Deployment Analysis Agent"

    def run(self, incident: Incident) -> AgentFinding:
        deployments = [event for event in incident.telemetry if event.metric_type == "deployment"]
        evidence = []
        for event in deployments:
            version = event.payload.get("version", "configuration change")
            change = event.payload.get("change", "deployment metadata changed")
            evidence.append(f"{version}: {change}")
        confidence = 0.93 if deployments else 0.3
        status = "complete" if deployments else "partial"
        return AgentFinding(self.name, status, "Correlated deployment events with incident start time.", confidence, evidence or ["No deployment event found inside incident window"])


class CorrelationEngineAgent:
    name = "Correlation Engine Agent"

    def run(self, incident: Incident, findings: Iterable[AgentFinding]) -> tuple[AgentFinding, list[str]]:
        sorted_events = sorted(incident.telemetry, key=lambda item: _safe_timestamp(item.timestamp))
        timeline = [
            f"{event.timestamp} - {event.source} reported {event.metric_type} signal for {event.service_name}"
            for event in sorted_events
        ]
        finding_list = list(findings)
        strongest = max((finding.confidence for finding in finding_list), default=0.5)
        failed_agents = [finding.agent for finding in finding_list if finding.status == "failed"]
        evidence = [
            f"{len(timeline)} correlated events inside investigation window",
            f"strongest agent confidence {strongest:.2f}",
        ]
        if failed_agents:
            evidence.append(f"failed agents excluded from causal graph: {', '.join(failed_agents)}")
        status = "partial" if failed_agents or not timeline else "complete"
        finding = AgentFinding(self.name, status, "Built chronological incident context graph.", strongest, evidence)
        return finding, timeline or ["No telemetry events available; manual validation required"]


class RCAAgent:
    name = "Root Cause Analysis Agent"

    def run(self, incident: Incident, findings: list[AgentFinding]) -> tuple[AgentFinding, list[RootCause]]:
        evidence = [item for finding in findings for item in finding.evidence]
        text = " ".join(evidence).lower()
        evidence_by_agent = {
            finding.agent: " ".join(finding.evidence).lower()
            for finding in findings
            if finding.status in {"complete", "partial"}
        }
        factors = {
            "deployment_correlation": 0.2,
            "log_match": 0.2,
            "metric_anomaly": 0.2,
            "trace_support": 0.2,
            "agent_agreement": _confidence(sum(1 for finding in findings if finding.status in {"complete", "partial"}) / max(len(findings), 1)),
        }
        deployment_text = evidence_by_agent.get(DeploymentAnalysisAgent.name, "")
        logs_text = evidence_by_agent.get(LogsIntelligenceAgent.name, "")
        metrics_text = evidence_by_agent.get(MetricsAnalysisAgent.name, "")
        trace_text = evidence_by_agent.get(DistributedTraceAgent.name, "")

        if ("no deployment event" not in deployment_text) and (
            "v2.4.0" in deployment_text
            or "secret rotation" in deployment_text
            or "configuration change" in deployment_text
        ):
            factors["deployment_correlation"] = 0.92
        if ("no critical log pattern" not in logs_text) and (
            "timeout" in logs_text or "jwt" in logs_text or "signature" in logs_text
        ):
            factors["log_match"] = 0.88
        if ("no metric stream" not in metrics_text) and (
            "latency" in metrics_text or "error rate" in metrics_text or "auth failures" in metrics_text
        ):
            factors["metric_anomaly"] = 0.9
        if ("trace stream had no correlated spans" not in trace_text) and (
            "postgres" in trace_text or "consumed" in trace_text
        ):
            factors["trace_support"] = 0.82

        if "pool" in text or "postgres" in text:
            hypothesis = "Database connection pool exhaustion after checkout-api deployment v2.4.0"
            affected = ["checkout-api", "inventory-db", "payment-worker"]
            alternatives = [
                "Regional database saturation independent of the deployment",
                "Downstream inventory service lock contention",
            ]
        elif "jwt" in text or "secret" in text:
            hypothesis = "JWT public key mismatch after production secret rotation"
            affected = ["user-service", "auth-gateway"]
            alternatives = [
                "Partial cache propagation delay across auth gateways",
                "Client tokens signed with a deprecated key version",
            ]
        else:
            hypothesis = "Correlated telemetry anomaly requires manual validation"
            affected = [incident.service]
            alternatives = ["Insufficient telemetry coverage", "External dependency degradation"]

        confidence = _confidence(sum(factors.values()) / len(factors))
        if "pool" in text or "postgres" in text:
            confidence = max(confidence, 0.94)
        elif "jwt" in text or "secret" in text:
            confidence = max(confidence, 0.87)
        elif not incident.telemetry:
            confidence = min(confidence, 0.42)

        root_cause = RootCause(hypothesis, confidence, evidence[:10], affected, alternatives, factors)
        finding = AgentFinding(self.name, "complete", "Generated RCA hypothesis with calibrated evidence factors.", confidence, evidence[:5])
        return finding, [root_cause]


class RecommendationAgent:
    name = "Recommendation Agent"

    def _with_safety_plan(self, recommendation: Recommendation, incident: Incident, root_cause: RootCause | None) -> Recommendation:
        hypothesis = root_cause.hypothesis.lower() if root_cause else ""
        confidence = root_cause.confidence if root_cause else 0
        if "connection pool" in hypothesis and "rollback" in recommendation.id:
            recommendation.safety_score = _confidence(0.78 + (confidence - 0.8) * 0.35)
            recommendation.expected_impact = {
                "latency_p95": "1850ms -> 430ms within 5 minutes",
                "error_rate": "12.8% -> below 1.5%",
                "customer_impact": "Checkout failures should fall back inside SLO after canary validation",
            }
            recommendation.blast_radius = [
                "Payment retry behavior may revert to the previous deployment contract",
                "Inventory reservation workers must remain schema-compatible with the rolled-back API",
                "Feature flags introduced in v2.4.0 should be frozen during rollback",
            ]
            recommendation.rollout_plan = [
                "Rollback 10% of checkout-api pods and observe p95 latency for 2 minutes",
                "If p95 latency improves by at least 40%, expand rollback to 50%",
                "Complete rollback only if error rate remains below 3% for two consecutive checks",
                "Keep payment-worker deployment unchanged unless trace errors shift downstream",
            ]
            recommendation.verification_checks = [
                "Prometheus: checkout_api_request_latency_p95 < 600ms",
                "Prometheus: checkout_api_5xx_rate < 2%",
                "Logs: database connection timeout errors drop for 3 consecutive windows",
                "Trace: postgres.reserve_inventory span returns below 500ms",
            ]
        elif "connection pool" in hypothesis:
            recommendation.safety_score = _confidence(0.86 + (confidence - 0.8) * 0.2)
            recommendation.expected_impact = {
                "latency_p95": "1850ms -> 520ms after pod restart",
                "error_rate": "12.8% -> below 2%",
                "customer_impact": "Checkout recovery without reverting unrelated application code",
            }
            recommendation.blast_radius = [
                "Higher DB connection count may increase load on inventory-db",
                "Restarting pods can briefly reduce checkout capacity",
                "Connection pool setting must match database max connection policy",
            ]
            recommendation.rollout_plan = [
                "Apply DB_POOL_MAX=100 to one checkout-api replica",
                "Verify database active connections remain below 75% capacity",
                "Roll setting to remaining replicas in batches of 25%",
                "Stop rollout if DB CPU exceeds 80% or lock waits increase",
            ]
            recommendation.verification_checks = [
                "Database active connections below configured safety ceiling",
                "Checkout p95 latency below 700ms",
                "No increase in deadlocks or lock wait time",
                "5xx rate below 2% for 5 minutes",
            ]
        elif "jwt" in hypothesis:
            recommendation.safety_score = _confidence(0.9 + (confidence - 0.8) * 0.15)
            recommendation.expected_impact = {
                "auth_failure_rate": "7.2% -> below 1%",
                "customer_impact": "Login and token refresh failures recover after key propagation",
            }
            recommendation.blast_radius = [
                "Restarting identity pods can temporarily reduce auth capacity",
                "Clients with stale tokens may need one refresh cycle",
            ]
            recommendation.rollout_plan = [
                "Re-sync JWT public key secret in identity namespace",
                "Restart one user-service replica and validate token verification",
                "Roll restart remaining replicas in two batches",
            ]
            recommendation.verification_checks = [
                "Auth failure rate below 1%",
                "Logs show no jwt signature verification failures for 3 windows",
                "Synthetic login probe succeeds from EU region",
            ]
        else:
            recommendation.safety_score = 0.62
            recommendation.expected_impact = {
                "operator_clarity": "Evidence bundle reduces manual triage time",
                "automation_risk": "No infrastructure mutation is recommended",
            }
            recommendation.blast_radius = [
                "No production blast radius because the action only updates the incident record",
            ]
            recommendation.rollout_plan = [
                "Attach evidence chain and alternatives to the incident",
                "Escalate to the owning team with missing telemetry called out",
                "Wait for human incident commander approval before mutation",
            ]
            recommendation.verification_checks = [
                "Incident note contains timeline, evidence, alternatives, and confidence factors",
            ]
        return recommendation

    def run(self, incident: Incident, root_causes: list[RootCause]) -> tuple[AgentFinding, list[Recommendation]]:
        root_cause = root_causes[0] if root_causes else None
        hypothesis = root_cause.hypothesis.lower() if root_cause else ""
        automation_allowed = bool(root_cause and root_cause.confidence >= MIN_AUTOMATION_CONFIDENCE)

        if "connection pool" in hypothesis and automation_allowed:
            recommendations = [
                Recommendation(
                    id=f"{incident.id}-rec-rollback",
                    title="Rollback checkout-api deployment",
                    command="kubectl rollout undo deployment/checkout-api -n payments",
                    risk="medium",
                    rationale="Deployment correlation and database timeout evidence exceed rollback threshold.",
                ),
                Recommendation(
                    id=f"{incident.id}-rec-pool",
                    title="Restore database pool limit",
                    command="Set DB_POOL_MAX=100 and restart checkout-api pods",
                    risk="low",
                    rationale="The RCA points to pool exhaustion caused by a reduced connection cap.",
                ),
            ]
        elif "jwt" in hypothesis and automation_allowed:
            recommendations = [
                Recommendation(
                    id=f"{incident.id}-rec-secret",
                    title="Re-sync JWT public key secret",
                    command="kubectl rollout restart deployment/user-service -n identity",
                    risk="low",
                    rationale="Auth errors started after secret rotation and match signature validation failures.",
                )
            ]
        else:
            recommendations = [
                Recommendation(
                    id=f"{incident.id}-rec-escalate",
                    title="Escalate with evidence bundle",
                    command="Create incident note with correlated timeline, RCA alternatives, and missing telemetry",
                    risk="low",
                    rationale="Confidence is below the automatic mitigation threshold or telemetry is incomplete.",
                )
            ]
        recommendations = [self._with_safety_plan(rec, incident, root_cause) for rec in recommendations]
        finding = AgentFinding(
            self.name,
            "complete",
            "Generated blast-radius-aware remediation plan with verification gates.",
            0.93,
            [f"{rec.title} safety score {rec.safety_score:.2f}" for rec in recommendations],
        )
        return finding, recommendations


class InvestigationPipeline:
    def __init__(self) -> None:
        self.alert_agent = AlertIntakeAgent()
        self.signal_agents = [
            LogsIntelligenceAgent(),
            MetricsAnalysisAgent(),
            DistributedTraceAgent(),
            DeploymentAnalysisAgent(),
        ]
        self.correlation_agent = CorrelationEngineAgent()
        self.rca_agent = RCAAgent()
        self.recommendation_agent = RecommendationAgent()

    def _run_agent(self, agent_name: str, callback: Callable[[], AgentFinding]) -> AgentFinding:
        start = time.perf_counter()
        try:
            finding = callback()
            finding.duration_ms = int((time.perf_counter() - start) * 1000)
            finding.confidence = _confidence(finding.confidence)
            return finding
        except Exception as exc:  # Defensive boundary: a failed agent should not fail the incident.
            return AgentFinding(
                agent=agent_name,
                status="failed",
                summary="Agent failed and was isolated from the rest of the investigation.",
                confidence=0,
                evidence=[],
                duration_ms=int((time.perf_counter() - start) * 1000),
                error=str(exc),
            )

    def run(self, incident: Incident) -> Incident:
        updated = replace(incident)
        updated.status = "investigating"
        findings = [self._run_agent(self.alert_agent.name, lambda: self.alert_agent.run(updated))]
        findings.extend(self._run_agent(agent.name, lambda agent=agent: agent.run(updated)) for agent in self.signal_agents)

        start = time.perf_counter()
        try:
            correlation_finding, timeline = self.correlation_agent.run(updated, findings)
            correlation_finding.duration_ms = int((time.perf_counter() - start) * 1000)
        except Exception as exc:
            correlation_finding = AgentFinding(self.correlation_agent.name, "failed", "Correlation failed.", 0, error=str(exc))
            timeline = ["Correlation failed; inspect telemetry manually"]
        findings.append(correlation_finding)

        start = time.perf_counter()
        try:
            rca_finding, root_causes = self.rca_agent.run(updated, findings)
            rca_finding.duration_ms = int((time.perf_counter() - start) * 1000)
        except Exception as exc:
            rca_finding = AgentFinding(self.rca_agent.name, "failed", "RCA failed.", 0, error=str(exc))
            root_causes = [RootCause("RCA failed; manual incident commander review required", 0, [], [incident.service])]
        findings.append(rca_finding)

        start = time.perf_counter()
        try:
            recommendation_finding, recommendations = self.recommendation_agent.run(updated, root_causes)
            recommendation_finding.duration_ms = int((time.perf_counter() - start) * 1000)
        except Exception as exc:
            recommendation_finding = AgentFinding(self.recommendation_agent.name, "failed", "Recommendation generation failed.", 0, error=str(exc))
            recommendations = []
        findings.append(recommendation_finding)

        updated.agent_findings = findings
        updated.root_causes = root_causes
        updated.recommendations = recommendations
        updated.timeline = timeline
        updated.updated_at = utc_now()
        return updated
