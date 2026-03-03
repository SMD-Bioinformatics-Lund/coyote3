"""Unit tests for Flask-side API integration helpers."""

from __future__ import annotations

from flask import Flask

from coyote.services.api_client import api_client, endpoints


def test_get_web_api_client_uses_configured_base_url():
    app = Flask(__name__)
    app.config["API_BASE_URL"] = "http://api.local:9000"

    with app.app_context():
        client = api_client.get_web_api_client()

    assert client._base_url == "http://api.local:9000"


def test_build_forward_headers_includes_cookie_if_present():
    headers = api_client.build_forward_headers({"Cookie": "session=abc"})
    assert headers == {
        "X-Requested-With": "XMLHttpRequest",
        "Cookie": "session=abc",
    }


def test_forward_headers_without_request_context_returns_default_header():
    assert api_client.forward_headers() == {"X-Requested-With": "XMLHttpRequest"}


def test_forward_headers_with_request_context_includes_cookie():
    app = Flask(__name__)

    with app.test_request_context(headers={"Cookie": "foo=bar"}):
        headers = api_client.forward_headers()

    assert headers["X-Requested-With"] == "XMLHttpRequest"
    assert headers["Cookie"] == "foo=bar"


def test_build_internal_headers_uses_internal_token_or_secret_key():
    app = Flask(__name__)
    app.config["INTERNAL_API_TOKEN"] = "internal-token"
    app.config["SECRET_KEY"] = "fallback-secret"

    with app.app_context():
        headers = api_client.build_internal_headers()

    assert headers["X-Coyote-Internal-Token"] == "internal-token"


def test_build_internal_headers_falls_back_to_secret_key():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "fallback-secret"

    with app.app_context():
        headers = api_client.build_internal_headers()

    assert headers["X-Coyote-Internal-Token"] == "fallback-secret"


def test_endpoint_builders_normalize_paths_and_skip_empty_parts():
    assert endpoints.v1("dna", "/samples/", "S1", "") == "/api/v1/dna/samples/S1"
    assert endpoints.auth("login") == "/api/v1/auth/login"
    assert endpoints.admin("users") == "/api/v1/admin/users"
    assert endpoints.common("gene", "TP53") == "/api/v1/common/gene/TP53"
    assert endpoints.coverage("plot") == "/api/v1/coverage/plot"
    assert endpoints.dashboard("summary") == "/api/v1/dashboard/summary"
    assert endpoints.dna_sample("S1", "variants") == "/api/v1/dna/samples/S1/variants"
    assert endpoints.home("samples") == "/api/v1/home/samples"
    assert endpoints.home_sample("S1", "context") == "/api/v1/home/samples/S1/context"
    assert endpoints.internal("roles", "levels") == "/api/v1/internal/roles/levels"
    assert endpoints.public("catalog") == "/api/v1/public/catalog"
    assert endpoints.rna_sample("S1", "fusions") == "/api/v1/rna/samples/S1/fusions"
    assert endpoints.sample("S1", "report") == "/api/v1/samples/S1/report"
