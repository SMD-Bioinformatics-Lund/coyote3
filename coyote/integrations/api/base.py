"""Shared transport primitives for Flask -> API calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class ApiRequestError(Exception):
    message: str
    status_code: int | None = None
    payload: Any | None = None

    def __str__(self) -> str:
        return self.message



class ApiPayload(dict[str, Any]):
    """Dict with attribute access for API payloads."""

    def __getattr__(self, key: str) -> Any:
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value

    def model_dump(self) -> dict[str, Any]:
        return _to_builtin(self)



def _as_api_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return ApiPayload({k: _as_api_payload(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_as_api_payload(v) for v in value]
    return value



def _to_builtin(value: Any) -> Any:
    if isinstance(value, ApiPayload):
        return {k: _to_builtin(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_builtin(v) for v in value]
    return value



class BaseApiClient:
    def __init__(self, base_url: str, timeout_seconds: float = 30.0) -> None:
        self._base_url = str(base_url).rstrip("/")
        self._timeout_seconds = timeout_seconds

    def _request(
        self,
        method: str,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                response = client.request(
                    method=method,
                    url=url,
                    headers=headers or {},
                    params=params or None,
                    json=json_body,
                )
        except httpx.RequestError as exc:
            raise ApiRequestError(message=f"API request failed: {exc}") from exc

        try:
            payload = response.json()
        except Exception:
            payload = {"error": response.text}

        if response.status_code >= 400:
            message = payload.get("error", f"API request failed ({response.status_code})")
            raise ApiRequestError(message=message, status_code=response.status_code, payload=payload)

        if not isinstance(payload, dict):
            raise ApiRequestError(
                message="API returned invalid payload format.",
                status_code=response.status_code,
                payload=payload,
            )
        return payload

    def _get(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> ApiPayload:
        return _as_api_payload(self._request("GET", path, headers=headers, params=params))

    def _post(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> ApiPayload:
        return _as_api_payload(self._request("POST", path, headers=headers, params=params, json_body=json_body))

    def get_json(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> ApiPayload:
        return self._get(path, headers=headers, params=params)

    def post_json(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> ApiPayload:
        return self._post(path, headers=headers, params=params, json_body=json_body)

