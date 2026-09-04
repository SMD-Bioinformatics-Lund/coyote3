"""Runtime dependency initialization tests."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
from pymongo.errors import AutoReconnect, OperationFailure

from api.app import runtime_setup
from api.infra.mongo import runtime_adapter


class _Config:
    UPPER = "value"
    lower = "ignored"

    @property
    def BROKEN(self):
        raise RuntimeError("unavailable")


@pytest.mark.parametrize(
    ("testing", "development", "env_name", "config_name"),
    [
        (True, False, "production", "TestConfig"),
        (False, True, "production", "DevelopmentConfig"),
        (False, False, "stage", "StageConfig"),
        (False, False, "staging", "StageConfig"),
        (False, False, "production", "ProductionConfig"),
    ],
)
def test_select_config_uses_runtime_mode(
    monkeypatch: pytest.MonkeyPatch,
    testing: bool,
    development: bool,
    env_name: str,
    config_name: str,
) -> None:
    selected: list[str] = []

    def config_type(name: str):
        class Config:
            @classmethod
            def validate_required_env(cls) -> None:
                selected.append(f"validated:{name}")

            def __init__(self) -> None:
                selected.append(name)

        return Config

    for name in ("TestConfig", "DevelopmentConfig", "StageConfig", "ProductionConfig"):
        monkeypatch.setattr(runtime_setup.app_config, name, config_type(name))
    monkeypatch.setenv("ENV_NAME", env_name)

    runtime_setup._select_config(testing=testing, development=development)

    assert config_name in selected
    if config_name in {"StageConfig", "ProductionConfig"}:
        assert f"validated:{config_name}" in selected


def test_config_dict_keeps_uppercase_readable_values() -> None:
    class ValidConfig:
        UPPER = "value"
        lower = "ignored"

    result = runtime_setup._config_dict(ValidConfig())

    assert result["UPPER"] == "value"
    assert "lower" not in result
    assert result["SECRET_KEY_FALLBACKS"] == []


def test_config_dict_does_not_hide_invalid_runtime_settings() -> None:
    with pytest.raises(RuntimeError, match="unavailable"):
        runtime_setup._config_dict(_Config())


def test_init_cache_assigns_created_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = object()
    calls: list[tuple[dict, str]] = []
    runtime = runtime_setup.ApiRuntimeContext(
        config={"CACHE_TYPE": "memory"}, logger=logging.getLogger("runtime-test")
    )
    monkeypatch.setattr(
        runtime_setup,
        "create_cache_backend",
        lambda *, config, logger, namespace: calls.append((config, namespace)) or backend,
    )

    runtime_setup._init_cache(runtime)

    assert runtime.cache is backend
    assert calls == [({"CACHE_TYPE": "memory"}, "api")]


def test_init_store_retries_transient_mongo_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    sleeps: list[float] = []
    runtime = runtime_setup.ApiRuntimeContext(
        config={"COYOTE3_DB": "test"}, logger=logging.getLogger("runtime-test")
    )

    def init_from_app(_runtime) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise AutoReconnect("temporary")

    monkeypatch.setattr(runtime_setup.store, "reset", lambda: None)
    monkeypatch.setattr(runtime_setup.store, "init_from_app", init_from_app)
    monkeypatch.setattr(runtime_setup.time, "sleep", sleeps.append)

    runtime_setup._init_store(runtime)

    assert attempts == 2
    assert sleeps == [2.0]


def test_init_store_does_not_retry_programming_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime_setup.store, "reset", lambda: None)
    monkeypatch.setattr(
        runtime_setup.store,
        "init_from_app",
        lambda _runtime: (_ for _ in ()).throw(ValueError("invalid configuration")),
    )
    monkeypatch.setattr(
        runtime_setup.time,
        "sleep",
        lambda _seconds: pytest.fail("programming errors must not be retried"),
    )
    runtime = runtime_setup.ApiRuntimeContext(config={}, logger=logging.getLogger("runtime-test"))

    with pytest.raises(ValueError, match="invalid configuration"):
        runtime_setup._init_store(runtime)


def test_init_store_raises_after_retry_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    runtime = runtime_setup.ApiRuntimeContext(config={}, logger=logging.getLogger("runtime-test"))

    def fail(_runtime) -> None:
        nonlocal attempts
        attempts += 1
        raise AutoReconnect("offline")

    monkeypatch.setattr(runtime_setup.store, "reset", lambda: None)
    monkeypatch.setattr(runtime_setup.store, "init_from_app", fail)
    monkeypatch.setattr(runtime_setup.time, "sleep", lambda _seconds: None)

    with pytest.raises(AutoReconnect, match="offline"):
        runtime_setup._init_store(runtime)

    assert attempts == 5


def test_create_runtime_context_initializes_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    phases: list[str] = []
    calls: list[str] = []
    config = SimpleNamespace(
        ENV_NAME="testing",
        APP_VERSION="4.0.0",
        LOG_FILE_ENABLED=False,
        LOG_LEVEL="INFO",
        LOGS="logs/api",
        COYOTE3_DB="coyote3_test",
        IDENTITY_DB="identity_test",
        KNOWLEDGEBASE_DB="knowledgebase_test",
        BAM_DB="bam_test",
    )
    monkeypatch.setattr(runtime_setup, "_select_config", lambda **_kwargs: config)
    monkeypatch.setattr(runtime_setup, "configure_json_logging", lambda **_kwargs: None)
    monkeypatch.setattr(runtime_setup, "_init_cache", lambda _runtime: calls.append("cache"))
    monkeypatch.setattr(runtime_setup, "_init_store", lambda _runtime: calls.append("store"))
    monkeypatch.setattr(runtime_setup, "AUTH_TYPE_OPTIONS", ("local",))
    monkeypatch.setattr(runtime_setup.util, "init_util", lambda: calls.append("util"))
    monkeypatch.setattr(
        runtime_setup,
        "set_startup_phase_duration",
        lambda *, phase, duration_ms: phases.append(phase),
    )

    result = runtime_setup.create_runtime_context(testing=True)

    assert result.config["ENV_NAME"] == "testing"
    assert calls == ["cache", "store", "util"]
    assert phases == ["cache", "database_and_indexes", "total"]


@pytest.mark.parametrize("missing_key", ["COYOTE3_DB", "IDENTITY_DB", "KNOWLEDGEBASE_DB", "BAM_DB"])
def test_create_runtime_context_requires_explicit_database_names(
    monkeypatch: pytest.MonkeyPatch, missing_key: str
) -> None:
    config_values = {
        "ENV_NAME": "testing",
        "COYOTE3_DB": "coyote3_test",
        "IDENTITY_DB": "identity_test",
        "KNOWLEDGEBASE_DB": "knowledgebase_test",
        "BAM_DB": "bam_test",
    }
    config_values[missing_key] = ""
    monkeypatch.setattr(
        runtime_setup,
        "_select_config",
        lambda **_kwargs: SimpleNamespace(**config_values),
    )

    with pytest.raises(RuntimeError, match=missing_key):
        runtime_setup.create_runtime_context(testing=True)


def test_create_runtime_context_requires_separate_knowledgebase_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runtime_setup,
        "_select_config",
        lambda **_kwargs: SimpleNamespace(
            ENV_NAME="testing",
            COYOTE3_DB="same_database",
            IDENTITY_DB="identity_test",
            KNOWLEDGEBASE_DB="same_database",
            BAM_DB="bam_test",
        ),
    )

    with pytest.raises(RuntimeError, match="must be different"):
        runtime_setup.create_runtime_context(testing=True)


def test_create_runtime_context_requires_separate_identity_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runtime_setup,
        "_select_config",
        lambda **_kwargs: SimpleNamespace(
            ENV_NAME="testing",
            COYOTE3_DB="application",
            IDENTITY_DB="application",
            KNOWLEDGEBASE_DB="knowledgebase",
            BAM_DB="bam",
        ),
    )

    with pytest.raises(RuntimeError, match="IDENTITY_DB must be different"):
        runtime_setup.create_runtime_context(testing=True)


def test_mongo_adapter_binds_knowledgebase_collections_to_dedicated_database() -> None:
    class FakeDatabase:
        def __init__(self, name: str) -> None:
            self.name = name

        def __getitem__(self, collection: str) -> tuple[str, str]:
            return self.name, collection

    adapter = runtime_adapter.MongoAdapter.__new__(runtime_adapter.MongoAdapter)
    adapter.app = SimpleNamespace(
        config={
            "COYOTE3_DB": "application",
            "IDENTITY_DB": "identity",
            "KNOWLEDGEBASE_DB": "knowledgebase",
            "BAM_DB": "bam",
            "DB_COLLECTIONS_CONFIG": {
                "application": {"samples_collection": "samples"},
                "identity": {"users_collection": "users"},
                "knowledgebase": {"civic_variants_collection": "civic_variants"},
                "bam": {"bam_samples": "samples"},
            },
        }
    )
    adapter.coyote_db = FakeDatabase("application")
    adapter.identity_db = FakeDatabase("identity")
    adapter.knowledgebase_db = FakeDatabase("knowledgebase")
    adapter.bam_db = FakeDatabase("bam")

    adapter.setup()

    assert adapter.samples_collection == ("application", "samples")
    assert adapter.users_collection == ("identity", "users")
    assert adapter.civic_variants_collection == ("knowledgebase", "civic_variants")
    assert adapter.bam_samples == ("bam", "samples")


def test_index_conflict_is_recorded_without_stopping_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = runtime_adapter.MongoAdapter.__new__(runtime_adapter.MongoAdapter)
    adapter.app = SimpleNamespace(logger=logging.getLogger("adapter-test"))
    adapter.index_setup_conflicts = []
    observations: list[tuple[str, str]] = []
    repository = SimpleNamespace(
        ensure_indexes=lambda: (_ for _ in ()).throw(
            OperationFailure("existing index differs", code=85)
        )
    )
    monkeypatch.setattr(
        runtime_adapter,
        "observe_operation",
        lambda *, operation, outcome, duration_ms: observations.append((operation, outcome)),
    )

    adapter._ensure_repository_indexes("variants", repository)

    assert adapter.index_setup_conflicts[0]["repository"] == "variants"
    assert observations == [("mongo_index_reconcile.variants", "conflict")]


def test_non_index_operation_failure_is_propagated(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = runtime_adapter.MongoAdapter.__new__(runtime_adapter.MongoAdapter)
    adapter.app = SimpleNamespace(logger=logging.getLogger("adapter-test"))
    adapter.index_setup_conflicts = []
    observations: list[tuple[str, str]] = []
    repository = SimpleNamespace(
        ensure_indexes=lambda: (_ for _ in ()).throw(OperationFailure("unauthorized", code=13))
    )
    monkeypatch.setattr(
        runtime_adapter,
        "observe_operation",
        lambda *, operation, outcome, duration_ms: observations.append((operation, outcome)),
    )

    with pytest.raises(OperationFailure, match="unauthorized"):
        adapter._ensure_repository_indexes("variants", repository)

    assert observations == [("mongo_index_reconcile.variants", "failure")]


def test_successful_index_setup_is_observed(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = runtime_adapter.MongoAdapter.__new__(runtime_adapter.MongoAdapter)
    adapter.app = SimpleNamespace(logger=logging.getLogger("adapter-test"))
    adapter.index_setup_conflicts = []
    observations: list[tuple[str, str]] = []
    monkeypatch.setattr(
        runtime_adapter,
        "observe_operation",
        lambda *, operation, outcome, duration_ms: observations.append((operation, outcome)),
    )

    adapter._ensure_repository_indexes("samples", SimpleNamespace(ensure_indexes=lambda: None))

    assert observations == [("mongo_index_reconcile.samples", "success")]


def test_runtime_index_verification_records_findings_without_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from api.infra.mongo import index_management

    adapter = runtime_adapter.MongoAdapter.__new__(runtime_adapter.MongoAdapter)
    adapter.app = SimpleNamespace(logger=logging.getLogger("adapter-test"))
    adapter.index_setup_conflicts = []
    finding = {
        "repository": "samples",
        "collection": "samples",
        "name": "sample_id_1",
        "state": "missing",
    }
    monkeypatch.setattr(index_management, "build_index_plan", lambda _adapter: [finding])

    adapter.verify_index_contracts()

    assert adapter.index_setup_conflicts == [finding]
