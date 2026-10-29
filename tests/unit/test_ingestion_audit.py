"""Ingestion audit history remains correlated, retained, and separate from job execution."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import mongomock
import pytest

from api.infra.mongo.repositories.audit import AuditRepository
from coyote3.application.operations.ingest_audit import IngestionAuditAttempt


def test_ingestion_filter_runs_before_limit_and_counts_both_stores():
    """Unrelated recent traffic cannot crowd older ingestion events out of the window."""
    db = mongomock.MongoClient(tz_aware=True).identity
    now = datetime.now(timezone.utc)
    db.audit_events.insert_one({"event_type": "ingest.attempt.succeeded", "occurred_at": now})
    db.operational_audit_events.insert_one(
        {"event_type": "ingest.upload.rejected", "occurred_at": now - timedelta(days=1)}
    )
    db.audit_events.insert_many(
        [
            {"event_type": "report.saved", "occurred_at": now + timedelta(seconds=i)}
            for i in range(1, 10)
        ]
    )
    repository = AuditRepository(
        db.audit_events, operational_collection=db.operational_audit_events
    )
    result = repository.recent_events(limit=1, ingestion_only=True)
    assert result["total"] == 2
    assert [event["event_type"] for event in result["events"]] == ["ingest.attempt.succeeded"]
    assert repository.recent_events(limit=1)["total"] == 11


def test_committed_attempt_records_correlated_actor_sample_and_retained_history():
    audit = Mock()
    actor = Mock(username="synthetic_operator")
    attempt = IngestionAuditAttempt(audit, actor=actor, source="upload", manifest="synthetic.yaml")
    attempt.succeeded({"sample_id": "synthetic-id", "sample_name": "SYNTHETIC"})
    started, completed = audit.record.call_args_list
    assert started.args[0] == "ingest.attempt.started"
    assert completed.args[0] == "ingest.attempt.succeeded"
    assert started.kwargs["metadata"]["attempt_id"] == completed.kwargs["metadata"]["attempt_id"]
    assert completed.kwargs["resource_id"] == "synthetic-id"
    assert completed.kwargs["actor"] is actor
    assert completed.kwargs["metadata"]["duration_ms"] >= 0
    assert completed.kwargs["retention_class"] == "traceability"


@pytest.mark.parametrize(
    "error,stage",
    [
        (ValueError("Invalid manifest"), "failed"),
        (RuntimeError("Lost commit response"), "unconfirmed"),
    ],
)
def test_failure_does_not_claim_an_uncertain_outcome_is_a_rejection(error, stage):
    audit = Mock()
    attempt = IngestionAuditAttempt(audit, actor="synthetic", source="api")
    attempt.failed(error)
    assert audit.record.call_args.args[0] == f"ingest.attempt.{stage}"
    assert audit.record.call_args.kwargs["outcome"] == "failure"


def test_audit_outage_never_turns_a_committed_result_into_a_retry(caplog):
    audit = Mock()
    audit.record.side_effect = OSError("Synthetic audit storage outage")
    attempt = IngestionAuditAttempt(audit, actor="synthetic", source="api")
    attempt.succeeded({"sample_id": "synthetic"})
    assert "Ingestion audit delivery failed" in caplog.text
