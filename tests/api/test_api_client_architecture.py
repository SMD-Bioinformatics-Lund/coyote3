"""Tests for Flask -> API transport primitives."""

from __future__ import annotations

import httpx
import pytest

from coyote.services.api_client.api_client import CoyoteApiClient
from coyote.services.api_client.base import ApiPayload, ApiRequestError, BaseApiClient, _as_api_payload


class _ResponseStub:
    """Provide  ResponseStub behavior.
    """
    def __init__(self, status_code: int, json_payload, text: str = ""):
        """Handle __init__.

        Args:
                status_code: Status code.
                json_payload: Json payload.
                text: Text. Optional argument.
        """
        self.status_code = status_code
        self._json_payload = json_payload
        self.text = text

    def json(self):
        """Handle json.

        Returns:
            The function result.
        """
        if isinstance(self._json_payload, Exception):
            raise self._json_payload
        return self._json_payload


def test_api_payload_attribute_access_and_model_dump():
    """Handle test api payload attribute access and model dump.

    Returns:
        The function result.
    """
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
    """Handle test request error is wrapped as api request error.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    class _ClientRaises:
        """Provide  ClientRaises behavior.
        """
        def __init__(self, *args, **kwargs):
            """Handle __init__.

            Args:
                    *args: Args. Additional positional arguments.
                    **kwargs: Kwargs. Additional keyword arguments.
            """
            pass

        def __enter__(self):
            """Handle __enter__.

            Returns:
                    The __enter__ result.
            """
            return self

        def __exit__(self, exc_type, exc, tb):
            """Handle __exit__.

            Args:
                    exc_type: Exc type.
                    exc: Exc.
                    tb: Tb.

            Returns:
                    The __exit__ result.
            """
            return False

        def request(self, **kwargs):
            """Handle request.

            Args:
                **kwargs: Additional keyword values for ``kwargs``.

            Returns:
                The function result.
            """
            req = httpx.Request("GET", "http://example.invalid")
            raise httpx.ConnectError("boom", request=req)

    monkeypatch.setattr(httpx, "Client", _ClientRaises)

    client = BaseApiClient(base_url="http://example.invalid")
    with pytest.raises(ApiRequestError) as exc:
        client._request("GET", "/api/v1/health")
    assert "API request failed" in str(exc.value)


def test_http_error_payload_is_mapped(monkeypatch):
    """Handle test http error payload is mapped.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    class _ClientReturns403:
        """Provide  ClientReturns403 behavior.
        """
        def __init__(self, *args, **kwargs):
            """Handle __init__.

            Args:
                    *args: Args. Additional positional arguments.
                    **kwargs: Kwargs. Additional keyword arguments.
            """
            pass

        def __enter__(self):
            """Handle __enter__.

            Returns:
                    The __enter__ result.
            """
            return self

        def __exit__(self, exc_type, exc, tb):
            """Handle __exit__.

            Args:
                    exc_type: Exc type.
                    exc: Exc.
                    tb: Tb.

            Returns:
                    The __exit__ result.
            """
            return False

        def request(self, **kwargs):
            """Handle request.

            Args:
                **kwargs: Additional keyword values for ``kwargs``.

            Returns:
                The function result.
            """
            return _ResponseStub(403, {"error": "Forbidden"})

    monkeypatch.setattr(httpx, "Client", _ClientReturns403)

    client = BaseApiClient(base_url="http://example.invalid")
    with pytest.raises(ApiRequestError) as exc:
        client._request("GET", "/api/v1/users")
    assert exc.value.status_code == 403
    assert exc.value.message == "Forbidden"
    assert exc.value.payload == {"error": "Forbidden"}


def test_non_dict_payload_rejected(monkeypatch):
    """Handle test non dict payload rejected.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    class _ClientReturnsList:
        """Provide  ClientReturnsList behavior.
        """
        def __init__(self, *args, **kwargs):
            """Handle __init__.

            Args:
                    *args: Args. Additional positional arguments.
                    **kwargs: Kwargs. Additional keyword arguments.
            """
            pass

        def __enter__(self):
            """Handle __enter__.

            Returns:
                    The __enter__ result.
            """
            return self

        def __exit__(self, exc_type, exc, tb):
            """Handle __exit__.

            Args:
                    exc_type: Exc type.
                    exc: Exc.
                    tb: Tb.

            Returns:
                    The __exit__ result.
            """
            return False

        def request(self, **kwargs):
            """Handle request.

            Args:
                **kwargs: Additional keyword values for ``kwargs``.

            Returns:
                The function result.
            """
            return _ResponseStub(200, [{"bad": "shape"}])

    monkeypatch.setattr(httpx, "Client", _ClientReturnsList)

    client = BaseApiClient(base_url="http://example.invalid")
    with pytest.raises(ApiRequestError) as exc:
        client._request("GET", "/api/v1/health")
    assert "invalid payload format" in exc.value.message.lower()


def test_facade_exposes_transport_methods():
    """Handle test facade exposes transport methods.

    Returns:
        The function result.
    """
    required = [
        "get_json",
        "post_json",
    ]
    missing = [name for name in required if not hasattr(CoyoteApiClient, name)]
    assert not missing
