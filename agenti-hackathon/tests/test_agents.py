import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.agents import InvestigationPipeline
from backend.models import Incident
from backend.sample_data import build_seed_incidents
from backend.store import IncidentStore


ROOT = Path(__file__).resolve().parents[1]
TEST_DATA = ROOT / ".test-data"
TEST_DATA.mkdir(exist_ok=True)


class InvestigationPipelineTest(unittest.TestCase):
    def test_checkout_incident_generates_confident_root_cause(self) -> None:
        incident = build_seed_incidents()[0]
        updated = InvestigationPipeline().run(incident)

        self.assertEqual(updated.status, "investigating")
        self.assertGreaterEqual(updated.root_causes[0].confidence, 0.9)
        self.assertIn("connection pool", updated.root_causes[0].hypothesis.lower())
        self.assertGreaterEqual(updated.root_causes[0].confidence_factors["trace_support"], 0.8)
        self.assertGreaterEqual(len(updated.agent_findings), 7)
        self.assertGreaterEqual(len(updated.recommendations), 1)
        self.assertGreaterEqual(updated.recommendations[0].safety_score, 0.8)
        self.assertIn("latency_p95", updated.recommendations[0].expected_impact)
        self.assertGreaterEqual(len(updated.recommendations[0].blast_radius), 2)
        self.assertGreaterEqual(len(updated.recommendations[0].rollout_plan), 3)
        self.assertGreaterEqual(len(updated.recommendations[0].verification_checks), 3)

    def test_remediation_is_audited_without_losing_incident(self) -> None:
        incident = InvestigationPipeline().run(build_seed_incidents()[0])
        with TemporaryDirectory(dir=TEST_DATA, ignore_cleanup_errors=True) as directory:
            store = IncidentStore([incident], db_path=f"{directory}/incidents.db")
            recommendation_id = incident.recommendations[0].id

            updated, error = store.apply_recommendation(incident.id, recommendation_id, "test-key-1")
            repeated, repeated_error = store.apply_recommendation(incident.id, recommendation_id, "test-key-1")
            reused_key, reused_error = store.apply_recommendation(incident.id, incident.recommendations[1].id, "test-key-1")
            duplicate, duplicate_error = store.apply_recommendation(incident.id, recommendation_id, "test-key-2")

            self.assertIsNone(error)
            self.assertIsNone(repeated_error)
            self.assertIsNotNone(updated)
            self.assertIsNotNone(repeated)
            self.assertIsNone(reused_key)
            self.assertIsNone(duplicate)
            self.assertEqual(updated.status, "mitigated")
            self.assertTrue(updated.recommendations[0].applied)
            self.assertEqual(len(updated.audit_log), 1)
            self.assertEqual(len(repeated.audit_log), 1)
            self.assertIn("No infrastructure command was executed", updated.audit_log[0].result)
            self.assertEqual(reused_error, "idempotency_key was already used for a different remediation")
            self.assertEqual(duplicate_error, "recommendation already applied")

    def test_empty_telemetry_degrades_to_manual_validation(self) -> None:
        incident = Incident(
            id="inc-empty",
            title="Unknown production alert",
            service="unknown-service",
            severity="P2",
            status="open",
            started_at="2026-05-24T00:00:00+00:00",
            region="unknown",
            team="platform",
            summary="Alert arrived without correlated telemetry.",
            telemetry=[],
        )

        updated = InvestigationPipeline().run(incident)

        self.assertLess(updated.root_causes[0].confidence, 0.8)
        self.assertIn("manual validation", updated.root_causes[0].hypothesis.lower())
        self.assertEqual(updated.recommendations[0].id, "inc-empty-rec-escalate")
        self.assertLess(updated.recommendations[0].safety_score, 0.8)
        self.assertIn("No production blast radius", updated.recommendations[0].blast_radius[0])

    def test_malformed_metrics_are_partial_not_crashing(self) -> None:
        incident = build_seed_incidents()[0]
        incident.telemetry[1].payload["latency_p95_ms"] = "not-a-number"

        updated = InvestigationPipeline().run(incident)

        metrics = next(finding for finding in updated.agent_findings if finding.agent == "Metrics Analysis Agent")
        self.assertEqual(metrics.status, "partial")
        self.assertTrue(any("malformed" in item for item in metrics.evidence))

    def test_missing_trace_does_not_inflate_trace_support(self) -> None:
        incident = build_seed_incidents()[1]
        updated = InvestigationPipeline().run(incident)

        self.assertIn("jwt", updated.root_causes[0].hypothesis.lower())
        self.assertGreaterEqual(updated.root_causes[0].confidence, 0.85)
        self.assertLessEqual(updated.root_causes[0].confidence_factors["trace_support"], 0.25)
        self.assertEqual(updated.recommendations[0].id, f"{incident.id}-rec-secret")


if __name__ == "__main__":
    unittest.main()
