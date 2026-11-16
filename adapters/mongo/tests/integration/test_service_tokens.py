"""Managed credentials fail closed across lifecycle, scope and authentication boundaries."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import mongomock
import pytest
from coyote.application.accounts.service_tokens import ServiceTokens
from coyote.contracts.service_tokens import ServiceTokenCreate
from coyote.domain.exceptions import AppError
from coyote_mongo.repositories.service_tokens import MongoServiceTokenRepository


@pytest.fixture
def service():
    collection = mongomock.MongoClient().identity.service_tokens
    users = {"owner": {"username": "owner", "is_active": True}}
    return ServiceTokens(
        MongoServiceTokenRepository(collection),
        users=SimpleNamespace(
            user_with_id=users.get, list_active_users_for_notifications=lambda: list(users.values())
        ),
        assays=SimpleNamespace(
            get_all_asps=lambda **_: [{"asp_id": "assay_a", "display_name": "Assay A"}]
        ),
        audience="testing",
        audit=Mock(),
    )


def payload(**changes):
    """Select one real test-registry assay and one clinical environment."""
    return ServiceTokenCreate.model_validate(
        {
            "name": "Synthetic pipeline",
            "owner": "owner",
            "asp_ids": ["assay_a"],
            "environments": ["testing"],
            "operations": ["sample_bundle"],
            **changes,
        }
    )


def actor():
    """Return the administrator accountable for credential lifecycle actions."""
    return SimpleNamespace(username="issuer")


def test_issue_discloses_once_stores_only_digest_and_audits_metadata(service):
    issued = service.issue(payload(), actor=actor())
    record = service.repository.collection.find_one()
    assert issued.token not in str(record)
    assert "token_hash" in record
    assert "token_hash" not in str(service.list_metadata())
    assert "token_hash" not in str(service.audit.record.call_args)
    assert issued.token not in str(service.audit.record.call_args)
    assert service.resolve(issued.token).token_id == issued.metadata.token_id
    assert service.list_metadata()[0].last_used_at is not None
    assert service.list_metadata()[0].expires_at.utcoffset() == timedelta(0)


@pytest.mark.parametrize(
    "failure", ["expired", "revoked", "audience", "owner_inactive", "owner_deleted", "tampered"]
)
def test_invalid_credentials_cannot_resolve(service, failure):
    issued = service.issue(payload(), actor=actor())
    token = issued.token
    if failure == "expired":
        service.repository.collection.update_one(
            {}, {"$set": {"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)}}
        )
    elif failure == "revoked":
        service.revoke(issued.metadata.token_id, actor=actor())
    elif failure == "audience":
        service.audience = "production"
    elif failure == "owner_inactive":
        service.users.user_with_id("owner")["is_active"] = False
    elif failure == "owner_deleted":
        service.users.user_with_id = lambda _: None
    else:
        token += "tampered"
    assert service.resolve(token) is None


def test_revoke_is_idempotent_and_does_not_change_other_credentials(service):
    first = service.issue(payload(), actor=actor())
    second = service.issue(payload(), actor=actor())
    revoked = service.revoke(first.metadata.token_id, actor=actor())
    again = service.revoke(first.metadata.token_id, actor=SimpleNamespace(username="another_admin"))
    assert again.revoked_by == revoked.revoked_by
    assert again.revoked_at == revoked.revoked_at
    assert service.resolve(second.token) is not None
    with pytest.raises(AppError) as error:
        service.revoke("missing", actor=actor())
    assert error.value.status_code == 404


@pytest.mark.parametrize("failure", ["missing", "rejected", "exception"])
def test_issuance_never_discloses_an_unaudited_live_credential(service, failure):
    """Audit failure cannot leave a usable credential after creation has failed."""
    if failure == "missing":
        service.audit = None
    elif failure == "rejected":
        service.audit.record.return_value = None
    else:
        service.audit.record.side_effect = RuntimeError("Synthetic audit failure")
    with pytest.raises((AppError, RuntimeError)):
        service.issue(payload(), actor=actor())
    assert all(row.revoked_at is not None for row in service.list_metadata())


@pytest.mark.parametrize(
    "changes", [{"asp_ids": ["unknown"]}, {"environments": ["unknown"]}, {"owner": "unknown"}]
)
def test_scope_and_owner_must_be_registered(service, changes):
    with pytest.raises(AppError) as error:
        service.issue(payload(**changes), actor=actor())
    assert error.value.status_code == 422
    assert service.repository.collection.count_documents({}) == 0
