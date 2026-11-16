"""Standalone persistence settings reject unrelated configuration and ambient routing."""

from unittest.mock import MagicMock

import pytest
from coyote_mongo.config.settings import MongoSettings
from coyote_mongo.repositories.audit_outbox import AuditOutboxRepository, audit_route, enqueue_audit
from pydantic import ValidationError


def settings(**overrides):
    """Construct an independent adapter configuration without API imports or environment loading."""
    return MongoSettings(
        **{
            "uri": "mongodb://operator:synthetic-password@mongo:27017",
            "primary_database": "application",
            "identity_database": "identity",
            "knowledgebase_database": "reference",
            "bam_database": "alignments",
            "environment": "dev",
            **overrides,
        }
    )


def test_settings_hide_credentials_and_reject_unrelated_inputs():
    assert "synthetic-password" not in repr(settings())
    with pytest.raises(ValidationError) as failure:
        settings(ldap_password="synthetic-unrelated-secret")
    assert "synthetic-unrelated-secret" not in str(failure.value)


def test_settings_reject_collisions_and_invalid_pool_before_connecting():
    with pytest.raises(RuntimeError, match="must be different"):
        settings(identity_database="application")
    with pytest.raises(ValidationError, match="min_pool_size"):
        settings(min_pool_size=5, max_pool_size=2)
    with pytest.raises(ValidationError):
        settings(connect_timeout_ms=-1)


def test_explicit_audit_context_preserves_routes_and_ignores_process_changes(monkeypatch):
    selected = settings()
    context = selected.audit
    assert context.route == audit_route(selected.runtime_values())
    monkeypatch.setenv("ENV_NAME", "production")
    monkeypatch.setenv("IDENTITY_DB", "another_center")
    monkeypatch.setenv("IDENTITY_MONGO_URI", "mongodb://other-center:27017")
    database = MagicMock()
    database.name = "application"
    enqueue_audit(
        database,
        MagicMock(in_transaction=True, client=database.client),
        context=context,
        event_type="synthetic.created",
        resource_type="synthetic",
        resource_id="record",
    )
    receipt = database.__getitem__.return_value.insert_one.call_args.args[0]
    assert receipt["route"] == context.route
    assert receipt["event"]["source"]["environment"] == "development"


def test_queue_delivery_rejects_missing_deployment_route_before_reading():
    database = MagicMock()
    repository = AuditOutboxRepository(database)
    with pytest.raises(ValueError, match="explicit deployment route"):
        repository.deliver(MagicMock(), environment="test", route="")
    repository.collection.find.assert_not_called()
