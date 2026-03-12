"""Security-sensitive API settings behavior tests."""

from __future__ import annotations

import os

import pytest

from api import settings


def test_configure_process_env_defaults_external_api_off_in_non_production(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("REQUIRE_EXTERNAL_API", raising=False)
    monkeypatch.setenv("TESTING", "1")

    settings.configure_process_env()

    assert os.environ["REQUIRE_EXTERNAL_API"] == "0"


def test_configure_process_env_defaults_external_api_on_in_production(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("REQUIRE_EXTERNAL_API", raising=False)
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.delenv("DEVELOPMENT", raising=False)

    settings.configure_process_env()

    assert os.environ["REQUIRE_EXTERNAL_API"] == "1"


def test_production_requires_explicit_secret_key():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        settings.get_api_secret_key({})


def test_production_requires_explicit_internal_api_token():
    with pytest.raises(RuntimeError, match="INTERNAL_API_TOKEN"):
        settings.get_internal_api_token({"SECRET_KEY": "x"})


def test_production_requires_explicit_session_salt():
    with pytest.raises(RuntimeError, match="API_SESSION_SALT"):
        settings.get_api_session_salt({"SECRET_KEY": "x", "INTERNAL_API_TOKEN": "y"})


def test_non_production_allows_dev_fallbacks():
    config = {"TESTING": True}

    assert settings.get_api_secret_key(config) == "coyote3-api-dev-only"
    assert settings.get_internal_api_token(config) == ""
    assert settings.get_api_session_salt(config) == "coyote3-api-session-v1-dev-only"
    assert settings.get_api_session_cookie_secure(config) is False


def test_production_session_cookie_secure_defaults_true():
    assert settings.get_api_session_cookie_secure({}) is True
