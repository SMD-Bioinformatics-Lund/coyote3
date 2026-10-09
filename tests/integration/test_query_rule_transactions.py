"""Opt-in publication checks against an explicitly selected disposable replica set."""

import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pymongo import MongoClient

from api.application.query_rules import QueryRuleService
from api.contracts.schemas.query_rules import QueryRuleDraft, QueryRuleTransition
from api.infra.mongo.repositories import query_rules as persistence


@pytest.fixture
def service(monkeypatch):
    """Create a uniquely named synthetic database only when explicitly configured."""
    uri = os.getenv("QUERY_RULE_TEST_MONGO_URI")
    if not uri:
        pytest.skip("Set QUERY_RULE_TEST_MONGO_URI to a disposable replica set")
    with MongoClient(uri, serverSelectionTimeoutMS=3000, tz_aware=True) as client:
        database = client[f"coyote3_query_rule_test_{uuid4().hex}"]

        def receipt(db, session, **values):
            """Use an isolated receipt sink to verify the shared transaction boundary."""
            db.receipts.insert_one({"event": values["event_type"]}, session=session)

        monkeypatch.setattr(persistence, "enqueue_audit", receipt)
        repository = persistence.QueryRuleRepository(
            SimpleNamespace(
                query_rule_sets_collection=database.query_rule_sets,
                query_rule_revisions_collection=database.query_rule_revisions,
            )
        )
        repository.ensure_indexes()
        try:
            yield QueryRuleService(
                repository, groups=SimpleNamespace(get=lambda key: {"group_id": key})
            )
        finally:
            client.drop_database(database.name)


def approved(service, mode):
    """Create and independently approve a synthetic group policy."""
    row = service.create(
        QueryRuleDraft(
            scope={"assay_group": "example", "analysis": "snv"},
            name="Synthetic",
            reason="Transaction test",
            content={"evidence_mode": mode},
        ),
        "author",
    )
    return service.transition(
        str(row["_id"]),
        "approve",
        QueryRuleTransition(
            expected_revision=1,
            reason="Synthetic review",
        ),
        "reviewer",
    )


def publish(service, row):
    """Activate the inspected synthetic version."""
    return service.transition(
        str(row["_id"]),
        "publish",
        QueryRuleTransition(
            expected_revision=row["revision"],
            reason="Synthetic publication",
        ),
        "publisher",
    )


def test_publication_switches_the_unique_scope_atomically(service):
    previous = publish(service, approved(service, "paired"))
    successor = publish(service, approved(service, "case_only"))
    collection = service.repository.get_collection()
    assert collection.count_documents({"status": "published"}) == 1
    assert service.repository.get(str(previous["_id"]))["status"] == "retired"
    assert service.repository.get(str(successor["_id"]))["status"] == "published"


def test_audit_failure_rolls_back_both_sides_of_publication(service, monkeypatch):
    previous = publish(service, approved(service, "paired"))
    successor = approved(service, "case_only")

    def reject_receipt(*args, **kwargs):
        """Simulate an audit persistence failure after publication writes."""
        raise RuntimeError("Synthetic receipt failure")

    monkeypatch.setattr(persistence, "enqueue_audit", reject_receipt)
    with pytest.raises(RuntimeError, match="Synthetic receipt failure"):
        publish(service, successor)
    assert service.repository.get(str(previous["_id"]))["status"] == "published"
    assert service.repository.get(str(successor["_id"]))["status"] == "approved"
