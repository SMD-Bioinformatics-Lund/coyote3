"""Security-sensitive API settings behavior tests."""

from __future__ import annotations

import pytest

from api.config import runtime


def test_configure_process_env_is_noop(monkeypatch: pytest.MonkeyPatch):
    """Test configure process env is noop.

    Args:
        monkeypatch (pytest.MonkeyPatch): Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setenv("ENV_NAME", "testing")

    runtime.configure_process_env()


def test_production_requires_explicit_secret_key():
    """Test production requires explicit secret key.

    Returns:
        The function result.
    """
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("ENV_NAME", "production")
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            runtime.get_api_secret_key({})


def test_production_requires_explicit_internal_api_token():
    """Test production requires explicit internal api token.

    Returns:
        The function result.
    """
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("ENV_NAME", "production")
        with pytest.raises(RuntimeError, match="INTERNAL_API_TOKEN"):
            runtime.get_internal_api_token({"SECRET_KEY": "x"})


def test_non_production_allows_dev_fallbacks():
    """Test non production allows dev fallbacks.

    Returns:
        The function result.
    """
    config = {"ENV_NAME": "testing"}

    assert runtime.get_api_secret_key(config) == "coyote3-api-dev-only"
    assert runtime.get_internal_api_token(config) == ""
    assert runtime.get_api_session_cookie_secure(config) is False


def test_production_session_cookie_secure_defaults_true():
    """Test production session cookie secure defaults true.

    Returns:
        The function result.
    """
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("ENV_NAME", "production")
        assert runtime.get_api_session_cookie_secure({}) is True


def test_session_cookie_secure_follows_browser_facing_scheme():
    """HTTPS uses a secure cookie while explicit local HTTP can proceed."""
    assert runtime.get_api_session_cookie_secure({}, request_scheme="https") is True
    assert runtime.get_api_session_cookie_secure({}, request_scheme="http") is False


def test_production_rejects_placeholder_secret_and_token():
    """Production mode rejects known CI/dev placeholder values."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("ENV_NAME", "production")
        with pytest.raises(RuntimeError, match="Insecure production setting for SECRET_KEY"):
            runtime.get_api_secret_key({"SECRET_KEY": "ci-test-secret-key"})

        with pytest.raises(
            RuntimeError, match="Insecure production setting for INTERNAL_API_TOKEN"
        ):
            runtime.get_internal_api_token({"INTERNAL_API_TOKEN": "ci-test-internal-token"})
