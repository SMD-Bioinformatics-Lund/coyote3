"""Demo profiles keep production protections and use explicitly isolated native storage."""

import json
import os
import subprocess
import sys

import pytest
from coyote_api.config.security import (
    get_api_secret_key,
    get_api_session_cookie_secure,
    get_internal_api_token,
    get_runtime_mode_flags,
)


@pytest.mark.parametrize(
    "environment,expected",
    [
        ("testing", {"testing": True, "development": False}),
        ("development", {"testing": False, "development": True}),
        ("production", {"testing": False, "development": False}),
        ("staging", {"testing": False, "development": False}),
    ],
)
def test_unmodified_environment_mode_selection_is_preserved(monkeypatch, environment, expected):
    monkeypatch.delenv("COYOTE4_RUNTIME_MODE", raising=False)
    monkeypatch.setenv("ENV_NAME", environment)
    assert get_runtime_mode_flags() == expected


@pytest.mark.parametrize("environment", ["testing", "development", "production"])
def test_production_runtime_override_never_enables_test_or_development_paths(
    monkeypatch, environment
):
    monkeypatch.setenv("ENV_NAME", environment)
    monkeypatch.setenv("COYOTE4_RUNTIME_MODE", "production")
    assert get_runtime_mode_flags() == {"testing": False, "development": False}


@pytest.mark.parametrize("mode", ["", "invalid", "test", "prod"])
def test_unrecognized_explicit_runtime_mode_fails_closed(monkeypatch, mode):
    monkeypatch.setenv("COYOTE4_RUNTIME_MODE", mode)
    with pytest.raises(RuntimeError, match="COYOTE4_RUNTIME_MODE"):
        get_runtime_mode_flags()


@pytest.mark.parametrize("reader", [get_api_secret_key, get_internal_api_token])
def test_production_override_requires_explicit_secrets_for_testing_profiles(monkeypatch, reader):
    monkeypatch.setenv("COYOTE4_RUNTIME_MODE", "production")
    with pytest.raises(RuntimeError, match="Missing required API setting"):
        reader({"ENV_NAME": "testing"})


def test_production_override_rejects_test_secrets_and_keeps_local_http_cookie_behavior(monkeypatch):
    monkeypatch.setenv("COYOTE4_RUNTIME_MODE", "production")
    settings = {"ENV_NAME": "testing", "SECRET_KEY": "coyote4-api-dev-only"}
    with pytest.raises(RuntimeError, match="Insecure production setting"):
        get_api_secret_key(settings)
    assert get_api_session_cookie_secure(settings) is True
    assert get_api_session_cookie_secure(settings, request_scheme="http") is False
    assert get_api_session_cookie_secure(settings, request_scheme="https") is True


@pytest.mark.parametrize("override", [False, True])
def test_storage_override_is_resolved_before_paths_without_creating_directories(tmp_path, override):
    environment = {key: os.environ[key] for key in ("PATH", "HOME", "LANG") if key in os.environ}
    environment.update({"ENV_NAME": "testing", "COYOTE4_RUNTIME_ROOT": str(tmp_path / "runtime")})
    if override:
        environment["COYOTE4_DATA_ROOT"] = str(tmp_path / "native-data")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json; from coyote_api.config import paths; print(json.dumps([str(paths.DATA_CONTAINER_ROOT), str(paths.REPORTS_BASE_PATH), str(paths.INGEST_STAGING_DIR)]))",
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    root = str(tmp_path / "native-data") if override else "/data"
    assert json.loads(result.stdout) == [
        root,
        f"{root}/coyote4_test/reports",
        f"{root}/coyote4_test/ingest_staging",
    ]
    assert not (tmp_path / "native-data").exists()


def test_relative_storage_override_fails_before_runtime_initialization(tmp_path):
    environment = {key: os.environ[key] for key in ("PATH", "HOME", "LANG") if key in os.environ}
    environment.update({"COYOTE4_RUNTIME_ROOT": str(tmp_path), "COYOTE4_DATA_ROOT": "relative"})
    result = subprocess.run(
        [sys.executable, "-c", "from coyote_api.config import paths"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "COYOTE4_DATA_ROOT" in result.stderr
