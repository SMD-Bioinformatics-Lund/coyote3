from __future__ import annotations

import os
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from api.application.admin.app_controls import (
    AppControlsService,
    _task_summary,
    _worker_runtime_details,
)
from api.config.contracts.application import OPERATIONAL_COLLECTIONS
from api.contracts.public import PublicModulesPayload


class _AppControlsCollection:
    def __init__(self) -> None:
        self.doc: dict[str, Any] | None = None
        self.last_update: dict[str, Any] | None = None
        self.last_delete_query: dict[str, Any] | None = None
        self.database: Any | None = None

    def find_one(self, query, projection=None):
        _ = projection
        if query.get("control_id") == OPERATIONAL_COLLECTIONS.app_controls_document_id:
            return dict(self.doc) if self.doc else None
        return None

    def find_one_and_update(self, query, update, upsert=False, return_document=None):
        _ = return_document
        self.last_update = update
        if query.get("control_id") != OPERATIONAL_COLLECTIONS.app_controls_document_id:
            return None
        if self.doc is None:
            if not upsert:
                return None
            self.doc = {"control_id": OPERATIONAL_COLLECTIONS.app_controls_document_id}
            self.doc.update(update.get("$setOnInsert", {}))
        self.doc.update(update.get("$set", {}))
        return dict(self.doc)

    def delete_many(self, query):
        self.last_delete_query = query
        return SimpleNamespace(deleted_count=3)


class _Db:
    def __init__(self, collection: _AppControlsCollection) -> None:
        self.collection = collection
        self.collection.database = self

    def __getitem__(self, name: str):
        _ = name
        return self.collection


def test_app_controls_update_keeps_created_on_insert_only_metadata():
    collection = _AppControlsCollection()
    service = AppControlsService(_Db(collection), identity_db=_Db(collection), config={})
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
        "control_id": OPERATIONAL_COLLECTIONS.app_controls_document_id,
        "created_on": created_on,
        "updated_by": "coyote3.admin",
        "updated_on": created_on,
        "celery": {"enabled": True},
        "retention": {"audit_events_days": 730},
        "modules": {"dna_analysis_enabled": True},
    }
    service = AppControlsService(_Db(collection), identity_db=_Db(collection), config={})

    result = service.update_controls({"modules": {"rna_analysis_enabled": False}})

    assert result["controls"]["created_on"] == created_on
    assert result["controls"]["modules"]["rna_analysis_enabled"] is False
    assert "created_on" not in collection.last_update["$set"]


def test_public_module_payload_exposes_only_module_availability_metadata():
    collection = _AppControlsCollection()
    collection.doc = {
        "control_id": OPERATIONAL_COLLECTIONS.app_controls_document_id,
        "modules": {"reports_enabled": False},
    }
    service = AppControlsService(_Db(collection), identity_db=_Db(collection), config={})

    payload = service.public_module_payload()

    assert payload["modules"]["reports"]["enabled"] is False
    assert payload["modules"]["reports"]["label"] == "Clinical reporting"
    assert "control_field" not in payload["modules"]["reports"]
    assert payload["curation"]["tiering"] == {
        "small_variant": True,
        "cnv": False,
        "fusion": True,
        "translocation": False,
    }
    validated = PublicModulesPayload.model_validate(payload).model_dump()
    assert validated["curation"] == payload["curation"]


def test_app_controls_persist_resource_tiering_switches():
    collection = _AppControlsCollection()
    service = AppControlsService(_Db(collection), identity_db=_Db(collection), config={})

    result = service.update_controls(
        {"curation": {"tiering": {"cnv_enabled": True, "fusion_enabled": False}}}
    )

    tiering = result["controls"]["curation"]["tiering"]
    assert tiering["cnv_enabled"] is True
    assert tiering["fusion_enabled"] is False
    assert tiering["small_variant_enabled"] is True
    assert collection.last_update["$set"]["curation"]["tiering"]["cnv_enabled"] is True


def test_runtime_status_observes_active_tasks_before_worker_metadata(monkeypatch):
    from api.celery_app import celery_app

    calls: list[str] = []
    worker = "celery@worker-1"

    class _Inspect:
        def active(self):
            calls.append("active")
            return {
                worker: [
                    {
                        "id": "ingest-1",
                        "name": "api.tasks.ingest.ingest_watch_directory_once",
                        "delivery_info": {"routing_key": "ingest"},
                    }
                ]
            }

        def reserved(self):
            calls.append("reserved")
            return {worker: []}

        def scheduled(self):
            calls.append("scheduled")
            return {worker: []}

        def stats(self):
            calls.append("stats")
            return {worker: {"pool": {"max-concurrency": 2}, "total": {}}}

        def registered(self):
            calls.append("registered")
            return {worker: ["api.tasks.ingest.ingest_watch_directory_once"]}

        def active_queues(self):
            calls.append("active_queues")
            return {worker: [{"name": "ingest"}]}

    def _inspect(*, timeout):
        assert timeout == 1.5
        return _Inspect()

    monkeypatch.setattr(celery_app.control, "inspect", _inspect)
    controls = _AppControlsCollection()
    service = AppControlsService(_Db(controls), identity_db=_Db(controls), config={})

    runtime = service.runtime_status()["celery"]

    assert calls[0] == "active"
    assert runtime["active_count"] == 1
    assert runtime["reserved_count"] == 0
    assert runtime["tasks"][0]["task_id"] == "ingest-1"
    assert runtime["inspection_timeout_seconds"] == 1.5


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


def test_cleanup_disk_logs_gzips_and_deletes_by_retention(tmp_path):
    collection = _AppControlsCollection()
    collection.doc = {
        "control_id": OPERATIONAL_COLLECTIONS.app_controls_document_id,
        "retention": {"disk_log_days": 30, "gzip_disk_logs_after_days": 1},
    }
    service = AppControlsService(
        _Db(collection), identity_db=_Db(collection), config={"LOGS": str(tmp_path)}
    )
    compressible = tmp_path / "api.log"
    expired = tmp_path / "worker.log"
    recent = tmp_path / "recent.log"
    compressible.write_text("compress me", encoding="utf-8")
    expired.write_text("delete me", encoding="utf-8")
    recent.write_text("keep me", encoding="utf-8")
    now = datetime.now(timezone.utc).timestamp()
    os.utime(compressible, (now - 2 * 86_400, now - 2 * 86_400))
    os.utime(expired, (now - 31 * 86_400, now - 31 * 86_400))

    result = service.cleanup_disk_logs()

    assert result["status"] == "ok"
    assert result["gzipped"] == 1
    assert result["deleted"] == 1
    assert (tmp_path / "api.log.gz").exists()
    assert not compressible.exists()
    assert not expired.exists()
    assert recent.exists()


def test_cleanup_audit_events_only_deletes_expired_operational_events():
    collection = _AppControlsCollection()
    collection.doc = {
        "control_id": OPERATIONAL_COLLECTIONS.app_controls_document_id,
        "retention": {"audit_events_days": 90},
    }
    service = AppControlsService(_Db(collection), identity_db=_Db(collection), config={})

    result = service.cleanup_audit_events()

    assert result["deleted"] == 3
    assert collection.last_delete_query == {
        "retention_class": "operational",
        "occurred_at": {"$lt": result["cutoff"]},
    }


def test_run_maintenance_audits_failure_without_exposing_error_text(monkeypatch):
    events: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    audit = SimpleNamespace(record=lambda *args, **kwargs: events.append((args, kwargs)))
    controls = _AppControlsCollection()
    service = AppControlsService(
        _Db(controls), identity_db=_Db(controls), config={}, audit_service=audit
    )
    monkeypatch.setattr(
        service, "cleanup_audit_events", lambda: (_ for _ in ()).throw(OSError("secret path"))
    )

    try:
        service.run_maintenance()
    except OSError:
        pass
    else:
        raise AssertionError("maintenance failure should propagate to Celery")

    assert events[0][0][0] == "maintenance.retention.failed"
    assert events[0][1]["metadata"] == {"error_type": "OSError"}
