"""Shared transport primitives for Flask -> API calls."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import httpx

_SENSITIVE_KEYS = {
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "cookie",
    "session",
}


@dataclass
class ApiRequestError(Exception):
    """Represent the api request error type."""

    message: str
    status_code: int | None = None
    payload: Any | None = None

    def __str__(self) -> str:
        """__str__.

        Returns:
                The __str__ result.
        """
        return self.message


class ApiPayload(dict[str, Any]):
    """Dict with attribute access for API payloads."""

    def __getattr__(self, key: str) -> Any:
        """__getattr__.

        Args:
                key: Key.

        Returns:
                The __getattr__ result.
        """
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc

    def __setattr__(self, key: str, value: Any) -> None:
        """__setattr__.

        Args:
                key: Key.
                value: Value.

        Returns:
                None.
        """
        self[key] = value

    def model_dump(self) -> dict[str, Any]:
        """Model dump.

        Returns:
            dict[str, Any]: Normalized return value.
        """
        return _to_builtin(self)


def _as_api_payload(value: Any) -> Any:
    """As api payload.

    Args:
            value: Value.

    Returns:
            The  as api payload result.
    """
    if isinstance(value, dict):
        return ApiPayload({k: _as_api_payload(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_as_api_payload(v) for v in value]
    return value


def _to_builtin(value: Any) -> Any:
    """To builtin.

    Args:
            value: Value.

    Returns:
            The  to builtin result.
    """
    if isinstance(value, ApiPayload):
        return {k: _to_builtin(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_builtin(v) for v in value]
    return value


def _to_json_compatible(value: Any) -> Any:
    """Convert nested values to JSON-serializable builtins for httpx."""
    if isinstance(value, ApiPayload):
        return {k: _to_json_compatible(v) for k, v in value.items()}
    if isinstance(value, dict):
        return {k: _to_json_compatible(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_json_compatible(v) for v in value]
    if isinstance(value, tuple):
        return [_to_json_compatible(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


class BaseApiClient:
    """Provide the base api client type."""

    def __init__(
        self, base_url: str, timeout_seconds: float = 30.0, client: httpx.Client | None = None
    ) -> None:
        """__init__.

        Args:
                base_url: Base url.
                timeout_seconds: Timeout seconds. Optional argument.
                client: Client. Optional argument.
        """
        self._base_url = str(base_url).rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._client = client or httpx.Client(
            timeout=self._timeout_seconds,
            headers={"Accept": "application/json"},
        )
        self._last_response_headers: dict[str, str] = {}
        self._last_response_cookies: dict[str, str] = {}

    def _request(
        self,
        method: str,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Request.

        Args:
                method: Method.
                path: Path.
                headers: Headers. Optional argument.
                params: Params. Optional argument.
                json_body: Json body. Optional argument.

        Returns:
                The  request result.
        """
        url = f"{self._base_url}{path}"
        try:
            response = self._client.request(
                method=method,
                url=url,
                headers=headers or {},
                params=params or None,
                json=_to_json_compatible(json_body) if json_body is not None else None,
            )
        except httpx.RequestError as exc:
            raise ApiRequestError(message=f"API request failed: {exc}") from exc

        response_headers = getattr(response, "headers", {}) or {}
        response_cookies = getattr(response, "cookies", {}) or {}
        self._last_response_headers = dict(response_headers)
        if hasattr(response_cookies, "items"):
            self._last_response_cookies = {name: value for name, value in response_cookies.items()}
        else:
            self._last_response_cookies = {}

        try:
            payload = response.json()
        except Exception:
            payload = {"error": response.text}

        if response.status_code >= 400:
            message = self._safe_error_message(payload, response.status_code)
            raise ApiRequestError(
                message=message,
                status_code=response.status_code,
                payload=payload,
            )

        if not isinstance(payload, dict):
            raise ApiRequestError(
                message="API returned invalid payload format.",
                status_code=response.status_code,
                payload=payload,
            )
        return payload

    def _request_multipart(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: list[tuple[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send multipart/form-data request and decode JSON payload."""
        url = f"{self._base_url}{path}"
        try:
            response = self._client.request(
                method=method,
                url=url,
                headers=headers or {},
                params=params or None,
                data=data or None,
                files=files or None,
            )
        except httpx.RequestError as exc:
            raise ApiRequestError(message=f"API request failed: {exc}") from exc

        response_headers = getattr(response, "headers", {}) or {}
        response_cookies = getattr(response, "cookies", {}) or {}
        self._last_response_headers = dict(response_headers)
        if hasattr(response_cookies, "items"):
            self._last_response_cookies = {name: value for name, value in response_cookies.items()}
        else:
            self._last_response_cookies = {}

        try:
            payload = response.json()
        except Exception:
            payload = {"error": response.text}

        if response.status_code >= 400:
            message = self._safe_error_message(payload, response.status_code)
            raise ApiRequestError(
                message=message,
                status_code=response.status_code,
                payload=payload,
            )
        if not isinstance(payload, dict):
            raise ApiRequestError(
                message="API returned invalid payload format.",
                status_code=response.status_code,
                payload=payload,
            )
        return payload

    def _safe_error_message(self, payload: Any, status_code: int) -> str:
        """Safe error message.

        Args:
                payload: Payload.
                status_code: Status code.

        Returns:
                The  safe error message result.
        """
        if isinstance(payload, dict):
            raw = str(payload.get("error") or payload.get("details") or "").strip()
            if raw:
                lowered = raw.lower()
                if any(key in lowered for key in _SENSITIVE_KEYS):
                    return f"API request failed ({status_code})"
                return raw[:200]
        return f"API request failed ({status_code})"

    def _get(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> ApiPayload:
        """Get.

        Args:
                path: Path.
                headers: Headers. Optional argument.
                params: Params. Optional argument.

        Returns:
                The  get result.
        """
        return _as_api_payload(self._request("GET", path, headers=headers, params=params))

    def _post(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> ApiPayload:
        """Post.

        Args:
                path: Path.
                headers: Headers. Optional argument.
                params: Params. Optional argument.
                json_body: Json body. Optional argument.

        Returns:
                The  post result.
        """
        return _as_api_payload(
            self._request("POST", path, headers=headers, params=params, json_body=json_body)
        )

    def _put(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> ApiPayload:
        """Put.

        Args:
                path: Path.
                headers: Headers. Optional argument.
                params: Params. Optional argument.
                json_body: Json body. Optional argument.

        Returns:
                The  put result.
        """
        return _as_api_payload(
            self._request("PUT", path, headers=headers, params=params, json_body=json_body)
        )

    def _patch(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> ApiPayload:
        """Patch.

        Args:
                path: Path.
                headers: Headers. Optional argument.
                params: Params. Optional argument.
                json_body: Json body. Optional argument.

        Returns:
                The  patch result.
        """
        return _as_api_payload(
            self._request("PATCH", path, headers=headers, params=params, json_body=json_body)
        )

    def _delete(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> ApiPayload:
        """Delete.

        Args:
                path: Path.
                headers: Headers. Optional argument.
                params: Params. Optional argument.
                json_body: Json body. Optional argument.

        Returns:
                The  delete result.
        """
        return _as_api_payload(
            self._request("DELETE", path, headers=headers, params=params, json_body=json_body)
        )

    def get_json(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> ApiPayload:
        """Return json.

        Args:
            path (str): Normalized ``path``.
            headers (dict[str, str] | None): Normalized ``headers``.
            params (dict[str, Any] | None): Normalized ``params``.

        Returns:
            ApiPayload: Normalized return value.
        """
        return self._get(path, headers=headers, params=params)

    def post_json(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> ApiPayload:
        """Post json.

        Args:
            path (str): Normalized ``path``.
            headers (dict[str, str] | None): Normalized ``headers``.
            params (dict[str, Any] | None): Normalized ``params``.
            json_body (dict[str, Any] | None): Normalized ``json_body``.

        Returns:
            ApiPayload: Normalized return value.
        """
        return self._post(path, headers=headers, params=params, json_body=json_body)

    def put_json(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> ApiPayload:
        """Put json.

        Args:
            path (str): Normalized ``path``.
            headers (dict[str, str] | None): Normalized ``headers``.
            params (dict[str, Any] | None): Normalized ``params``.
            json_body (dict[str, Any] | None): Normalized ``json_body``.

        Returns:
            ApiPayload: Normalized return value.
        """
        return self._put(path, headers=headers, params=params, json_body=json_body)

    def patch_json(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> ApiPayload:
        """Patch json.

        Args:
            path (str): Normalized ``path``.
            headers (dict[str, str] | None): Normalized ``headers``.
            params (dict[str, Any] | None): Normalized ``params``.
            json_body (dict[str, Any] | None): Normalized ``json_body``.

        Returns:
            ApiPayload: Normalized return value.
        """
        return self._patch(path, headers=headers, params=params, json_body=json_body)

    def delete_json(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> ApiPayload:
        """Delete json.

        Args:
            path (str): Normalized ``path``.
            headers (dict[str, str] | None): Normalized ``headers``.
            params (dict[str, Any] | None): Normalized ``params``.
            json_body (dict[str, Any] | None): Normalized ``json_body``.

        Returns:
            ApiPayload: Normalized return value.
        """
        return self._delete(path, headers=headers, params=params, json_body=json_body)

    def post_multipart(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: list[tuple[str, Any]] | None = None,
    ) -> ApiPayload:
        """Post multipart form-data payload."""
        return _as_api_payload(
            self._request_multipart(
                "POST",
                path,
                headers=headers,
                params=params,
                data=data,
                files=files,
            )
        )

    def close(self) -> None:
        """Close.

        Returns:
            None.
        """
        self._client.close()

    def last_response_cookie(self, name: str) -> str | None:
        """Last response cookie.

        Args:
            name (str): Normalized ``name``.

        Returns:
            str | None: Normalized return value.
        """
        return self._last_response_cookies.get(name)

    def last_response_header(self, name: str) -> str | None:
        """Last response header.

        Args:
            name (str): Normalized ``name``.

        Returns:
            str | None: Normalized return value.
        """
        return self._last_response_headers.get(name)
