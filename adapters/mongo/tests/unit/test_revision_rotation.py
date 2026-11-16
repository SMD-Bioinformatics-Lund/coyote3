from __future__ import annotations

import mongomock
import pytest
from coyote_mongo.repositories.revision_rotation import rotate_active_revision
from mongo_test_support.settings import audit_context


def test_revision_rotation_fails_closed_without_transaction_support(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collection = mongomock.MongoClient()["revision_rotation"]["asp"]
    original_id = collection.insert_one(
        {"asp_id": "hema_gmsv1", "version": 1, "is_active": True}
    ).inserted_id

    def fail_insert(*_args, **_kwargs):
        raise RuntimeError("successor insert failed")

    monkeypatch.setattr(collection, "insert_one", fail_insert)

    with pytest.raises(NotImplementedError):
        rotate_active_revision(
            collection,
            context=audit_context(),
            selector={"asp_id": "hema_gmsv1"},
            expected_version=1,
            new_document={"asp_id": "hema_gmsv1", "version": 2, "is_active": True},
            retire_fields={"retired_by": "admin", "retired_reason": "superseded"},
        )

    restored = collection.find_one({"_id": original_id})
    assert restored is not None
    assert restored["is_active"] is True
    assert "retired_by" not in restored
    assert "retired_reason" not in restored
    assert collection.count_documents({"asp_id": "hema_gmsv1"}) == 1
