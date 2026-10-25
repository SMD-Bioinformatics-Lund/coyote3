"""Stable SDK errors retaining HTTP responses and safe server diagnostics."""

from __future__ import annotations

import json
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

ModelT = TypeVar("ModelT", bound=BaseModel)


class ResponseValidationError(ValueError):
    """A successful server response does not satisfy the SDK's response contract."""


class ResourceNotLoadedError(RuntimeError):
    """A local resource reference needs refresh() before its metadata can be read."""


class CoyoteAPIError(httpx.HTTPStatusError):
    """An unsuccessful response with structured diagnostics and its original HTTP response."""

    def __init__(self, response: httpx.Response) -> None:
        """Extract diagnostics without including credentials or response bodies in the repr.

        Args:
            response: Unsuccessful API response with its originating request.
        """
        self.status_code = response.status_code
        try:
            body = response.json()
        except ValueError:
            body = {}
        if not isinstance(body, dict):
            body = {}
        self.code: str | None = body.get("code") if isinstance(body.get("code"), str) else None
        self.message: str | None = body.get("error") if isinstance(body.get("error"), str) else None
        self.request_id: str | None = response.headers.get("X-Request-ID")
        if self.request_id is None and isinstance(body.get("request_id"), str):
            self.request_id = body["request_id"]
        self.retry_after: str | None = response.headers.get("Retry-After")
        super().__init__(
            f"Coyote3 API request failed (HTTP {self.status_code})",
            request=response.request,
            response=response,
        )


class AuthenticationError(CoyoteAPIError):
    """The server rejected the session with HTTP 401."""


class PermissionDeniedError(CoyoteAPIError):
    """The server denied access with HTTP 403."""


class NotFoundError(CoyoteAPIError):
    """The requested resource was not found (HTTP 404)."""


class ConflictError(CoyoteAPIError):
    """Current server state conflicts with the operation (HTTP 409)."""


class RequestValidationError(CoyoteAPIError):
    """The server rejected request validation with HTTP 422."""


class RateLimitError(CoyoteAPIError):
    """The server limited the request rate (HTTP 429); retry_after retains its guidance."""


def raise_for_api_status(response: httpx.Response) -> None:
    """Raise a stable SDK error for non-success responses without retrying requests.

    Args:
        response: HTTP response with an originating request.

    Raises:
        CoyoteAPIError: For redirects, client errors and server errors.
    """
    if response.is_success:
        return
    response.read()
    error_type = {
        401: AuthenticationError,
        403: PermissionDeniedError,
        404: NotFoundError,
        409: ConflictError,
        422: RequestValidationError,
        429: RateLimitError,
    }.get(response.status_code, CoyoteAPIError)
    raise error_type(response)


def parse_model(model: type[ModelT], payload: object) -> ModelT:
    """Validate decoded JSON with JSON-mode rules, including ISO datetime parsing.

    Args:
        model: Pydantic response model owned by the SDK or shared transport contract.
        payload: Decoded JSON response.

    Returns:
        Validated response model, retaining meaningful null values.

    Raises:
        ResponseValidationError: If the response shape or values are invalid.
    """
    try:
        return model.model_validate_json(json.dumps(payload))
    except (ValidationError, TypeError, ValueError):
        raise ResponseValidationError(f"Response does not match {model.__name__}") from None
