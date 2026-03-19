"""Security-sensitive API settings behavior tests."""

from __future__ import annotations

import pytest

from api import settings


def test_configure_process_env_is_noop(monkeypatch: pytest.MonkeyPatch):
    """Test configure process env is noop.

    Args:
        monkeypatch (pytest.MonkeyPatch): Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setenv("TESTING", "1")

    settings.configure_process_env()


def test_production_requires_explicit_secret_key():
    """Test production requires explicit secret key.

    Returns:
        The function result.
    """
    with pytest.MonkeyPatch.context() as mp:
        mp.delenv("TESTING", raising=False)
        mp.delenv("DEVELOPMENT", raising=False)
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            settings.get_api_secret_key({})


def test_production_requires_explicit_internal_api_token():
    """Test production requires explicit internal api token.

    Returns:
        The function result.
    """
    with pytest.MonkeyPatch.context() as mp:
        mp.delenv("TESTING", raising=False)
        mp.delenv("DEVELOPMENT", raising=False)
        with pytest.raises(RuntimeError, match="INTERNAL_API_TOKEN"):
            settings.get_internal_api_token({"SECRET_KEY": "x"})


def test_production_requires_explicit_session_salt():
    """Test production requires explicit session salt.

    Returns:
        The function result.
    """
    with pytest.MonkeyPatch.context() as mp:
        mp.delenv("TESTING", raising=False)
        mp.delenv("DEVELOPMENT", raising=False)
        with pytest.raises(RuntimeError, match="API_SESSION_SALT"):
            settings.get_api_session_salt({"SECRET_KEY": "x", "INTERNAL_API_TOKEN": "y"})


def test_non_production_allows_dev_fallbacks():
    """Test non production allows dev fallbacks.

    Returns:
        The function result.
    """
    config = {"TESTING": True}

    assert settings.get_api_secret_key(config) == "coyote3-api-dev-only"
    assert settings.get_internal_api_token(config) == ""
    assert settings.get_api_session_salt(config) == "coyote3-api-session-v1-dev-only"
    assert settings.get_api_session_cookie_secure(config) is False


def test_production_session_cookie_secure_defaults_true():
    """Test production session cookie secure defaults true.

    Returns:
        The function result.
    """
    with pytest.MonkeyPatch.context() as mp:
        mp.delenv("TESTING", raising=False)
        mp.delenv("DEVELOPMENT", raising=False)
        assert settings.get_api_session_cookie_secure({}) is True


def test_production_rejects_placeholder_secret_and_token_and_salt():
    """Production mode rejects known CI/dev placeholder values."""
    with pytest.MonkeyPatch.context() as mp:
        mp.delenv("TESTING", raising=False)
        mp.delenv("DEVELOPMENT", raising=False)
        with pytest.raises(RuntimeError, match="Insecure production setting for SECRET_KEY"):
            settings.get_api_secret_key({"SECRET_KEY": "ci-test-secret-key"})

        with pytest.raises(
            RuntimeError, match="Insecure production setting for INTERNAL_API_TOKEN"
        ):
            settings.get_internal_api_token({"INTERNAL_API_TOKEN": "ci-test-internal-token"})

        with pytest.raises(RuntimeError, match="Insecure production setting for API_SESSION_SALT"):
            settings.get_api_session_salt({"API_SESSION_SALT": "coyote3-api-session-v1-dev-only"})
