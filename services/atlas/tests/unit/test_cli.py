"""Offline commands and explicit API submission preserve reviewed identity and credentials."""

from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from coyote_atlas import cli
from coyote_atlas.bundle import ReferenceBundle


@pytest.fixture
def plan(monkeypatch):
    result = SimpleNamespace(model_dump=lambda **kwargs: {"manifest_sha256": "a" * 64})
    monkeypatch.setattr(ReferenceBundle, "plan", lambda self: result)
    return result


@pytest.mark.parametrize("command", ["validate", "plan"])
def test_offline_commands_never_require_connection_settings(plan, command, capsys):
    assert cli.main([command]) == 0
    assert '"manifest_sha256"' in capsys.readouterr().out


def test_install_requires_reviewed_hash_and_explicit_api_configuration(plan, monkeypatch, capsys):
    monkeypatch.delenv("COYOTE_ATLAS_API_URL", raising=False)
    client = Mock()
    monkeypatch.setattr(cli, "CoyoteClient", client)
    assert cli.main(["install", "--expected-manifest-sha256", "a" * 64]) == 1
    client.assert_not_called()
    assert "Reference operation failed" in capsys.readouterr().err


@pytest.mark.parametrize(
    "url",
    [
        "",
        "ftp://example.test",
        "https://user:private@example.test",
        "https://example.test/?token=private",
        "https://example.test/#private",
        "https://example.test/\nprivate",
    ],
)
def test_invalid_urls_do_not_expose_secrets_or_start_requests(plan, monkeypatch, capsys, url):
    client = Mock()
    monkeypatch.setattr(cli, "CoyoteClient", client)
    assert cli.main(["install", "--api-url", url, "--expected-manifest-sha256", "a" * 64]) == 1
    client.assert_not_called()
    assert "private" not in capsys.readouterr().err


@pytest.mark.parametrize("token", ["", "private\nsecond", "private\x00", "privateä", "x" * 16385])
def test_invalid_tokens_never_reach_client(plan, monkeypatch, token, capsys):
    monkeypatch.setattr(
        cli.os,
        "getenv",
        lambda name, default=None: token if name == "COYOTE_ATLAS_TOKEN" else default,
    )
    client = Mock()
    monkeypatch.setattr(cli, "CoyoteClient", client)
    assert (
        cli.main(
            ["install", "--api-url", "https://example.test", "--expected-manifest-sha256", "a" * 64]
        )
        == 1
    )
    client.assert_not_called()
    assert "private" not in capsys.readouterr().err


def test_cli_values_override_environment_and_send_only_explicit_plan(plan, monkeypatch, capsys):
    monkeypatch.setenv("COYOTE_ATLAS_API_URL", "https://unused.test")
    monkeypatch.setenv("COYOTE_ATLAS_TOKEN", "unused-token")
    monkeypatch.setenv("OPERATOR_TOKEN", "synthetic-private-token")
    client = Mock()
    client.api.admin.references.apply.post.return_value = {"collections": {"hgnc_genes": "skipped"}}
    factory = Mock()
    factory.return_value.__enter__ = Mock(return_value=client)
    factory.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(cli, "CoyoteClient", factory)
    assert (
        cli.main(
            [
                "install",
                "--api-url",
                "https://example.test/prefix",
                "--token-env",
                "OPERATOR_TOKEN",
                "--expected-manifest-sha256",
                "a" * 64,
                "--force",
            ]
        )
        == 0
    )
    factory.assert_called_once_with("https://example.test/prefix", timeout=600.0, transport=None)
    client.login_with_token.assert_called_once_with("synthetic-private-token")
    client.api.admin.references.apply.post.assert_called_once_with(
        json={"expected_manifest_sha256": "a" * 64, "force": True}
    )
    assert "synthetic-private-token" not in capsys.readouterr().out


def test_env_connection_uses_verified_custom_ca(plan, monkeypatch):
    monkeypatch.setenv("COYOTE_ATLAS_API_URL", "https://example.test")
    monkeypatch.setenv("COYOTE_ATLAS_TOKEN", "synthetic-token")
    monkeypatch.setenv("COYOTE_ATLAS_CA_BUNDLE", "trusted.pem")
    context = object()
    create_context = Mock(return_value=context)
    transport = Mock()
    monkeypatch.setattr(cli.ssl, "create_default_context", create_context)
    monkeypatch.setattr(cli.httpx, "HTTPTransport", transport)
    client = Mock()
    client.return_value.__enter__ = Mock(side_effect=httpx.ConnectError("private URL or token"))
    client.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(cli, "CoyoteClient", client)
    assert cli.main(["install", "--expected-manifest-sha256", "a" * 64]) == 1
    create_context.assert_called_once_with(cafile="trusted.pem")
    transport.assert_called_once_with(verify=context)


def test_local_plan_change_never_submits(plan, monkeypatch):
    monkeypatch.setenv("COYOTE_ATLAS_API_URL", "https://example.test")
    client = Mock()
    monkeypatch.setattr(cli, "CoyoteClient", client)
    assert cli.main(["install", "--expected-manifest-sha256", "b" * 64]) == 1
    client.assert_not_called()


def test_explicit_local_bundle_is_used(tmp_path, capsys):
    assert cli.main(["--bundle", str(tmp_path), "inspect"]) == 1
    assert str(tmp_path) not in capsys.readouterr().err
