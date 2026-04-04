"""HTTP middleware assembly for the FastAPI app."""

from __future__ import annotations

import time
import uuid
from typing import Awaitable, Callable

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from api.lifecycle import ensure_runtime_initialized
from api.observability.prometheus_metrics import observe_request, record_rate_limited
from api.runtime_state import (
    app as runtime_app,
)
from api.runtime_state import (
    current_username,
    reset_current_request_id,
    reset_current_user,
    set_current_request_id,
    set_current_user,
)
from api.security.access import is_public_api_path, resolve_request_user
from api.security.audit_events import emit_mutation_event, emit_request_event, request_ip
from shared.rate_limit import FixedWindowRateLimiter

_API_RATE_LIMIT_EXCLUDED_PATHS = frozenset(
    {
        "/api/v1/health",
        "/api/v1/docs",
        "/api/v1/openapi.json",
        "/api/v1/redoc",
        "/api/v1/internal/metrics",
    }
)
_API_LIMITER: FixedWindowRateLimiter | None = None
_API_LIMITER_CFG: tuple[int, int] | None = None


def _get_api_limiter() -> FixedWindowRateLimiter | None:
    global _API_LIMITER, _API_LIMITER_CFG
    enabled = bool(runtime_app.config.get("API_RATE_LIMIT_ENABLED", True))
    if not enabled:
        _API_LIMITER = None
        _API_LIMITER_CFG = None
        return None
    limit = int(runtime_app.config.get("API_RATE_LIMIT_REQUESTS_PER_MINUTE", 600))
    window_seconds = int(runtime_app.config.get("API_RATE_LIMIT_WINDOW_SECONDS", 60))
    cfg = (limit, window_seconds)
    if _API_LIMITER is None or _API_LIMITER_CFG != cfg:
        _API_LIMITER = FixedWindowRateLimiter(limit=limit, window_seconds=window_seconds)
        _API_LIMITER_CFG = cfg
    return _API_LIMITER


def build_authentication_middleware(
    *, testing: bool, development: bool
) -> Callable[[Request, Callable[..., Awaitable[JSONResponse]]], Awaitable[JSONResponse]]:
    """Build the request middleware that initializes runtime state and enforces API auth."""

    async def api_authentication_middleware(request: Request, call_next):
        """Api authentication middleware.

        Args:
            request (Request): Value for ``request``.
            call_next: Value for ``call_next``.

        Returns:
            The function result.
        """
        ensure_runtime_initialized(testing=testing, development=development)
        start = time.perf_counter()
        path = request.url.path
        authenticated_user = None
        user_token = None
        request_id = (request.headers.get("X-Request-ID") or "").strip() or str(uuid.uuid4())
        request.state.request_id = request_id
        request_token = set_current_request_id(request_id)
        if path.startswith("/api/v1/"):
            limiter = _get_api_limiter()
            if limiter and path not in _API_RATE_LIMIT_EXCLUDED_PATHS:
                ip = request_ip(request)
                allowed, retry_after = limiter.check(f"{ip}|{request.method}")
                if not allowed:
                    duration_ms = (time.perf_counter() - start) * 1000.0
                    record_rate_limited(path=path)
                    observe_request(
                        method=request.method,
                        path=path,
                        status_code=429,
                        duration_ms=duration_ms,
                    )
                    response = JSONResponse(
                        status_code=429,
                        content={"status": 429, "error": "Too many requests"},
                        headers={"Retry-After": str(retry_after), "X-Request-ID": request_id},
                    )
                    runtime_app.logger.warning(
                        "api_rate_limited request_id=%s method=%s path=%s ip=%s retry_after=%ss",
                        request_id,
                        request.method,
                        path,
                        ip,
                        retry_after,
                    )
                    reset_current_request_id(request_token)
                    return response
            authenticated_user = resolve_request_user(request)
            if authenticated_user is not None:
                request.state.authenticated_user = authenticated_user
                user_token = set_current_user(authenticated_user)
            if not is_public_api_path(path) and authenticated_user is None:
                response = _unauthorized_response(
                    request=request, request_id=request_id, start=start
                )
                if user_token is not None:
                    reset_current_user(user_token)
                reset_current_request_id(request_token)
                return response

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        duration_ms = (time.perf_counter() - start) * 1000.0
        username = (
            authenticated_user.username
            if authenticated_user is not None
            else current_username(default="anonymous")
        )
        runtime_app.logger.info(
            "api_request request_id=%s method=%s path=%s status=%s duration_ms=%.2f user=%s ip=%s",
            request_id,
            request.method,
            path,
            response.status_code,
            duration_ms,
            username,
            request_ip(request),
        )
        if path.startswith("/api/v1/"):
            observe_request(
                method=request.method,
                path=path,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
            emit_request_event(
                request=request,
                username=username,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
        if (
            path.startswith("/api/v1/")
            and request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}
            and not is_public_api_path(path)
        ):
            emit_mutation_event(
                request=request,
                username=username,
                status_code=response.status_code,
                action=request.method.upper(),
                target=path,
            )
        if user_token is not None:
            reset_current_user(user_token)
        reset_current_request_id(request_token)
        return response

    return api_authentication_middleware


def _unauthorized_response(*, request: Request, request_id: str, start: float) -> JSONResponse:
    """Return a standardized unauthenticated API response and emit request audit metadata."""
    exc = HTTPException(status_code=401, detail={"status": 401, "error": "Login required"})
    payload = (
        exc.detail
        if isinstance(exc.detail, dict)
        else {"status": exc.status_code, "error": str(exc.detail)}
    )
    response = JSONResponse(status_code=exc.status_code, content=payload)
    response.headers["X-Request-ID"] = request_id
    duration_ms = (time.perf_counter() - start) * 1000.0
    runtime_app.logger.info(
        "api_request request_id=%s method=%s path=%s status=%s duration_ms=%.2f user=%s ip=%s",
        request_id,
        request.method,
        request.url.path,
        exc.status_code,
        duration_ms,
        "anonymous",
        request_ip(request),
    )
    observe_request(
        method=request.method,
        path=request.url.path,
        status_code=exc.status_code,
        duration_ms=duration_ms,
    )
    emit_request_event(
        request=request,
        username="anonymous",
        status_code=exc.status_code,
        duration_ms=duration_ms,
        extra={"kind": "authentication"},
    )
    return response
