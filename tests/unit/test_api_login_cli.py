"""Login CLI delegates to the validated HTTP client and hides credentials by default."""

import json

import httpx
import pytest

from scripts.ingest.api_login import main


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
            headers={"set-cookie": "coyote3_api_session=synthetic-token; HttpOnly; Secure"},
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
