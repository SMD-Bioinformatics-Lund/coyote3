from __future__ import annotations

from coyote.application.admin.app_controls import _worker_runtime_details


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
