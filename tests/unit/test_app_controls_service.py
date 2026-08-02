from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from api.application.admin.app_controls import (
    APP_CONTROLS_ID,
    AppControlsService,
    _task_summary,
    _worker_runtime_details,
    default_app_controls,
    merge_controls,
)


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
            "celery": {"sample_ingest_enabled": False},
            "retention": {"disk_log_days": 45},
        },
        actor=actor,
    )

    assert result["controls"]["created_on"] is not None
    assert result["controls"]["updated_by"] == "coyote3.admin"
    assert result["controls"]["celery"]["sample_ingest_enabled"] is False
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
        "modules": {"dna_analysis_enabled": True},
    }
    service = AppControlsService(_Db(collection), config={})

    result = service.update_controls({"modules": {"rna_analysis_enabled": False}})

    assert result["controls"]["created_on"] == created_on
    assert result["controls"]["modules"]["rna_analysis_enabled"] is False
    assert "created_on" not in collection.last_update["$set"]


def test_merge_controls_migrates_legacy_ingest_and_analysis_switches():
    controls = merge_controls(
        default_app_controls({}),
        {
            "celery": {
                "ingest_bundle_enabled": True,
                "ingest_dependents_enabled": False,
            },
            "modules": {"dna_enabled": False, "rna_enabled": True},
        },
    )

    assert controls.celery.sample_ingest_enabled is False
    assert controls.modules.dna_analysis_enabled is False
    assert controls.modules.rna_analysis_enabled is True


def test_public_module_payload_exposes_only_module_availability_metadata():
    collection = _AppControlsCollection()
    collection.doc = {
        "control_id": APP_CONTROLS_ID,
        "modules": {"reports_enabled": False},
    }
    service = AppControlsService(_Db(collection), config={})

    payload = service.public_module_payload()

    assert payload["modules"]["reports"]["enabled"] is False
    assert payload["modules"]["reports"]["label"] == "Clinical reporting"
    assert "control_field" not in payload["modules"]["reports"]


def test_task_summary_excludes_task_payloads_and_normalizes_scheduled_requests():
    rows = {
        "celery@worker-1": [
            {
                "eta": "2026-08-02T10:00:00Z",
                "request": {
                    "id": "task-1",
                    "name": "api.tasks.maintenance.run_retention_maintenance",
                    "args": ["must-not-leak"],
                    "kwargs": {"secret": "must-not-leak"},
                    "delivery_info": {"routing_key": "celery"},
                },
            }
        ]
    }

    result = _task_summary(rows, state="scheduled")

    assert result == [
        {
            "worker": "celery@worker-1",
            "state": "scheduled",
            "task_id": "task-1",
            "task_name": "api.tasks.maintenance.run_retention_maintenance",
            "queue": "celery",
            "eta": "2026-08-02T10:00:00Z",
            "started_at": None,
        }
    ]
    assert "args" not in result[0]
    assert "kwargs" not in result[0]


def test_worker_runtime_details_reports_capacity_activity_and_consumed_queues():
    details = _worker_runtime_details(
        {
            "celery@worker-1": {
                "pid": 42,
                "uptime": 3_661,
                "pool": {"implementation": "prefork", "max-concurrency": 4},
                "total": {"task.a": 3, "task.b": 2},
            }
        },
        {"celery@worker-1": [{"id": "active"}]},
        {"celery@worker-1": [{"id": "reserved"}]},
        {"celery@worker-1": []},
        {"celery@worker-1": ["task.a", "task.b"]},
        {"celery@worker-1": [{"name": "ingest"}, {"name": "celery"}]},
    )

    assert details == [
        {
            "name": "celery@worker-1",
            "status": "online",
            "pid": 42,
            "uptime_seconds": 3_661,
            "pool": "prefork",
            "concurrency": 4,
            "processed_count": 5,
            "active_count": 1,
            "reserved_count": 1,
            "scheduled_count": 0,
            "registered_count": 2,
            "queues": ["celery", "ingest"],
        }
    ]
