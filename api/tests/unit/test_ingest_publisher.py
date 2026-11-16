"""The server publishes allowlisted job IDs without importing worker implementations."""

from unittest.mock import Mock

import pytest
from coyote_api.app.application_factory import publish_ingest_job
from coyote_api.celery_app import celery_app
from coyote_api.config.runtime_settings import DefaultConfig


def test_publisher_sends_only_retained_identity(monkeypatch):
    send = Mock()
    monkeypatch.setattr(celery_app, "send_task", send)
    publish_ingest_job("sample_bundle", "synthetic-job")
    send.assert_called_once_with(
        "coyote_ingest.tasks.ingest_sample_bundle",
        kwargs={"job_id": "synthetic-job"},
        task_id="synthetic-job",
        queue=DefaultConfig.CELERY_INGEST_QUEUE,
    )


def test_unknown_kind_is_rejected_before_publication(monkeypatch):
    send = Mock()
    monkeypatch.setattr(celery_app, "send_task", send)
    with pytest.raises(KeyError):
        publish_ingest_job("arbitrary", "synthetic-job")
    send.assert_not_called()
