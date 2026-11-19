"""Standalone Relay settings use explicit destinations and do not expose credentials."""

from unittest.mock import Mock

import pytest

from coyote_relay import login, submit
from coyote_relay.config import ApiConnection, configured_value, read_token


def test_connection_cli_overrides_environment_and_preserves_mount_prefix():
    environment = {
        "COYOTE_RELAY_API_URL": "https://environment.invalid/base/",
        "COYOTE_RELAY_CA_BUNDLE": "/environment-ca.pem",
    }
    inherited = ApiConnection.resolve(environment=environment)
    assert inherited.base_url == "https://environment.invalid/base"
    assert inherited.ca_bundle == "/environment-ca.pem"
    overridden = ApiConnection.resolve(
        base_url="https://explicit.invalid/prefix/",
        ca_bundle="/explicit-ca.pem",
        environment=environment,
    )
    assert overridden.base_url == "https://explicit.invalid/prefix"
    assert overridden.ca_bundle == "/explicit-ca.pem"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not-a-url",
        "file:///private/input",
        "https://operator:synthetic-secret@example.invalid",
        "https://example.invalid?secret=synthetic-secret",
        "https://example.invalid#synthetic-secret",
        "https://example.invalid:invalid",
        "https://example.invalid/\nprivate",
        "https://example.invalid/path with spaces",
    ],
)
def test_invalid_api_url_never_echoes_the_supplied_value(value):
    with pytest.raises(ValueError) as failure:
        ApiConnection.resolve(base_url=value, environment={})
    assert "COYOTE_RELAY_API_URL" in str(failure.value)
    assert "synthetic-secret" not in str(failure.value)
    assert "private/input" not in str(failure.value)


def test_missing_destination_does_not_use_application_environment_aliases():
    with pytest.raises(ValueError):
        ApiConnection.resolve(environment={"COYOTE4_BASE_URL": "https://unexpected.invalid"})


def test_explicit_empty_value_does_not_reuse_environment_credentials():
    assert configured_value("password", "", environment={"COYOTE_RELAY_PASSWORD": "secret"}) == ""
    with pytest.raises(ValueError):
        read_token(token="", environment={"COYOTE_RELAY_TOKEN": "secret"})


def test_token_sources_respect_explicit_selection_and_never_read_host_defaults(tmp_path):
    environment = {
        "COYOTE_RELAY_TOKEN": "relay-token",
        "OPERATOR_TOKEN": "selected-token",
        "INTERNAL_API_TOKEN": "host-token",
    }
    assert read_token(environment=environment) == "relay-token"
    assert read_token(token="argument-token", environment=environment) == "argument-token"
    assert read_token(token_env="OPERATOR_TOKEN", environment=environment) == "selected-token"
    token_file = tmp_path / "token.txt"
    token_file.write_text("file-token\n")
    assert read_token(token_file=str(token_file), environment=environment) == "file-token"
    with pytest.raises(ValueError):
        read_token(token_env="ABSENT_TOKEN", environment=environment)
    with pytest.raises(ValueError):
        read_token(environment={"INTERNAL_API_TOKEN": "host-token"})
    with pytest.raises(ValueError, match="Choose only one"):
        read_token(token="explicit", token_env="OPERATOR_TOKEN", environment=environment)


@pytest.mark.parametrize(
    "token",
    [
        "",
        "embedded\rnewline",
        "embedded\nnewline",
        'unsafe"quote',
        "embedded\x00value",
        "embedded\u200bvalue",
        "x" * 16385,
    ],
)
def test_token_validation_does_not_echo_invalid_secrets(token):
    with pytest.raises(ValueError) as failure:
        read_token(token=token, environment={})
    if token:
        assert token not in str(failure.value)


@pytest.mark.parametrize("explicit", [False, True])
def test_submission_resolves_connection_and_auth_before_delegating(monkeypatch, explicit):
    monkeypatch.setenv("COYOTE_RELAY_API_URL", "https://environment.invalid/prefix/")
    monkeypatch.setenv("COYOTE_RELAY_AUTH", "bearer")
    monkeypatch.setenv("COYOTE_RELAY_CA_BUNDLE", "/environment.pem")
    delegate = Mock(return_value=0)
    monkeypatch.setattr(submit, "submit", delegate)
    options = ["synthetic.yaml"]
    if explicit:
        options.extend(
            [
                "--base-url",
                "https://explicit.invalid/mount/",
                "--auth",
                "ingest",
                "--ca-bundle",
                "/explicit.pem",
            ]
        )
    assert submit.main(options) == 0
    args = delegate.call_args.args[0]
    assert args.base_url == (
        "https://explicit.invalid/mount" if explicit else "https://environment.invalid/prefix"
    )
    assert args.auth == ("ingest" if explicit else "bearer")
    assert args.ca_bundle == ("/explicit.pem" if explicit else "/environment.pem")


@pytest.mark.parametrize(
    "command,options", [(login, ["--mode", "token"]), (submit, ["synthetic.yaml"])]
)
def test_cli_rejects_missing_api_url_without_attempting_a_connection(
    monkeypatch, capsys, command, options
):
    monkeypatch.delenv("COYOTE_RELAY_API_URL", raising=False)
    monkeypatch.setenv("COYOTE4_BASE_URL", "https://not-selected.invalid")
    with pytest.raises(SystemExit) as failure:
        command.main(options)
    assert failure.value.code == 2
    assert "COYOTE_RELAY_API_URL" in capsys.readouterr().err


def test_explicit_token_variable_is_forwarded_to_submission(monkeypatch):
    monkeypatch.setenv("COYOTE_RELAY_API_URL", "https://synthetic.invalid")
    monkeypatch.setenv("COYOTE_RELAY_TOKEN", "unselected")
    monkeypatch.setenv("PIPELINE_CREDENTIAL", "selected")

    def delegate(args):
        assert submit.load_token(args) == "selected"
        return 0

    monkeypatch.setattr(submit, "submit", delegate)
    assert submit.main(["synthetic.yaml", "--token-env", "PIPELINE_CREDENTIAL"]) == 0
