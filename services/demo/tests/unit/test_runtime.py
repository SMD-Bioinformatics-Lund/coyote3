"""Demonstration queue consumers cannot start before target and credential validation."""

from importlib import import_module

import pytest
from coyote_demo import runtime
from coyote_relay import worker
from demo_test_support.deployment import demo_settings


def test_worker_preflight_runs_before_queue_consumer(monkeypatch):
    for key, value in demo_settings().items():
        monkeypatch.setenv(key, value)
    sequence = []
    monkeypatch.setattr(runtime, "validate_runtime", lambda settings: sequence.append("validated"))
    monkeypatch.setattr(worker, "main", lambda options: sequence.append(options) or 0)
    assert runtime.main(["ingest", "--concurrency=1"]) == 0
    assert sequence == ["validated", ["--loglevel=INFO", "--concurrency=1"]]


@pytest.mark.parametrize("service", ["ingest", "maintenance", "beat"])
def test_disabled_or_unsafe_demo_never_starts_queue_consumer(monkeypatch, service):
    monkeypatch.delenv("COYOTE_DEMO_ENABLED", raising=False)
    monkeypatch.setattr(worker, "main", lambda _: pytest.fail("Unsafe consumer started"))
    with pytest.raises(ValueError, match="COYOTE_DEMO_ENABLED"):
        runtime.main([service])


@pytest.mark.parametrize("service", ["maintenance", "beat"])
def test_maintenance_services_validate_first_and_keep_scheduler_state_isolated(
    monkeypatch, tmp_path, service
):
    from coyote_api.celery_app import celery_app
    from coyote_api.config import paths
    from coyote_api.config.runtime_settings import DefaultConfig

    # Keep this process's selected center; the test changes only projected demo inputs.
    import_module("coyote_demo.host")
    for key, value in demo_settings().items():
        monkeypatch.setenv(key, value)
    root = tmp_path / "data" / "coyote4_test"
    monkeypatch.setattr(paths, "COYOTE4_DATA_CONTAINER_ROOT", root)
    sequence = []
    monkeypatch.setattr(runtime, "validate_runtime", lambda settings: sequence.append("validated"))
    monkeypatch.setattr(celery_app, "start", lambda arguments: sequence.append(arguments) or 0)
    assert runtime.main([service]) == 0
    assert sequence[0] == "validated"
    arguments = sequence[1]
    if service == "maintenance":
        assert arguments == [
            "worker",
            "--queues",
            DefaultConfig.CELERY_DEFAULT_QUEUE,
            "--loglevel=INFO",
            "--concurrency=1",
        ]
        assert not root.exists()
    else:
        assert arguments == [
            "beat",
            "--loglevel=INFO",
            f"--schedule={root / 'celerybeat-schedule'}",
            f"--pidfile={root / 'celerybeat.pid'}",
        ]
        assert root.is_dir()


@pytest.mark.parametrize(
    "arguments",
    [
        ["ingest", "--broker=redis://production"],
        ["beat", "--schedule=/ordinary/celerybeat"],
        ["beat", "--concurrency=1"],
        ["maintenance", "--concurrency=0"],
    ],
)
def test_service_options_cannot_override_isolated_endpoints_or_scheduler_paths(
    monkeypatch, arguments
):
    monkeypatch.setattr(
        runtime, "validate_runtime", lambda _: pytest.fail("Invalid arguments reached runtime")
    )
    with pytest.raises(SystemExit):
        runtime.main(arguments)
