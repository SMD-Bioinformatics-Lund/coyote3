"""Consistent public errors without exposing infrastructure exception details."""

from http import HTTPStatus
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse

from api.infra.observability.redaction import redact_diagnostics

ERROR_GUIDANCE = {
    400: ("invalid_request", "Check the request values and try again."),
    401: ("authentication_required", "Sign in again to continue."),
    403: ("access_denied", "Contact an administrator if this access is expected."),
    404: ("not_found", "Refresh the page and check that the resource is still available."),
    405: ("method_not_allowed", "Use one of the methods listed in the Allow response header."),
    406: ("not_acceptable", "Request a response format supported by this endpoint."),
    408: ("request_timeout", "Check whether the operation completed before submitting it again."),
    409: ("conflict", "Reload the current record and review your changes before retrying."),
    410: ("gone", "This resource is no longer available. Refresh the resource list."),
    412: ("precondition_failed", "Reload the current version before retrying the change."),
    413: (
        "payload_too_large",
        "Reduce the upload size or ask an administrator about the upload limit.",
    ),
    415: (
        "unsupported_media_type",
        "Use the content type and file format documented for this endpoint.",
    ),
    422: ("validation_failed", "Correct the listed fields or conditions before retrying."),
    428: ("precondition_required", "Supply the version or precondition required by this endpoint."),
    429: ("rate_limited", "Wait before retrying. Follow Retry-After when provided."),
    500: (
        "internal_error",
        "Check the operation status before retrying. Contact support with the reference ID.",
    ),
    502: (
        "upstream_error",
        "A dependent service failed. Check the operation status before retrying.",
    ),
    503: (
        "service_unavailable",
        "The service is temporarily unavailable. Check the operation status before retrying.",
    ),
    504: (
        "upstream_timeout",
        "A dependent service timed out. Check whether the operation completed before retrying.",
    ),
}


def error_response(
    request: Request,
    status: int,
    error: str | None = None,
    *,
    details=None,
    category: str | None = None,
    hint: str | None = None,
    headers=None,
    module: str | None = None,
) -> JSONResponse:
    """Build an error with safe diagnostics, a stable status code and support reference.

    Args:
        request: Request carrying the correlation ID and authenticated context.
        status: HTTP error status; this helper does not select endpoint semantics.
        error: Safe client-facing explanation for 4xx responses.
        details: Field issues or business-rule detail for 4xx responses.
        category: Optional existing application category.
        hint: Optional recovery action for 4xx responses.
        headers: Protocol headers to preserve, such as Allow or Retry-After.
        module: Optional disabled application-module identifier.

    Returns:
        JSON response with no-store caching. Server errors never expose supplied details.
    """
    try:
        title = HTTPStatus(status).phrase
    except ValueError:
        title = "Request failed"
    code, default_hint = ERROR_GUIDANCE.get(
        status, ("request_failed", "Contact support with the reference ID.")
    )
    identity = getattr(request.state, "request_id", None) or str(uuid4())
    request.state.request_id = identity
    if status >= 500:
        error, details, hint = title, None, default_hint
    payload = redact_diagnostics(
        {
            "status": status,
            "error": error or title,
            "details": details,
            "category": category,
            "code": code,
            "hint": hint or default_hint,
            "request_id": identity,
        }
    )
    if module is not None:
        payload["module"] = module
    response_headers = dict(headers or {})
    if status == 401 and not any(key.lower() == "www-authenticate" for key in response_headers):
        response_headers["WWW-Authenticate"] = "Bearer"
    response_headers.update({"X-Request-ID": identity, "Cache-Control": "no-store"})
    return JSONResponse(status_code=status, content=payload, headers=response_headers)
