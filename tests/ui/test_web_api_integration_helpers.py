"""Unit tests for Flask-side API integration helpers."""

from __future__ import annotations

from flask import Flask, g

from coyote.errors.exceptions import from_api_request_error
from coyote.services.api_client import api_client, endpoints
from coyote.services.api_client.base import ApiRequestError
from coyote.services.api_client.web import _compose_flash_message


def test_get_web_api_client_uses_configured_base_url():
    """Test get web api client uses configured base url.

    Returns:
        The function result.
    """
    app = Flask(__name__)
    app.config["API_BASE_URL"] = "http://api.local:9000"

    with app.app_context():
        client = api_client.get_web_api_client()

    assert client._base_url == "http://api.local:9000"


def test_get_web_api_client_reuses_client_within_request_context():
    """Test get web api client reuses client within request context.

    Returns:
        The function result.
    """
    app = Flask(__name__)
    app.config["API_BASE_URL"] = "http://api.local:9000"

    with app.test_request_context():
        first = api_client.get_web_api_client()
        second = api_client.get_web_api_client()

    assert first is second


def test_close_web_api_client_removes_request_scoped_client():
    """Test close web api client removes request scoped client.

    Returns:
        The function result.
    """
    app = Flask(__name__)
    app.config["API_BASE_URL"] = "http://api.local:9000"

    with app.test_request_context():
        client = api_client.get_web_api_client()
        api_client.close_web_api_client()

        assert getattr(g, "_coyote_api_client", None) is None
        assert getattr(client._client, "is_closed", True) is True


def test_build_forward_headers_includes_cookie_if_present():
    """Test build forward headers includes cookie if present.

    Returns:
        The function result.
    """
    headers = api_client.build_forward_headers({"Cookie": "session=abc"})
    assert headers == {
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json",
        "Cookie": "session=abc",
    }


def test_build_forward_headers_includes_request_id_when_present():
    """Test build forward headers includes request id when present.

    Returns:
        The function result.
    """
    headers = api_client.build_forward_headers({"X-Request-ID": "rid-123"})
    assert headers["X-Request-ID"] == "rid-123"


def test_forward_headers_without_request_context_returns_default_header():
    """Test forward headers without request context returns default header.

    Returns:
        The function result.
    """
    assert api_client.forward_headers() == {
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json",
    }


def test_forward_headers_with_request_context_includes_cookie():
    """Test forward headers with request context includes cookie.

    Returns:
        The function result.
    """
    app = Flask(__name__)

    with app.test_request_context(headers={"Cookie": "foo=bar"}):
        headers = api_client.forward_headers()

    assert headers["X-Requested-With"] == "XMLHttpRequest"
    assert headers["Accept"] == "application/json"
    assert headers["Cookie"] == "foo=bar"


def test_forward_headers_with_api_session_cookie_adds_bearer_auth():
    """Test forward headers with api session cookie adds bearer auth.

    Returns:
        The function result.
    """
    app = Flask(__name__)
    app.config["API_SESSION_COOKIE_NAME"] = "coyote3_api_session"

    with app.test_request_context(headers={"Cookie": "coyote3_api_session=token123; foo=bar"}):
        headers = api_client.forward_headers()

    assert headers["Authorization"] == "Bearer token123"


def test_forward_headers_falls_back_to_flask_request_id_context():
    """Test forward headers falls back to flask request id context.

    Returns:
        The function result.
    """
    app = Flask(__name__)

    with app.test_request_context(headers={"Cookie": "foo=bar"}):
        g.request_id = "rid-g"
        headers = api_client.forward_headers()

    assert headers["X-Request-ID"] == "rid-g"


def test_build_internal_headers_uses_internal_token_or_secret_key():
    """Test build internal headers uses internal token or secret key.

    Returns:
        The function result.
    """
    app = Flask(__name__)
    app.config["INTERNAL_API_TOKEN"] = "internal-token"
    app.config["SECRET_KEY"] = "fallback-secret"

    with app.app_context():
        headers = api_client.build_internal_headers()

    assert headers["X-Coyote-Internal-Token"] == "internal-token"
    assert headers["Accept"] == "application/json"


def test_build_internal_headers_falls_back_to_secret_key_in_testing():
    """Test build internal headers falls back to secret key in testing.

    Returns:
        The function result.
    """
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "fallback-secret"

    with app.app_context():
        headers = api_client.build_internal_headers()

    assert headers["X-Coyote-Internal-Token"] == "fallback-secret"


def test_build_internal_headers_does_not_fallback_to_secret_key_in_production():
    """Test build internal headers does not fallback to secret key in production.

    Returns:
        The function result.
    """
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "fallback-secret"

    with app.app_context():
        headers = api_client.build_internal_headers()

    assert "X-Coyote-Internal-Token" not in headers


def test_build_internal_headers_does_not_fallback_to_secret_key_in_development():
    """Test build internal headers does not fallback to secret key in development.

    Returns:
        The function result.
    """
    app = Flask(__name__)
    app.config["DEVELOPMENT"] = True
    app.config["SECRET_KEY"] = "fallback-secret"

    with app.app_context():
        headers = api_client.build_internal_headers()

    assert "X-Coyote-Internal-Token" not in headers


def test_endpoint_builders_normalize_paths_and_skip_empty_parts():
    """Test endpoint builders normalize paths and skip empty parts.

    Returns:
        The function result.
    """
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


def test_from_api_request_error_preserves_4xx_headline_and_details():
    """4xx page errors should keep the domain-specific headline and troubleshooting detail."""
    exc = ApiRequestError(
        message="ASPC not registered for assay 'hema_GMSv1' in environment 'production'",
        status_code=422,
        payload={
            "error": "ASPC not registered for assay 'hema_GMSv1' in environment 'production'",
            "details": "Sample '26MD04507p' belongs to environment 'production'.",
            "hint": "Create and activate the ASPC for this assay/environment combination.",
        },
    )

    page_error = from_api_request_error(exc, summary="Unable to load DNA findings.")

    assert page_error.status_code == 422
    assert (
        page_error.message
        == "ASPC not registered for assay 'hema_GMSv1' in environment 'production'"
    )
    assert "Sample '26MD04507p' belongs to environment 'production'." in str(page_error.details)
    assert "Hint: Create and activate the ASPC for this assay/environment combination." in str(
        page_error.details
    )
    assert endpoints.public("catalog") == "/api/v1/public/catalog"
    assert endpoints.rna_sample("S1", "fusions") == "/api/v1/samples/S1/fusions"
    assert endpoints.sample("S1", "report") == "/api/v1/samples/S1/report"


def test_compose_flash_message_includes_upstream_details_and_hint():
    """Flash messages should include the actionable upstream reason when available."""
    exc = ApiRequestError(
        message="body.config.asp_group: Value error, asp_group must be one of ['hematology']",
        status_code=400,
        payload={
            "error": "Invalid assay_specific_panels payload",
            "details": "body.config.asp_group: Value error, asp_group must be one of ['hematology']",
            "hint": "Select one of the supported assay groups from the dropdown.",
        },
    )

    message = _compose_flash_message("Failed to create assay panel.", exc)

    assert "Failed to create assay panel. (HTTP 400)" in message
    assert "body.config.asp_group: Value error" in message
    assert "Hint: Select one of the supported assay groups from the dropdown." in message
