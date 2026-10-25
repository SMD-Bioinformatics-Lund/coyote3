"""Document leases distinguish users and tabs, expire, and reject stale ownership."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import mongomock
import pytest

from api.infra.mongo.repositories.edit_leases import MongoEditLeaseRepository
from coyote3.application.editing import DocumentEditing
from coyote3.application.operations.editing import DocumentEditors, EditableResource
from coyote3.application.operations.runtime import ApplicationRuntime
from coyote3.domain.exceptions import AppError


@pytest.fixture
def editing():
    """Use a fixed clock without a TTL index so expiry is enforced by queries."""
    now = [datetime(2030, 1, 1, tzinfo=UTC)]
    repository = MongoEditLeaseRepository(
        SimpleNamespace(coyote_db=mongomock.MongoClient(tz_aware=True).test)
    )
    return DocumentEditing(repository, clock=lambda: now[0]), now


def test_competing_users_and_tabs_cannot_share_lease(editing):
    service, _ = editing
    first, other_tab, second_user = uuid4(), uuid4(), uuid4()
    assert service.acquire("draft", "one", owner="alice", editor_id=first).owned
    for owner, session in (("alice", other_tab), ("bob", second_user)):
        status = service.acquire("draft", "one", owner=owner, editor_id=session)
        assert not status.owned
        assert status.owner == "alice"
        assert "editor_id" not in status.model_dump()
        with pytest.raises(AppError) as error:
            service.require_owner("draft", "one", owner=owner, editor_id=session)
        assert error.value.status_code == 409
    assert service.acquire("draft", "two", owner="bob", editor_id=second_user).owned


def test_expiry_and_stale_release_do_not_affect_successor(editing):
    service, now = editing
    first, successor = uuid4(), uuid4()
    service.acquire("draft", "one", owner="alice", editor_id=first)
    now[0] += service.lifetime
    with pytest.raises(AppError):
        service.renew("draft", "one", owner="alice", editor_id=first)
    assert service.acquire("draft", "one", owner="bob", editor_id=successor).owned
    service.release("draft", "one", owner="alice", editor_id=first)
    service.require_owner("draft", "one", owner="bob", editor_id=successor)


def test_renewal_extends_ownership_and_release_is_idempotent(editing):
    service, now = editing
    session = uuid4()
    acquired = service.acquire("draft", "one", owner="alice", editor_id=session)
    now[0] += timedelta(seconds=30)
    renewed = service.renew("draft", "one", owner="alice", editor_id=session)
    assert renewed.expires_at == acquired.expires_at + timedelta(seconds=30)
    service.release("draft", "one", owner="alice", editor_id=session)
    service.release("draft", "one", owner="alice", editor_id=session)
    with pytest.raises(AppError):
        service.require_owner("draft", "one", owner="alice", editor_id=session)


def test_session_is_required_and_keys_do_not_collide(editing):
    service, _ = editing
    with pytest.raises(AppError) as error:
        service.require_owner("draft", "one", owner="alice", editor_id=None)
    assert error.value.category == "edit_lease_required"
    assert service.key("a:b", "c") != service.key("a", "b:c")


def editor_runtime(service, actor, session, load):
    """Bind current permission checks and canonical document lookup to the real runtime."""
    policy = SimpleNamespace(
        permission_allowed=lambda _user, permission, **_: permission in actor.permissions
    )
    runtime = ApplicationRuntime(
        authenticate=lambda: actor,
        policy_factory=lambda _: policy,
        sample_loader=lambda _: None,
        assay_loader=lambda _: None,
        audit_access=lambda _: None,
        document_editing=service,
        editor_id=session,
    )
    editors = DocumentEditors(runtime, {"draft": EditableResource("edit", load, "id")})
    runtime.edit_guard = editors.require_owner
    return runtime, editors


def test_permission_and_system_protection_precede_acquisition(editing):
    service, _ = editing
    actor = SimpleNamespace(username="alice", permissions=set(), is_superuser=False)
    reads = []
    runtime, editors = editor_runtime(
        service, actor, uuid4(), lambda identity: reads.append(identity)
    )
    with pytest.raises(AppError) as error:
        editors.session("draft", "one", runtime.editor_id, "acquire")
    assert error.value.status_code == 403
    assert not reads
    actor.permissions.add("edit")
    editors.resources["draft"].load = lambda _: {"id": "one", "system_installed": True}
    with pytest.raises(AppError) as error:
        editors.session("draft", "one", runtime.editor_id, "acquire")
    assert error.value.status_code == 403


def test_aliases_and_sdk_writes_share_the_same_guard(editing):
    service, _ = editing
    alice = SimpleNamespace(username="alice", permissions={"edit"}, is_superuser=False)
    bob = SimpleNamespace(username="bob", permissions={"edit"}, is_superuser=False)

    def load(_):
        """Resolve either alias to the same stored identity."""
        return {"id": "canonical"}

    first, editors = editor_runtime(service, alice, uuid4(), load)
    second, other = editor_runtime(service, bob, uuid4(), load)
    assert editors.session("draft", "alias", first.editor_id, "acquire").owned
    assert not other.session("draft", "canonical", second.editor_id, "acquire").owned
    writes = []
    with pytest.raises(AppError):
        second.execute(
            "update",
            ("edit",),
            lambda *_: writes.append("bob"),
            edit_resource=("draft", "canonical"),
        )
    assert not writes
    first.execute(
        "update", ("edit",), lambda *_: writes.append("alice"), edit_resource=("draft", "alias")
    )
    assert writes == ["alice"]
    second.editor_id = None
    with pytest.raises(AppError):
        second.execute(
            "delete",
            ("edit",),
            lambda *_: writes.append("deleted"),
            edit_resource=("draft", "canonical"),
            editing_session_required=False,
        )
    assert writes == ["alice"]


def test_immediate_action_releases_lease_even_when_write_fails(editing):
    service, _ = editing
    actor = SimpleNamespace(username="alice", permissions={"edit"}, is_superuser=False)
    runtime, _ = editor_runtime(service, actor, None, lambda _: {"id": "one"})

    def fail(*_):
        """Simulate a rejected mutation after the lease was acquired."""
        raise ValueError("write rejected")

    with pytest.raises(ValueError):
        runtime.execute(
            "delete",
            ("edit",),
            fail,
            edit_resource=("draft", "one"),
            editing_session_required=False,
        )
    assert service.acquire("draft", "one", owner="bob", editor_id=uuid4()).owned


def test_related_action_retains_form_lease_and_releases_new_resource_lease(editing):
    service, _ = editing
    editor = uuid4()
    service.acquire("setup", "one", owner="alice", editor_id=editor)
    assert service.hold_for_action("setup", "one", owner="alice", editor_id=editor) is None
    release = service.hold_for_action("genelists", "shared", owner="alice", editor_id=editor)
    assert release is not None
    release()
    service.require_owner("setup", "one", owner="alice", editor_id=editor)
    assert service.acquire("genelists", "shared", owner="bob", editor_id=uuid4()).owned


def test_sample_scope_is_checked_before_acquiring_or_renewing(editing):
    """An edit grant alone cannot lock a sample outside the user's assigned scope."""
    service, _ = editing
    actor = SimpleNamespace(username="alice", is_superuser=False, asp_groups=[])
    allowed = [False]
    policy = SimpleNamespace(
        permission_allowed=lambda *_args, **_kwargs: True,
        scope_allowed=lambda *_args: allowed[0],
    )
    sample = {"_id": "sample-one", "asp_id": "synthetic", "environment": "test"}
    runtime = ApplicationRuntime(
        authenticate=lambda: actor,
        policy_factory=lambda _: policy,
        sample_loader=lambda _: sample,
        assay_loader=lambda _: None,
        audit_access=lambda _: None,
        document_editing=service,
    )
    editors = DocumentEditors(
        runtime,
        {
            "sample-filters": EditableResource(
                "sample:edit:own", lambda _: sample, "_id", sample_scoped=True
            ),
        },
    )
    session = uuid4()
    with pytest.raises(AppError) as error:
        editors.session("sample-filters", "sample-one", session, "acquire")
    assert error.value.status_code == 403
    allowed[0] = True
    assert editors.session("sample-filters", "sample-one", session, "acquire").owned
    allowed[0] = False
    with pytest.raises(AppError) as error:
        editors.session("sample-filters", "sample-one", session, "renew")
    assert error.value.status_code == 403
