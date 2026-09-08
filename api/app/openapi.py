"""OpenAPI schema customization helpers."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from api.interfaces.http.tags import OPENAPI_TAG_GROUPS
from api.security.access import get_api_session_cookie_name, is_public_api_path

_PROTECTED_OPENAPI_EXACT = {
    "/api/v1/auth/session",
    "/api/v1/auth/whoami",
}


def apply_openapi_security_schema(app: FastAPI) -> dict:
    """Apply the standard authentication schema to OpenAPI output.

    Args:
        app: FastAPI application whose OpenAPI schema should be customized.

    Returns:
        The application OpenAPI schema with security schemes and auth responses
        applied to protected endpoints.
    """
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
        servers=app.servers,
    )
    schema["x-tagGroups"] = OPENAPI_TAG_GROUPS
    components = schema.setdefault("components", {})
    security_schemes = components.setdefault("securitySchemes", {})
    security_schemes["ApiSessionCookie"] = {
        "type": "apiKey",
        "in": "cookie",
        "name": get_api_session_cookie_name(),
        "description": "Browser-managed session cookie. Mutations require X-CSRF-Token.",
    }
    security_schemes["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "opaque",
        "description": "Opaque API session token. Access is limited by the user's permissions.",
    }

    for path, operations in schema.get("paths", {}).items():
        for method, operation in operations.items():
            if method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                continue
            if path.startswith("/api/v1/") and (
                not is_public_api_path(path) or path in _PROTECTED_OPENAPI_EXACT
            ):
                operation["security"] = [{"ApiSessionCookie": []}, {"BearerAuth": []}]
                responses = operation.setdefault("responses", {})
                responses.setdefault("401", {"description": "Unauthorized"})
                responses.setdefault("403", {"description": "Forbidden"})

    app.openapi_schema = schema
    return app.openapi_schema
