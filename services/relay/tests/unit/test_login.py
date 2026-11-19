"""Login CLI delegates to the validated HTTP client and hides credentials by default."""

import json

import httpx
import pytest

from coyote_relay import login
from coyote_relay.login import main


@pytest.mark.parametrize("print_token", [False, True])
@pytest.mark.parametrize("mode", ["password", "token"])
@pytest.mark.parametrize("password_env", [False, True])
def test_cli_uses_validated_sessions_and_exports_only_when_requested(
    monkeypatch, capsys, print_token, mode, password_env
):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={"user": {"username": "synthetic"}},
            headers={"set-cookie": "coyote4_api_session=synthetic-token; HttpOnly; Secure"},
        )

    original_client = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(**{**kwargs, "transport": httpx.MockTransport(respond)}),
    )
    credentials = (
        ["--username", "synthetic", "--password", "synthetic-password", "--provider", "local"]
        if mode == "password"
        else ["--token", "synthetic-token"]
    )
    if mode == "password" and password_env:
        monkeypatch.setenv("SYNTHETIC_LOGIN_PASSWORD", "synthetic-password")
        credentials = [
            "--username",
            "synthetic",
            "--password-env",
            "SYNTHETIC_LOGIN_PASSWORD",
            "--provider",
            "local",
        ]
    args = ["--base-url", "https://synthetic.invalid/prefix", "--mode", mode, *credentials]
    assert main(args + (["--print-token"] if print_token else [])) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["user"] == {"username": "synthetic"}
    assert ("session_token" in payload) == print_token
    if print_token:
        assert payload["session_token"] == "synthetic-token"
    assert len(calls) == 1
    assert calls[0].url.path == (
        "/prefix/api/v1/auth/sessions" if mode == "password" else "/prefix/api/v1/auth/session"
    )
    if mode == "token":
        assert calls[0].headers["Authorization"] == "Bearer synthetic-token"


@pytest.mark.parametrize("explicit", [False, True])
def test_login_reads_relay_environment_with_explicit_credentials_taking_precedence(
    monkeypatch, capsys, explicit
):
    calls = []
    environment = {
        "COYOTE_RELAY_API_URL": "https://environment.invalid/prefix/",
        "COYOTE_RELAY_USERNAME": "environment-user",
        "COYOTE_RELAY_PASSWORD": "environment-password",
        "COYOTE_RELAY_PROVIDER": "ldap",
    }
    for key, value in environment.items():
        monkeypatch.setenv(key, value)

    def respond(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={"user": {"username": "synthetic"}},
            headers={"set-cookie": "coyote4_api_session=synthetic-token; HttpOnly; Secure"},
        )

    original_client = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(**{**kwargs, "transport": httpx.MockTransport(respond)}),
    )
    options = ["--mode", "password"]
    if explicit:
        options.extend(
            [
                "--base-url",
                "https://explicit.invalid/mount",
                "--username",
                "explicit-user",
                "--password",
                "explicit-password",
                "--provider",
                "local",
            ]
        )
    assert main(options) == 0
    assert len(calls) == 1
    body = json.loads(calls[0].content)
    assert body["username"] == ("explicit-user" if explicit else "environment-user")
    assert body["password"] == ("explicit-password" if explicit else "environment-password")
    assert body["provider"] == ("local" if explicit else "ldap")
    assert calls[0].url.path == (
        "/mount/api/v1/auth/sessions" if explicit else "/prefix/api/v1/auth/sessions"
    )
    output = capsys.readouterr().out
    assert "environment-password" not in output
    assert "explicit-password" not in output
    assert "synthetic-token" not in output


def test_login_uses_selected_ca_bundle_with_tls_verification(monkeypatch, capsys):
    monkeypatch.setenv("COYOTE_RELAY_API_URL", "https://synthetic.invalid")
    monkeypatch.setenv("COYOTE_RELAY_TOKEN", "synthetic-token")
    monkeypatch.setenv("COYOTE_RELAY_CA_BUNDLE", "/selected/ca.pem")
    context, transport = object(), object()
    calls = []

    def create_context(*, cafile):
        assert cafile == "/selected/ca.pem"
        return context

    def create_transport(*, verify):
        assert verify is context
        return transport

    class Client:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, url, *, headers):
            assert url == "https://synthetic.invalid/api/v1/auth/session"
            assert headers == {"Authorization": "Bearer synthetic-token"}
            return httpx.Response(
                200, json={"user": {"username": "synthetic"}}, request=httpx.Request("GET", url)
            )

    monkeypatch.setattr(login.ssl, "create_default_context", create_context)
    monkeypatch.setattr(login.httpx, "HTTPTransport", create_transport)
    monkeypatch.setattr(login.httpx, "Client", Client)
    assert main(["--mode", "token"]) == 0
    assert calls == [{"transport": transport, "timeout": 30.0, "follow_redirects": False}]
    assert "synthetic-token" not in capsys.readouterr().out


def test_selected_missing_password_variable_does_not_fall_back(monkeypatch, capsys):
    monkeypatch.setenv("COYOTE_RELAY_API_URL", "https://synthetic.invalid")
    monkeypatch.setenv("COYOTE_RELAY_USERNAME", "synthetic")
    monkeypatch.setenv("COYOTE_RELAY_PASSWORD", "must-not-be-used")
    monkeypatch.setenv("COYOTE_RELAY_PROVIDER", "local")
    monkeypatch.delenv("MISSING_PASSWORD", raising=False)
    with pytest.raises(SystemExit) as failure:
        main(["--mode", "password", "--password-env", "MISSING_PASSWORD"])
    assert failure.value.code == 2
    assert "must-not-be-used" not in capsys.readouterr().err
