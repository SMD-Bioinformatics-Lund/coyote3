"""Branded documentation views for the canonical OpenAPI contract."""

from base64 import b64encode
from pathlib import Path

from fastapi import FastAPI, Request
from jinja2 import Environment, FileSystemLoader, select_autoescape
from starlette.responses import HTMLResponse

API_DESCRIPTION = """Coyote3 is a clinical genomics application for reviewing sample
findings, recording interpretations and preparing reports. The API provides access
to the sample data, annotations and assay configuration used in the application.

## Working with Coyote3

Start with a sample to review its small variants, copy-number changes, fusions,
biomarkers and coverage. Finding endpoints provide the annotations and knowledgebase
evidence used during review. Reporting endpoints let you preview the report before
creating a saved report with its finding snapshots.

For assay setup, use the administration endpoints for panels (ASP), analysis
configuration (ASPC) and gene lists (ISGL). Clinical reporting rules have their own
draft, review and publication workflow. The API applies the same permissions and
sample access checks as the Coyote3 interface.

## Authentication

| Client | Sign in with | When changing data |
| --- | --- | --- |
| Browser | Your Coyote3 session cookie | Send the session's `X-CSRF-Token`. |
| Script or integration | `Authorization: Bearer <session-token>` | No CSRF header is needed with a bearer token. |
| Public assay catalog | No sign-in required | Editing the catalog requires an account with the appropriate permissions. |

Sign in through the **Authentication** endpoints using a login provider enabled
by your center. Browser cookies and bearer tokens use the same session. The token
is opaque, not a JWT; treat it like a password.

## Sample ingestion

Check `GET /api/v1/health`, then submit the manifest and optional ZIP through
`POST /api/v1/internal/ingest/sample-bundle/upload` with `acknowledge=true`.
Use `X-Coyote-Ingest-Token` for an administrator-issued expiring pipeline token;
no user login is required. A terminal `status=ok` acknowledgement permits the
helper to rename the YAML to `.done`; `status=failed` permits `.failed`.
A timeout or missing acknowledgement is an unknown outcome: inspect the audit
before retrying. Async endpoints and task polling require a user session token.
The built-in Celery watcher reads mounted files directly and uses no HTTP token.

## Requests and errors

- Use the same application URL prefix as your Coyote3 installation.
- Check the operation's parameters for filters and pagination. A missing
  measurement is not the same as zero.
- `401`: sign in again. `403`: check your access and, for cookie-based changes,
  your CSRF token. `422`: correct the fields listed in the response.
- Errors include `status`, `error` and `details`. Include the response's
  `X-Request-ID` when asking your support team to investigate a failed request.

## Testing safely

The API explorer connects to this Coyote3 installation. Saving a comment, changing
a tier or creating a report here changes the same records you see in the application.
Use a non-production environment and synthetic samples when testing. Keep patient
data and session tokens out of shared examples, tickets and screenshots.
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
    logo = "data:image/png;base64," + b64encode((_TEMPLATES / "logo.png").read_bytes()).decode()

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
                version=app.version,
                environment=environment,
                nonproduction=environment not in {"production", "prod"},
                prefix=prefix,
                schema_url=f"{prefix}{app.openapi_url}",
                logo=logo,
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
