"""The backend projects resolved deployment inputs into narrow package-owned settings."""

import logging
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from coyote_api.config.backend import BackendSettings
from coyote_mongo.runtime_adapter import MongoAdapter


def runtime_config():
    """Return synthetic host settings with unrelated secrets and a shared Mongo endpoint."""
    return {
        "COYOTE4_MONGO_URI": "mongodb://operator:synthetic-db-secret@mongo:27017",
        "COYOTE4_DB": "application",
        "IDENTITY_DB": "identity",
        "KNOWLEDGEBASE_DB": "reference",
        "BAM_DB": "alignments",
        "ENV_NAME": "development",
        "SECRET_KEY": "synthetic-session-secret",
        "LDAP_SECRET": "synthetic-ldap-secret",
        "SMTP_PASSWORD": "synthetic-mail-secret",
        "ONCOKB_BASE_URL": "https://reference.example.test",
        "DASHBOARD_METRIC_CACHE_TTL_SECONDS": 77,
        "DASHBOARD_METRIC_CACHE_RETENTION_SECONDS": 1800,
        "DB_COLLECTIONS_CONFIG": {"primary": {"samples_collection": "samples"}},
    }


def test_package_settings_exclude_backend_secrets_and_do_not_retain_source_mapping(monkeypatch):
    config = runtime_config()
    resolved = BackendSettings.from_runtime(config)
    config["IDENTITY_DB"] = "foreign_identity"
    config["DB_COLLECTIONS_CONFIG"]["primary"]["samples_collection"] = "foreign_samples"
    assert resolved.mongo.identity_database == "identity"
    assert resolved.mongo.collections["primary"]["samples_collection"] == "samples"
    assert resolved.mongo.runtime_values()["DASHBOARD_METRIC_CACHE_TTL_SECONDS"] == 77
    assert resolved.mongo.runtime_values()["DASHBOARD_METRIC_CACHE_RETENTION_SECONDS"] == 1800
    assert resolved.public.oncokb_configured
    assert not resolved.public.clinpgx_configured
    assert set(resolved.public.model_dump()) == {"oncokb_configured", "clinpgx_configured"}
    assert (
        not {"SECRET_KEY", "LDAP_SECRET", "SMTP_PASSWORD"} & resolved.mongo.runtime_values().keys()
    )
    pool = Mock()
    pool.databases = {name: Mock() for name in ("primary", "identity", "knowledgebase", "bam")}
    factory = Mock(return_value=pool)
    monkeypatch.setattr("coyote_mongo.runtime_adapter.MongoConnections", factory)
    adapter = MongoAdapter()
    adapter.connect(resolved.mongo, logger=logging.getLogger("synthetic-adapter"))
    assert adapter.app.config == resolved.mongo.runtime_values()
    assert adapter.app.audit == resolved.mongo.audit
    assert "synthetic-db-secret" not in repr(adapter.app)


def test_adapter_rejects_a_whole_application_context():
    with pytest.raises(TypeError, match="MongoSettings"):
        MongoAdapter().connect(SimpleNamespace(config=runtime_config()))
