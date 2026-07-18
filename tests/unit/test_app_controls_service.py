from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from api.application.admin.app_controls import APP_CONTROLS_ID, AppControlsService


class _AppControlsCollection:
    def __init__(self) -> None:
        self.doc: dict[str, Any] | None = None
        self.last_update: dict[str, Any] | None = None

    def find_one(self, query, projection=None):
        _ = projection
        if query.get("control_id") == APP_CONTROLS_ID:
            return dict(self.doc) if self.doc else None
        return None

    def find_one_and_update(self, query, update, upsert=False, return_document=None):
        _ = return_document
        self.last_update = update
        if query.get("control_id") != APP_CONTROLS_ID:
            return None
        if self.doc is None:
            if not upsert:
                return None
            self.doc = {"control_id": APP_CONTROLS_ID}
            self.doc.update(update.get("$setOnInsert", {}))
        self.doc.update(update.get("$set", {}))
        return dict(self.doc)


class _Db:
    def __init__(self, collection: _AppControlsCollection) -> None:
        self.collection = collection

    def __getitem__(self, name: str):
        _ = name
        return self.collection


def test_app_controls_update_keeps_created_on_insert_only_metadata():
    collection = _AppControlsCollection()
    service = AppControlsService(_Db(collection), config={})
    actor = SimpleNamespace(username="coyote3.admin")

    result = service.update_controls(
        {
            "celery": {"ingest_watch_enabled": False},
            "retention": {"disk_log_days": 45},
        },
        actor=actor,
    )

    assert result["controls"]["created_on"] is not None
    assert result["controls"]["updated_by"] == "coyote3.admin"
    assert result["controls"]["celery"]["ingest_watch_enabled"] is False
    assert result["controls"]["retention"]["disk_log_days"] == 45
    assert "created_on" not in collection.last_update["$set"]
    assert "created_on" in collection.last_update["$setOnInsert"]


def test_app_controls_update_validates_existing_created_on_metadata():
    created_on = datetime(2026, 7, 17, 16, 2, 6, 74000, tzinfo=timezone.utc)
    collection = _AppControlsCollection()
    collection.doc = {
        "control_id": APP_CONTROLS_ID,
        "created_on": created_on,
        "updated_by": "coyote3.admin",
        "updated_on": created_on,
        "celery": {"enabled": True},
        "retention": {"audit_events_days": 730},
        "modules": {"dna_enabled": True},
    }
    service = AppControlsService(_Db(collection), config={})

    result = service.update_controls({"modules": {"rna_enabled": False}})

    assert result["controls"]["created_on"] == created_on
    assert result["controls"]["modules"]["rna_enabled"] is False
    assert "created_on" not in collection.last_update["$set"]
