"""Ingestion audit history remains correlated, retained, and separate from job execution."""

from datetime import datetime, timedelta, timezone

import mongomock
from coyote_mongo.repositories.audit import AuditRepository


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
