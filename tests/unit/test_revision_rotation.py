from __future__ import annotations

import mongomock
import pytest

from api.infra.mongo.repositories.revision_rotation import rotate_active_revision


def test_revision_rotation_restores_active_document_when_successor_insert_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collection = mongomock.MongoClient()["revision_rotation"]["asp"]
    original_id = collection.insert_one(
        {"asp_id": "hema_gmsv1", "version": 1, "is_active": True}
    ).inserted_id

    def fail_insert(*_args, **_kwargs):
        raise RuntimeError("successor insert failed")

    monkeypatch.setattr(collection, "insert_one", fail_insert)

    with pytest.raises(RuntimeError, match="successor insert failed"):
        rotate_active_revision(
            collection,
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
