"""Isolate transaction audit routing for explicitly configured disposable test databases."""

import os

import pytest


@pytest.fixture(autouse=True)
def transaction_audit_destination(monkeypatch):
    """Supply a synthetic audit destination when replica-set tests are enabled."""
    names = (
        "AUDIT_TEST_MONGO_URI",
        "ASSAY_SETUP_TEST_MONGO_URI",
        "CLINICAL_RULE_TEST_MONGO_URI",
        "REPORT_TEST_MONGO_URI",
        "LIFECYCLE_TEST_MONGO_URI",
        "CATALOG_TEST_MONGO_URI",
    )
    uri = next((os.environ[name] for name in names if os.getenv(name)), None)
    if uri:
        monkeypatch.setenv("ENV_NAME", "test")
        monkeypatch.setenv("IDENTITY_MONGO_URI", uri)
        monkeypatch.setenv("IDENTITY_DB", "coyote3_audit_integration")
