"""Tests for the split Flask -> API integration client architecture."""

from __future__ import annotations

import httpx
import pytest

from coyote.integrations.api.api_client import CoyoteApiClient
from coyote.integrations.api.base import ApiPayload, ApiRequestError, BaseApiClient, _as_api_payload


class _ResponseStub:
    def __init__(self, status_code: int, json_payload, text: str = ""):
        self.status_code = status_code
        self._json_payload = json_payload
        self.text = text

    def json(self):
        if isinstance(self._json_payload, Exception):
            raise self._json_payload
        return self._json_payload


def test_api_payload_attribute_access_and_model_dump():
    payload = _as_api_payload(
        {
            "sample": {"id": "S1", "meta": {"assay": "DNA"}},
            "items": [{"value": 1}, {"value": 2}],
        }
    )

    assert isinstance(payload, ApiPayload)
    assert payload.sample.id == "S1"
    assert payload.sample.meta.assay == "DNA"
    assert payload["items"][1].value == 2
    assert payload.model_dump() == {
        "sample": {"id": "S1", "meta": {"assay": "DNA"}},
        "items": [{"value": 1}, {"value": 2}],
    }


def test_request_error_is_wrapped_as_api_request_error(monkeypatch):
    class _ClientRaises:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def request(self, **kwargs):
            req = httpx.Request("GET", "http://example.invalid")
            raise httpx.ConnectError("boom", request=req)

    monkeypatch.setattr(httpx, "Client", _ClientRaises)

    client = BaseApiClient(base_url="http://example.invalid")
    with pytest.raises(ApiRequestError) as exc:
        client._request("GET", "/api/v1/health")
    assert "API request failed" in str(exc.value)


def test_http_error_payload_is_mapped(monkeypatch):
    class _ClientReturns403:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def request(self, **kwargs):
            return _ResponseStub(403, {"error": "Forbidden"})

    monkeypatch.setattr(httpx, "Client", _ClientReturns403)

    client = BaseApiClient(base_url="http://example.invalid")
    with pytest.raises(ApiRequestError) as exc:
        client._request("GET", "/api/v1/admin/users")
    assert exc.value.status_code == 403
    assert exc.value.message == "Forbidden"
    assert exc.value.payload == {"error": "Forbidden"}


def test_non_dict_payload_rejected(monkeypatch):
    class _ClientReturnsList:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def request(self, **kwargs):
            return _ResponseStub(200, [{"bad": "shape"}])

    monkeypatch.setattr(httpx, "Client", _ClientReturnsList)

    client = BaseApiClient(base_url="http://example.invalid")
    with pytest.raises(ApiRequestError) as exc:
        client._request("GET", "/api/v1/health")
    assert "invalid payload format" in exc.value.message.lower()


def test_facade_exposes_transport_methods():
    required = [
        "get_json",
        "post_json",
    ]
    missing = [name for name in required if not hasattr(CoyoteApiClient, name)]
    assert not missing
