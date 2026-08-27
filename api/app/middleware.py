"""HTTP middleware assembly for the FastAPI app."""

from __future__ import annotations

import time
from typing import Awaitable, Callable

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from api.app.lifecycle import ensure_runtime_initialized
from api.app.runtime_state import (
    app as runtime_app,
)
from api.app.runtime_state import (
    current_username,
    reset_current_request_id,
    reset_current_user,
    set_current_request_id,
    set_current_user,
)
from api.config.application_modules import modules_for_api_path
from api.infra.observability.logging import (
    bind_request_context,
    request_context_from_request,
    reset_request_context,
)
from api.infra.observability.prometheus_metrics import observe_request, record_rate_limited
from api.infra.rate_limit import RedisFixedWindowRateLimiter
from api.security.access import (
    is_public_api_path,
    requires_csrf_validation,
    resolve_request_user,
    validate_request_csrf,
)
from api.security.audit_events import emit_mutation_event, emit_request_event, request_ip

_API_RATE_LIMIT_EXCLUDED_PATHS = frozenset(
    {
        "/api/v1/health",
        "/api/v1/docs",
        "/api/v1/openapi.json",
        "/api/v1/redoc",
        "/api/v1/internal/metrics",
    }
)
_API_ACCESS_LOG_EXCLUDED_PATHS = frozenset(
    {
        "/api/v1/health",
        "/api/v1/internal/metrics",
    }
)
_API_LIMITER: RedisFixedWindowRateLimiter | None = None
_API_LIMITER_CFG: tuple[int, int, int] | None = None

_API_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
    "form-action 'self'; img-src 'self' data: blob: https:; font-src 'self' data:; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "script-src 'self' https://cdn.jsdelivr.net; connect-src 'self'"
)
_OPENAPI_UI_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
    "form-action 'self'; img-src 'self' data: blob: https:; "
    "font-src 'self' data: https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; connect-src 'self'"
)
_OPENAPI_UI_PATHS = frozenset({"/api/v1/docs", "/api/v1/redoc"})


def _get_api_limiter() -> RedisFixedWindowRateLimiter | None:
    global _API_LIMITER, _API_LIMITER_CFG
    enabled = bool(runtime_app.config.get("API_RATE_LIMIT_ENABLED", True))
    if not enabled:
        _API_LIMITER = None
        _API_LIMITER_CFG = None
        return None
    limit = int(runtime_app.config.get("API_RATE_LIMIT_REQUESTS_PER_MINUTE", 600))
    window_seconds = int(runtime_app.config.get("API_RATE_LIMIT_WINDOW_SECONDS", 60))
    backend = runtime_app.cache
    if backend is None:
        raise RuntimeError("Redis cache must be initialized before API rate limiting")
    cfg = (limit, window_seconds, id(backend))
    if _API_LIMITER is None or _API_LIMITER_CFG != cfg:
        _API_LIMITER = RedisFixedWindowRateLimiter(
            backend=backend, limit=limit, window_seconds=window_seconds
        )
        _API_LIMITER_CFG = cfg
    return _API_LIMITER


def build_authentication_middleware(
    *, testing: bool, development: bool
) -> Callable[[Request, Callable[..., Awaitable[JSONResponse]]], Awaitable[JSONResponse]]:
    """Build the request middleware that initializes runtime state and enforces API auth."""

    async def api_authentication_middleware(request: Request, call_next):
        """Initialize request context, auth, and audit metadata.

        Args:
            request: Active FastAPI request object.
            call_next: Downstream request handler.

        Returns:
            Response: Final response for the request.
        """
        ensure_runtime_initialized(testing=testing, development=development)
        start = time.perf_counter()
        path = request.url.path
        authenticated_user = None
        user_token = None
        request_context = request_context_from_request(request)
        context_token = bind_request_context(request_context)
        request_id = request_context.request_id
        request.state.request_id = request_id
        request_token = set_current_request_id(request_id)
        try:
            if path.startswith("/api/v1/"):
                limiter = _get_api_limiter()
                if limiter and path not in _API_RATE_LIMIT_EXCLUDED_PATHS:
                    ip = request_ip(request)
                    # Resolve the user here (before the gate) so the rate-limit
                    # bucket is per-user rather than per-IP when authenticated.
                    # This prevents co-located authenticated users sharing quota
                    # and stops credential-rotating IP bypass attempts.
                    _early_user = resolve_request_user(request)
                    _rate_limit_identity = (
                        f"{ip}|{_early_user.username}|{request.method}"
                        if _early_user is not None
                        else f"{ip}|{request.method}"
                    )
                    try:
                        allowed, retry_after = limiter.check(_rate_limit_identity)
                    except Exception:
                        runtime_app.logger.exception("api_rate_limit_backend_unavailable")
                        return JSONResponse(
                            status_code=503,
                            content={
                                "status": 503,
                                "error": "Request protection service is unavailable",
                                "details": "Retry the request shortly.",
                            },
                            headers={"Retry-After": "5", "X-Request-ID": request_id},
                        )
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
                            "api_rate_limited",
                            extra={"retry_after": retry_after, "ip": ip},
                        )
                        return response
                # Reuse the early resolution performed for the rate-limit key
                # when available, otherwise resolve now (unauthenticated paths).
                authenticated_user = (
                    _early_user
                    if limiter and path not in _API_RATE_LIMIT_EXCLUDED_PATHS
                    else resolve_request_user(request)
                )
                if authenticated_user is not None:
                    request.state.authenticated_user = authenticated_user
                    user_token = set_current_user(authenticated_user)
                if not is_public_api_path(path) and authenticated_user is None:
                    response = _unauthorized_response(
                        request=request, request_id=request_id, start=start
                    )
                    return response

                if (
                    bool(runtime_app.config.get("API_CSRF_ENABLED", True))
                    and authenticated_user is not None
                    and requires_csrf_validation(request.method, path)
                    and not validate_request_csrf(request)
                ):
                    return JSONResponse(
                        status_code=403,
                        content={
                            "status": 403,
                            "error": "CSRF validation failed",
                            "details": "Refresh the page and retry the action.",
                        },
                        headers={"X-Request-ID": request_id},
                    )

                governed_modules = modules_for_api_path(path)
                if governed_modules:
                    from api.app.deps.services import get_app_controls_service

                    controls_service = get_app_controls_service()
                    disabled_module = next(
                        (
                            module
                            for module in governed_modules
                            if not controls_service.module_enabled(module.key)
                        ),
                        None,
                    )
                    if disabled_module is not None:
                        duration_ms = (time.perf_counter() - start) * 1000.0
                        username = (
                            authenticated_user.username
                            if authenticated_user is not None
                            else current_username(default="anonymous")
                        )
                        response = JSONResponse(
                            status_code=503,
                            content={
                                "status": 503,
                                "error": f"{disabled_module.label} is temporarily unavailable",
                                "details": disabled_module.description,
                                "category": "module_disabled",
                                "hint": "Contact an application administrator if this module should be available.",
                                "module": disabled_module.key,
                            },
                            headers={"Retry-After": "60", "X-Request-ID": request_id},
                        )
                        _log_api_request(
                            request_id=request_id,
                            method=request.method,
                            path=path,
                            status_code=503,
                            duration_ms=duration_ms,
                            username=username,
                            ip=request_ip(request),
                        )
                        observe_request(
                            method=request.method,
                            path=path,
                            status_code=503,
                            duration_ms=duration_ms,
                        )
                        emit_request_event(
                            request=request,
                            username=username,
                            status_code=503,
                            duration_ms=duration_ms,
                            extra={
                                "kind": "module_disabled",
                                "module": disabled_module.key,
                            },
                        )
                        return response

            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            duration_ms = (time.perf_counter() - start) * 1000.0
            username = (
                authenticated_user.username
                if authenticated_user is not None
                else current_username(default="anonymous")
            )
            _log_api_request(
                request_id=request_id,
                method=request.method,
                path=path,
                status_code=int(response.status_code),
                duration_ms=duration_ms,
                username=username,
                ip=request_ip(request),
            )
            if path.startswith("/api/v1/"):
                observe_request(
                    method=request.method,
                    path=path,
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                )
                if int(response.status_code) >= 400:
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
            return response
        finally:
            if user_token is not None:
                reset_current_user(user_token)
            reset_current_request_id(request_token)
            reset_request_context(context_token)

    return api_authentication_middleware


def build_security_headers_middleware():
    """Build browser security headers for API and documentation responses."""

    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()"
        )
        content_security_policy = (
            _OPENAPI_UI_CONTENT_SECURITY_POLICY
            if request.url.path in _OPENAPI_UI_PATHS
            else _API_CONTENT_SECURITY_POLICY
        )
        response.headers.setdefault("Content-Security-Policy", content_security_policy)
        forwarded = request.headers.get("X-Forwarded-Proto", "").split(",", 1)[0].strip()
        if forwarded == "https" or request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response

    return security_headers_middleware


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
    _log_api_request(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=exc.status_code,
        duration_ms=duration_ms,
        username="anonymous",
        ip=request_ip(request),
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
    from api.app.deps.services import get_audit_service

    audit = get_audit_service()
    if audit is not None:
        audit.record(
            "auth.session.rejected",
            "Request rejected because no valid authenticated session was present",
            severity="warning",
            category="security",
            outcome="denied",
            actor="anonymous",
            resource_type="api_route",
            resource_id=request.url.path,
            tags=["authentication", "session", "access-denied"],
            metadata={"status_code": exc.status_code, "request_id": request_id},
        )
    return response


def _log_api_request(
    *,
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    username: str,
    ip: str,
) -> None:
    """Log API requests, suppressing successful health/heartbeat chatter."""
    if status_code < 400 and path in _API_ACCESS_LOG_EXCLUDED_PATHS:
        return
    log_fn = (
        runtime_app.logger.error
        if status_code >= 500
        else (runtime_app.logger.warning if status_code >= 400 else runtime_app.logger.info)
    )
    log_fn(
        "api_request request_id=%s method=%s path=%s status=%s duration_ms=%.2f user=%s ip=%s",
        request_id,
        method,
        path,
        status_code,
        duration_ms,
        username,
        ip,
    )
