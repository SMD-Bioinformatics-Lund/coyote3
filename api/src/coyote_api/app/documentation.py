# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Branded documentation views for the canonical OpenAPI contract."""

from base64 import b64encode
from pathlib import Path

from fastapi import FastAPI, Request
from jinja2 import Environment, FileSystemLoader, select_autoescape
from starlette.responses import HTMLResponse

from coyote_api.config.paths import API_LOGO_PATH, APPLICATION_FAVICON_PATH
from coyote_api.version import APPLICATION_VERSION

API_DESCRIPTION = """Coyote4 API for sample review, findings, reports and administration.
Operations enforce the same permissions, assay and environment scopes as the application.
Application and server releases are versioned separately; HTTP routes use `/api/v1`.

## Authentication

| Client | Sign in with | When changing data |
| --- | --- | --- |
| Browser | Your Coyote4 session cookie | Send the session's `X-CSRF-Token`. |
| Script or integration | `Authorization: Bearer <session-token>` | No CSRF header is needed with a bearer token. |
| Ingestion automation | Managed service or personal bearer token | Only granted ingestion operations, assays, environments and token-owned jobs are accessible. |
| Public assay catalog | No sign-in required | Editing requires the corresponding permissions. |

Read `GET /api/v1/auth/providers`, then send `username`, `password` and an enabled
`provider` to `POST /api/v1/auth/sessions`. The opaque session token is returned
in `Set-Cookie`; the response body includes `csrf_token`. Verify access with
`GET /api/v1/auth/whoami`. Managed tokens cannot create or replace a user session.

## Sample ingestion

Coyote Relay supplies optional sample-ingestion routes. A server without Relay
omits those endpoints. Managed service and personal tokens can permit synchronous
submission, asynchronous submission and token-owned job polling. The separate
`X-Coyote-Ingest-Token` and `X-Coyote-Internal-Token` headers support synchronous
sample-bundle ingestion only. Check each operation's security and request fields.

## Responses

Errors include `status`, `error` and `details`. Check the operation's response schema
and include `X-Request-ID` when requesting support. Verify a write's outcome before
retrying after a timeout. The explorer uses this installation's data; use synthetic
samples in a non-production environment for integration testing.
"""

_TEMPLATES = Path(__file__).with_name("templates")
_ENVIRONMENT = Environment(
    loader=FileSystemLoader(_TEMPLATES), autoescape=select_autoescape(["html", "xml"])
)


def register_api_documentation(app: FastAPI, *, environment: str) -> None:
    """Register reference and explorer pages without adding schema operations.

    Args:
        app: Application receiving GET routes at /api/v1/redoc and /api/v1/docs.
        environment: Display label; values other than production/prod enable
            the nonproduction warning.

    Raises:
        OSError: The bundled logo cannot be read.
        jinja2.TemplateNotFound: The bundled reference template is unavailable.

    Notes:
        Loads the template and logo immediately; rendered pages disable caching.
    """
    template = _ENVIRONMENT.get_template("api_reference.html")
    logo = "data:image/svg+xml;base64," + b64encode(API_LOGO_PATH.read_bytes()).decode()
    favicon = (
        "data:image/x-icon;base64," + b64encode(APPLICATION_FAVICON_PATH.read_bytes()).decode()
    )

    def render(request: Request, view: str) -> HTMLResponse:
        """Render a documentation view with deployment-prefixed schema links.

        Args:
            request: Request whose ASGI root_path supplies the external prefix.
            view: Template mode, reference or explorer.

        Returns:
            HTML with application version, environment, logo, and no-store headers.
        """
        prefix = request.scope.get("root_path", "").rstrip("/")
        return HTMLResponse(
            template.render(
                view=view,
                application_version=APPLICATION_VERSION,
                server_version=app.version,
                openapi_version=app.openapi_version,
                environment=environment,
                nonproduction=environment not in {"production", "prod"},
                prefix=prefix,
                schema_url=f"{prefix}{app.openapi_url}",
                logo=logo,
                favicon=favicon,
                relay_installed="relay" in getattr(app.state, "api_extensions", ()),
            ),
            headers={"Cache-Control": "no-store"},
        )

    async def reference(request: Request) -> HTMLResponse:
        """Serve the API reference page without requiring authentication.

        Args:
            request: Incoming request supplying the deployment prefix.

        Returns:
            The rendered, non-cacheable reference page.
        """
        return render(request, "reference")

    async def explorer(request: Request) -> HTMLResponse:
        """Serve the API explorer page without requiring authentication.

        Args:
            request: Incoming request supplying the deployment prefix.

        Returns:
            The rendered, non-cacheable explorer page.
        """
        return render(request, "explorer")

    app.add_route("/api/v1/redoc", reference, methods=["GET"], include_in_schema=False)
    app.add_route("/api/v1/docs", explorer, methods=["GET"], include_in_schema=False)
