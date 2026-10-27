"""Verify packaged seed loading and API-only deployment data maintenance."""

import json
import subprocess
from unittest.mock import Mock

import httpx
import pytest

from api.infra.seed.bundle import load_reference_seed_pack
from scripts.bootstrap.bootstrap_database import (
    DEFAULT_RBAC_DIR,
    DEFAULT_REFERENCE_DIR,
    build_seed_documents,
)
from scripts.deployment import manage_data


def test_application_seed_loading_does_not_read_reference_snapshots(tmp_path):
    """Malformed large reference files must not affect application-only bootstrap."""
    (tmp_path / "hgnc_genes.seed.ndjson").write_text("not json")
    (tmp_path / "vep_metadata.seed.ndjson").write_text("not json")
    (tmp_path / "assay_groups.seed.ndjson").write_text('{"group_id":"synthetic"}\n')
    assert load_reference_seed_pack(tmp_path, include_knowledgebase=False) == {
        "assay_groups": [{"group_id": "synthetic"}]
    }
    seed = build_seed_documents(
        rbac_dir=DEFAULT_RBAC_DIR,
        reference_dir=DEFAULT_REFERENCE_DIR,
        actor="synthetic.admin",
        include_knowledgebase=False,
    )
    assert {"roles", "permissions", "assay_groups", "query_rule_sets"} <= seed.keys()
    assert not {"hgnc_genes", "vep_metadata", "vep_diagrams"} & seed.keys()


@pytest.fixture
def api_transport(monkeypatch):
    """Mock HTTP only, keeping the real shared API login and session handling."""
    requests = []
    responses = {
        "login_status": 200,
        "install_status": 200,
        "change_status": 200,
        "temporary": False,
    }
    login_count = 0

    def handle(request):
        nonlocal login_count
        requests.append(request)
        if request.url.path.endswith("/auth/sessions"):
            login_count += 1
            return httpx.Response(
                responses["login_status"],
                json={
                    "user": {
                        "username": "admin",
                        "must_change_password": responses["temporary"] and login_count == 1,
                    }
                },
                headers={"set-cookie": f"coyote3_api_session=synthetic-{login_count}; Path=/"},
            )
        if request.url.path.endswith("/auth/password/change"):
            return httpx.Response(responses["change_status"], json={"status": "ok"})
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(
            responses["install_status"], json={"collections": {"hgnc_genes": "loaded"}}
        )

    client = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: client(**{**kwargs, "transport": httpx.MockTransport(handle)}),
    )
    monkeypatch.setattr(manage_data.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", Mock(return_value="admin"))
    monkeypatch.setattr(manage_data.getpass, "getpass", Mock(return_value="synthetic-password"))
    return requests, responses


def test_client_uses_existing_login_and_revokes_its_session(api_transport):
    requests, _ = api_transport
    assert manage_data.manage_data(
        api_url="https://synthetic.invalid/coyote3/", modules=["knowledgebase"], force=True
    ) == {"hgnc_genes": "loaded"}
    assert [request.method for request in requests] == ["POST", "POST", "DELETE"]
    assert requests[0].url.path == "/coyote3/api/v1/auth/sessions"
    assert json.loads(requests[0].content) == {
        "username": "admin",
        "password": "synthetic-password",
        "provider": "local",
    }
    assert json.loads(requests[1].content) == {"modules": ["knowledgebase"], "force": True}
    assert requests[1].headers["Authorization"] == "Bearer synthetic-1"
    assert requests[2].url.path.endswith("/auth/sessions/current")


@pytest.mark.parametrize("provider", ["local", "ldap"])
def test_maintenance_provider_is_explicit_even_for_email_logins(api_transport, provider):
    """A local account named with an email must not be redirected to LDAP."""
    requests, _ = api_transport
    manage_data.manage_data(
        api_url="https://synthetic.invalid",
        modules=["application"],
        username="synthetic@example.invalid",
        provider=provider,
    )
    assert json.loads(requests[0].content)["provider"] == provider


def test_temporary_password_is_changed_and_reauthenticated_before_data(api_transport, monkeypatch):
    requests, responses = api_transport
    responses["temporary"] = True
    monkeypatch.setattr(
        manage_data.getpass,
        "getpass",
        Mock(side_effect=["temporary-example", "PermanentExample!123", "PermanentExample!123"]),
    )
    manage_data.manage_data(api_url="https://synthetic.invalid", modules=["demo"], force=True)
    assert [request.url.path for request in requests] == [
        "/api/v1/auth/sessions",
        "/api/v1/auth/password/change",
        "/api/v1/auth/sessions",
        "/api/v1/admin/installation/data",
        "/api/v1/auth/sessions/current",
    ]
    assert json.loads(requests[1].content) == {
        "current_password": "temporary-example",
        "new_password": "PermanentExample!123",
        "confirm_password": "PermanentExample!123",
    }
    assert json.loads(requests[2].content)["password"] == "PermanentExample!123"
    assert requests[3].headers["Authorization"] == "Bearer synthetic-2"
    assert requests[4].headers["Authorization"] == "Bearer synthetic-2"


@pytest.mark.parametrize("status", [401, 403])
def test_rejected_login_cannot_submit_data(api_transport, status):
    requests, responses = api_transport
    responses["login_status"] = status
    with pytest.raises(httpx.HTTPStatusError):
        manage_data.manage_data(api_url="https://synthetic.invalid", modules=["application"])
    assert len(requests) == 1


def test_denied_ordinary_user_cannot_bypass_api_and_session_is_revoked(api_transport):
    requests, responses = api_transport
    responses["install_status"] = 403
    with pytest.raises(httpx.HTTPStatusError):
        manage_data.manage_data(
            api_url="https://synthetic.invalid", modules=["application"], force=True
        )
    assert requests[-1].method == "DELETE"


def test_failed_password_change_cannot_submit_data(api_transport, monkeypatch):
    requests, responses = api_transport
    responses.update(temporary=True, change_status=400)
    monkeypatch.setattr(manage_data.getpass, "getpass", Mock(side_effect=["old", "new", "new"]))
    with pytest.raises(httpx.HTTPStatusError):
        manage_data.manage_data(api_url="https://synthetic.invalid", modules=["application"])
    assert not any("installation/data" in request.url.path for request in requests)
    assert requests[-1].method == "DELETE"


def test_password_confirmation_mismatch_keeps_data_untouched(api_transport, monkeypatch):
    requests, responses = api_transport
    responses["temporary"] = True
    monkeypatch.setattr(
        manage_data.getpass, "getpass", Mock(side_effect=["old", "first", "second"])
    )
    with pytest.raises(ValueError, match="confirmation"):
        manage_data.manage_data(api_url="https://synthetic.invalid", modules=["demo"])
    assert len(requests) == 2
    assert requests[-1].method == "DELETE"


def test_missing_terminal_cannot_bypass_authentication(api_transport, monkeypatch):
    requests, _ = api_transport
    monkeypatch.setattr(manage_data.sys.stdin, "isatty", lambda: False)
    with pytest.raises(PermissionError, match="Run interactively"):
        manage_data.manage_data(api_url="https://synthetic.invalid", modules=["application"])
    assert not requests


def test_force_requires_explicit_modules():
    result = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/deployment/manage_data.py",
            "--api-url",
            "https://synthetic.invalid",
            "--force",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "--modules" in result.stderr
