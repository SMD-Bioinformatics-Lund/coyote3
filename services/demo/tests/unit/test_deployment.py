"""Unsafe target selections fail before demo processes can connect or write."""

import pytest
from coyote_demo.deployment import (
    DEMO_DATABASES,
    DEMO_MONGO_URI_KEYS,
    runtime_validator,
    validate_demo_privileges,
    validate_demo_target,
)
from demo_test_support.deployment import demo_privileges, demo_settings


def test_docker_and_native_demo_targets_are_explicit():
    settings = demo_settings()
    validate_demo_target(settings)
    settings["COYOTE_DEMO_MODE"] = "native"
    settings["COYOTE4_RUNTIME_ROOT"] = "/tmp/synthetic-demo/runtime"
    settings["COYOTE4_DATA_ROOT"] = "/tmp/synthetic-demo/data"
    for key in DEMO_MONGO_URI_KEYS:
        settings[key] = settings[key].replace("demo-mongo:27017", "127.0.0.1:27028")
    for key in ("CACHE_REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"):
        settings[key] = settings[key].replace("demo-redis:6379", "127.0.0.1:16379")
    validate_demo_target(settings)


@pytest.mark.parametrize("key", [*DEMO_DATABASES, *DEMO_MONGO_URI_KEYS])
def test_missing_database_selection_cannot_fall_back_to_another_endpoint(key):
    settings = demo_settings()
    settings.pop(key)
    with pytest.raises(ValueError, match=key):
        validate_demo_target(settings)


@pytest.mark.parametrize("key", list(DEMO_DATABASES))
def test_ordinary_database_names_are_rejected(key):
    settings = demo_settings() | {key: "coyote4_prod"}
    with pytest.raises(ValueError, match=key):
        validate_demo_target(settings)


@pytest.mark.parametrize(
    "uri,database",
    [
        ("mongodb://remote.example:27017", "coyote4_demo"),
        ("mongodb://localhost:27017", "coyote4_smd_prod"),
        ("mongodb://localhost:27017,remote.example:27017", "coyote4_demo"),
    ],
)
def test_installer_rejects_non_demo_targets(uri, database):
    """Ordinary databases and remote hosts fail before any connection is attempted."""
    with pytest.raises(ValueError):
        validate_demo_target(demo_settings() | {"COYOTE4_MONGO_URI": uri, "COYOTE4_DB": database})


@pytest.mark.parametrize(
    "key,value",
    [
        ("COYOTE_DEMO_ENABLED", "0"),
        ("COYOTE_DEMO_MODE", "remote"),
        ("ENV_NAME", "production"),
        ("COYOTE4_RUNTIME_ROOT", "/srv/coyote4"),
        ("COYOTE4_DATA_ROOT", "/srv/coyote4/data"),
        ("COYOTE4_RUNTIME_MODE", "testing"),
        ("TESTING", "1"),
        ("DEVELOPMENT", "1"),
        ("AUTHENTICATION_PROVIDERS", "local,ldap"),
        ("LDAP_HOST", "ldap.example.invalid"),
        ("SMTP_HOST", "smtp.example.invalid"),
        ("GENS_URI", "https://example.invalid"),
        ("IGV_URI", "https://example.invalid"),
        ("ONCOKB_PUBLIC_LOOKUPS_ENABLED", "1"),
        ("CLINPGX_PUBLIC_LOOKUPS_ENABLED", "1"),
        ("PUBLIC_BASE_URL", "http://example.invalid"),
        ("CACHE_REDIS_URL", "redis://default:secret@prod-redis:6379/0"),
        ("CELERY_BROKER_URL", "redis://default:secret@demo-redis:6379/0"),
        ("COYOTE4_MONGO_URI", "mongodb://coyote_demo:secret@prod-mongo:27017/?replicaSet=rs"),
        (
            "COYOTE4_MONGO_URI",
            "mongodb://root:secret@demo-mongo:27017/?authSource=admin&replicaSet=rs",
        ),
        (
            "COYOTE4_MONGO_URI",
            "mongodb://coyote_demo:secret@demo-mongo:27017/coyote4_prod?authSource=admin&replicaSet=rs",
        ),
    ],
)
def test_unsafe_runtime_settings_are_rejected(key, value):
    with pytest.raises(ValueError):
        validate_demo_target(demo_settings() | {key: value})


@pytest.mark.parametrize(
    "uri",
    [
        "mongodb://coyote_demo:SECRET@demo-mongo:bad/",
        "mongodb://[invalid",
        "mongodb://coyote_demo:SECRET@demo-mongo:27017/?SECRET",
        "mongodb://coyote_demo:SECRET@demo-mongo:27017/?authSource=admin&replicaSet=rs&proxyHost=production",
    ],
)
def test_invalid_uri_errors_do_not_expose_credentials(uri):
    with pytest.raises(ValueError) as error:
        validate_demo_target(demo_settings() | {"COYOTE4_MONGO_URI": uri})
    assert "SECRET" not in str(error.value)


def test_expanded_privileges_require_all_demo_databases_and_no_other_authority():
    privileges = demo_privileges()
    validate_demo_privileges(privileges)
    with pytest.raises(ValueError):
        validate_demo_privileges(privileges[:-1])
    for resource in ({"anyResource": True}, {"cluster": True}, {"db": "coyote4", "collection": ""}):
        with pytest.raises(ValueError):
            validate_demo_privileges(privileges + [{"resource": resource, "actions": ["find"]}])


def test_disabled_runtime_performs_no_probe(monkeypatch):
    monkeypatch.setenv("COYOTE_DEMO_ENABLED", "1")
    runtime_validator({"COYOTE_DEMO_ENABLED": "0"})


def test_runtime_rejects_wrong_target_before_host_probe(monkeypatch):
    from coyote_demo import host

    monkeypatch.setattr(host, "validate_runtime_credentials", lambda _: pytest.fail("Unsafe probe"))
    with pytest.raises(ValueError):
        runtime_validator(demo_settings() | {"COYOTE4_DB": "coyote4_prod"})


def test_runtime_probes_validated_settings(monkeypatch):
    from coyote_demo import host

    probed = []
    monkeypatch.setattr(host, "validate_runtime_credentials", probed.append)
    settings = demo_settings()
    runtime_validator(settings)
    assert probed == [settings]
