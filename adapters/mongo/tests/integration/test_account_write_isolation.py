"""Account updates preserve concurrent security changes and password lifecycle state."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import mongomock
import pytest
from coyote.application.accounts.users import UserManagementService
from coyote.contracts.schemas.governance import UsersDoc
from coyote.domain.exceptions import AppError
from coyote_mongo.repositories.users import UsersRepository
from mongo_test_support.settings import mongo_runtime


@pytest.fixture
def account(monkeypatch):
    """Use a synthetic persisted account and the real account service/repository."""
    collection = mongomock.MongoClient().test.users
    document = UsersDoc(
        username="synthetic",
        email="synthetic@example.test",
        firstname="Test",
        lastname="User",
        fullname="Test User",
        job_title="Reviewer",
        roles=["user"],
        auth_type=["local"],
        password="original-hash",
        must_change_password=True,
        password_action_token_hash="synthetic-token",
        password_action_purpose="reset",
        password_action_expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        ui_settings={"table_page_size": 50},
    ).model_dump(by_alias=True)
    document.pop("_id", None)
    collection.insert_one(document)
    repo = UsersRepository(SimpleNamespace(app=mongo_runtime(), users_collection=collection))
    service = UserManagementService(
        password_token_issuer=lambda **_: {},
        user_change_notifier=lambda **_: {},
        user_repository=repo,
        roles_repository=None,
        permissions_repository=None,
        assay_panel_repository=SimpleNamespace(
            group_options=lambda: [], get_all_asps=lambda **_: []
        ),
        password_hasher=lambda password: password,
    )
    return collection, repo, service


def test_administrative_edit_preserves_password_flags_tokens_and_preferences(account):
    collection, _, service = account
    before = collection.find_one()
    service.update_user(
        user_id="synthetic",
        payload={
            "form_data": {
                "email": "synthetic@example.test",
                "firstname": "Edited",
                "roles": ["user"],
                "auth_type": ["local"],
            }
        },
        actor_username="administrator",
    )
    after = collection.find_one()
    assert after["firstname"] == "Edited"
    for key in (
        "password",
        "must_change_password",
        "password_action_token_hash",
        "password_action_expires_at",
        "ui_settings",
    ):
        assert after[key] == before[key]


def test_administrator_saves_and_clears_paired_grants_atomically(account, monkeypatch):
    collection, _, service = account
    monkeypatch.setattr(
        "coyote.application.accounts.users.available_panels",
        lambda _: [{"asp_id": "assay_a"}, {"asp_id": "assay_b"}],
    )
    grants = [
        {"asp_id": "assay_a", "environments": ["production", "development"]},
        {"asp_id": "assay_b", "environments": ["production"]},
    ]
    service.update_user(
        user_id="synthetic",
        payload={"form_data": {"email": "synthetic@example.test", "assay_access": grants}},
        actor_username="administrator",
    )
    after = collection.find_one()
    assert after["assay_access"] == grants
    assert after["asp_ids"] == ["assay_a", "assay_b"]
    assert after["environments"] == ["development", "production"]
    with pytest.raises(AppError) as denied:
        service.update_own_profile(
            username="synthetic", payload={"firstname": "Edited", "assay_access": []}
        )
    assert denied.value.status_code == 400
    service.update_own_profile(username="synthetic", payload={"firstname": "Edited"})
    assert collection.find_one()["assay_access"] == grants
    service.update_user(
        user_id="synthetic",
        payload={"form_data": {"email": "synthetic@example.test", "assay_access": []}},
        actor_username="administrator",
    )
    assert collection.find_one()["assay_access"] == []


def test_invalid_or_duplicate_paired_grants_never_write(account, monkeypatch):
    collection, _, service = account
    before = collection.find_one()
    for grants in (
        [{"asp_id": "assay_a", "environments": ["unknown"]}],
        [{"asp_id": "assay_a", "environments": ["production"]}] * 2,
        "assay_a",
    ):
        with pytest.raises(AppError) as error:
            service.update_user(
                user_id="synthetic",
                payload={"form_data": {"assay_access": grants}},
                actor_username="administrator",
            )
        assert error.value.status_code == 422
        assert collection.find_one() == before


@pytest.mark.parametrize(
    "method,payload",
    [
        ("update_own_profile", {"firstname": "Edited"}),
        ("update_own_ui_settings", {"table_page_size": 100}),
    ],
)
def test_self_service_cannot_restore_concurrently_changed_roles(
    account, monkeypatch, method, payload
):
    collection, repo, service = account
    original = repo.update_user

    def concurrent_edit(*args, **kwargs):
        collection.update_one(
            {"username": "synthetic"}, {"$set": {"roles": ["restricted"]}, "$inc": {"version": 1}}
        )
        return original(*args, **kwargs)

    monkeypatch.setattr(repo, "update_user", concurrent_edit)
    with pytest.raises(AppError) as error:
        getattr(service, method)(username="synthetic", payload=payload)
    assert error.value.status_code == 409
    assert collection.find_one()["roles"] == ["restricted"]
    assert collection.find_one()["firstname"] == "Test"


def test_profile_save_does_not_restore_password_or_consumed_token(account, monkeypatch):
    collection, repo, service = account
    original = repo.update_user

    def reset_then_save(*args, **kwargs):
        assert repo.consume_password_action_token(
            user_id="synthetic",
            token_hash="synthetic-token",
            purpose="reset",
            password_hash="reset-hash",
        )
        return original(*args, **kwargs)

    monkeypatch.setattr(repo, "update_user", reset_then_save)
    service.update_own_profile(username="synthetic", payload={"firstname": "Edited"})
    after = collection.find_one()
    assert after["password"] == "reset-hash"
    assert after["must_change_password"] is False
    assert "password_action_token_hash" not in after


@pytest.mark.parametrize(
    "change",
    [
        {"password": "reset-hash"},
        {"is_active": False},
        {"auth_type": ["ldap"]},
    ],
)
def test_password_change_rejects_changed_credentials_or_access(account, change):
    collection, repo, _ = account
    collection.update_one({"username": "synthetic"}, {"$set": change})
    before = collection.find_one()
    assert not repo.set_local_password(
        user_id="synthetic", password_hash="new-hash", expected_password_hash="original-hash"
    )
    assert collection.find_one() == before


def test_verified_password_change_preserves_providers_and_invalidates_reset_token(account):
    collection, repo, _ = account
    collection.update_one({"username": "synthetic"}, {"$set": {"auth_type": ["local", "ldap"]}})
    assert repo.set_local_password(
        user_id="synthetic", password_hash="new-hash", expected_password_hash="original-hash"
    )
    assert not repo.set_local_password(
        user_id="synthetic", password_hash="stale-hash", expected_password_hash="original-hash"
    )
    after = collection.find_one()
    assert after["password"] == "new-hash"
    assert after["auth_type"] == ["local", "ldap"]
    assert "password_action_token_hash" not in after


def test_repository_rejects_credential_fields_in_general_account_updates(account):
    _, repo, _ = account
    with pytest.raises(ValueError):
        repo.update_user(
            "synthetic", {"password": "unverified"}, fields={"password"}, expected_version=1
        )


@pytest.mark.parametrize("current_status", [True, False])
def test_non_superuser_cannot_change_superuser_status_through_edit_form(account, current_status):
    collection, _, service = account
    collection.update_one(
        {"username": "synthetic"}, {"$set": {"roles": ["superuser"], "is_active": current_status}}
    )
    with pytest.raises(AppError) as error:
        service.update_user(
            user_id="synthetic",
            actor_username="administrator",
            payload={
                "form_data": {
                    "email": "synthetic@example.test",
                    "roles": ["superuser"],
                    "is_active": not current_status,
                }
            },
        )
    assert error.value.status_code == 403
    assert collection.find_one()["is_active"] is current_status


def test_authorized_superuser_can_change_status_through_edit_form(account):
    collection, _, service = account
    collection.update_one({"username": "synthetic"}, {"$set": {"roles": ["superuser"]}})
    service.update_user(
        user_id="synthetic",
        actor_username="emergency",
        actor_is_superuser=True,
        payload={
            "form_data": {
                "email": "synthetic@example.test",
                "roles": ["superuser"],
                "is_active": False,
            }
        },
    )
    assert collection.find_one()["is_active"] is False


def test_status_toggle_rejects_account_promoted_during_authorization(account, monkeypatch):
    collection, repo, service = account
    original = repo.update_user

    def promote_then_toggle(*args, **kwargs):
        collection.update_one(
            {"username": "synthetic"}, {"$set": {"roles": ["superuser"]}, "$inc": {"version": 1}}
        )
        return original(*args, **kwargs)

    monkeypatch.setattr(repo, "update_user", promote_then_toggle)
    with pytest.raises(AppError) as error:
        service.toggle_user(user_id="synthetic")
    assert error.value.status_code == 409
    assert collection.find_one()["is_active"] is True


def test_delete_rejects_account_promoted_during_authorization(account, monkeypatch):
    collection, repo, service = account
    original = repo.delete_user

    def promote_then_delete(*args, **kwargs):
        collection.update_one(
            {"username": "synthetic"}, {"$set": {"roles": ["superuser"]}, "$inc": {"version": 1}}
        )
        return original(*args, **kwargs)

    monkeypatch.setattr(repo, "delete_user", promote_then_delete)
    with pytest.raises(AppError) as error:
        service.delete_user(user_id="synthetic")
    assert error.value.status_code == 409
    assert collection.find_one()["roles"] == ["superuser"]


def test_delete_current_account_succeeds(account):
    collection, _, service = account
    assert service.delete_user(user_id="synthetic")["status"] == "ok"
    assert collection.count_documents({}) == 0
