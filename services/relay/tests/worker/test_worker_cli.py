"""Worker entry point preserves the queue and Celery's operational exit status."""

from unittest.mock import Mock

import pytest
from coyote_api.config.runtime_settings import DefaultConfig

from coyote_relay.celery_app import celery_app
from coyote_relay.worker import main


@pytest.mark.parametrize("status", [None, 0, 1, 2])
def test_worker_startup_exit_status_is_not_hidden(monkeypatch, status):
    start = Mock(return_value=status)
    monkeypatch.setattr(celery_app, "start", start)
    assert main(["--loglevel", "INFO"]) == status
    start.assert_called_once_with(
        ["worker", "--queues", DefaultConfig.CELERY_INGEST_QUEUE, "--loglevel", "INFO"]
    )
