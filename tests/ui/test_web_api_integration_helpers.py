"""Unit tests for Flask-side API integration helpers."""

from __future__ import annotations

from flask import Flask, g

from coyote.services.api_client import api_client, endpoints


def test_get_web_api_client_uses_configured_base_url():
    app = Flask(__name__)
    app.config["API_BASE_URL"] = "http://api.local:9000"

    with app.app_context():
        client = api_client.get_web_api_client()

    assert client._base_url == "http://api.local:9000"


def test_get_web_api_client_reuses_client_within_request_context():
    app = Flask(__name__)
    app.config["API_BASE_URL"] = "http://api.local:9000"

    with app.test_request_context():
        first = api_client.get_web_api_client()
        second = api_client.get_web_api_client()

    assert first is second


def test_close_web_api_client_removes_request_scoped_client():
    app = Flask(__name__)
    app.config["API_BASE_URL"] = "http://api.local:9000"

    with app.test_request_context():
        client = api_client.get_web_api_client()
        api_client.close_web_api_client()

        assert getattr(g, "_coyote_api_client", None) is None
        assert getattr(client._client, "is_closed", True) is True


def test_build_forward_headers_includes_cookie_if_present():
    headers = api_client.build_forward_headers({"Cookie": "session=abc"})
    assert headers == {
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json",
        "Cookie": "session=abc",
    }


def test_build_forward_headers_includes_request_id_when_present():
    headers = api_client.build_forward_headers({"X-Request-ID": "rid-123"})
    assert headers["X-Request-ID"] == "rid-123"


def test_forward_headers_without_request_context_returns_default_header():
    assert api_client.forward_headers() == {
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json",
    }


def test_forward_headers_with_request_context_includes_cookie():
    app = Flask(__name__)

    with app.test_request_context(headers={"Cookie": "foo=bar"}):
        headers = api_client.forward_headers()

    assert headers["X-Requested-With"] == "XMLHttpRequest"
    assert headers["Accept"] == "application/json"
    assert headers["Cookie"] == "foo=bar"


def test_forward_headers_with_api_session_cookie_adds_bearer_auth():
    app = Flask(__name__)
    app.config["API_SESSION_COOKIE_NAME"] = "coyote3_api_session"

    with app.test_request_context(headers={"Cookie": "coyote3_api_session=token123; foo=bar"}):
        headers = api_client.forward_headers()

    assert headers["Authorization"] == "Bearer token123"


def test_forward_headers_falls_back_to_flask_request_id_context():
    app = Flask(__name__)

    with app.test_request_context(headers={"Cookie": "foo=bar"}):
        g.request_id = "rid-g"
        headers = api_client.forward_headers()

    assert headers["X-Request-ID"] == "rid-g"


def test_build_internal_headers_uses_internal_token_or_secret_key():
    app = Flask(__name__)
    app.config["INTERNAL_API_TOKEN"] = "internal-token"
    app.config["SECRET_KEY"] = "fallback-secret"

    with app.app_context():
        headers = api_client.build_internal_headers()

    assert headers["X-Coyote-Internal-Token"] == "internal-token"
    assert headers["Accept"] == "application/json"


def test_build_internal_headers_falls_back_to_secret_key_in_testing():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "fallback-secret"

    with app.app_context():
        headers = api_client.build_internal_headers()

    assert headers["X-Coyote-Internal-Token"] == "fallback-secret"


def test_build_internal_headers_does_not_fallback_to_secret_key_in_production():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "fallback-secret"

    with app.app_context():
        headers = api_client.build_internal_headers()

    assert "X-Coyote-Internal-Token" not in headers


def test_build_internal_headers_does_not_fallback_to_secret_key_in_development():
    app = Flask(__name__)
    app.config["DEVELOPMENT"] = True
    app.config["SECRET_KEY"] = "fallback-secret"

    with app.app_context():
        headers = api_client.build_internal_headers()

    assert "X-Coyote-Internal-Token" not in headers


def test_endpoint_builders_normalize_paths_and_skip_empty_parts():
    assert endpoints.v1("dna", "/samples/", "S1", "") == "/api/v1/dna/samples/S1"
    assert endpoints.auth("sessions") == "/api/v1/auth/sessions"
    assert endpoints.auth("session") == "/api/v1/auth/session"
    assert endpoints.admin("users") == "/api/v1/users"
    assert endpoints.common("gene", "TP53") == "/api/v1/common/gene/TP53"
    assert endpoints.coverage("plot") == "/api/v1/coverage/plot"
    assert endpoints.dashboard("summary") == "/api/v1/dashboard/summary"
    assert endpoints.dna_sample("S1", "variants") == "/api/v1/samples/S1/small-variants"
    assert endpoints.home("samples") == "/api/v1/samples"
    assert endpoints.home_sample("S1", "context") == "/api/v1/samples/S1/edit-context"
    assert endpoints.internal("roles", "levels") == "/api/v1/internal/roles/levels"
    assert endpoints.public("catalog") == "/api/v1/public/catalog"
    assert endpoints.rna_sample("S1", "fusions") == "/api/v1/samples/S1/fusions"
    assert endpoints.sample("S1", "report") == "/api/v1/samples/S1/report"
