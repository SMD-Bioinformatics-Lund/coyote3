"""Branded documentation views for the canonical OpenAPI contract."""

from base64 import b64encode
from pathlib import Path

from fastapi import FastAPI, Request
from jinja2 import Environment, FileSystemLoader, select_autoescape
from starlette.responses import HTMLResponse

PRODUCT_OVERVIEW = (
    "Coyote3 is a clinical genomics application developed by the bioinformatics team at "
    "the Section for Molecular Diagnostics (SMD), Lund, within Region Sk\u00e5ne's "
    "clinical laboratory service.",
    "Clinical geneticists, bioinformaticians and laboratory staff use Coyote3 to ingest "
    "DNA and RNA samples, review genomic findings, record classifications and comments, "
    "and prepare reports. Assay configuration determines which analyses and filters are "
    "available. Saved reports retain finding snapshots and the reporting context used "
    "to produce them.",
)

API_DESCRIPTION = (
    "\n\n".join(PRODUCT_OVERVIEW)
    + """

## API scope

The API serves the Coyote3 interface and integrations with laboratory pipelines.
Sample and finding endpoints provide access to small variants, copy-number changes,
fusions, DNA translocations, HRD, MSI, TMB and coverage, subject to the sample's assay
configuration. Review operations record classifications and comments. Reporting
operations generate previews and save reports with their finding snapshots.

Administration endpoints manage assays, assay configurations (ASPC), in-silico gene
lists (ISGL), finding query rules, reporting rules and the public assay catalog. Clinical reporting rules
follow a draft, independent review and publication workflow. API access is subject
to the same permissions and assay, environment and sample-access restrictions as
the application; using an integration does not bypass those checks.

## Finding query rules

Published query policies resolve from application defaults through group, assay
and subpanel scopes. Application defaults use analysis-specific evidence and saved
sample filters; group-specific exceptions are stored in database rule sets.
Drafts do not affect clinical retrieval. Preview the effective policy and test a
saved version against a sample before approval and publication. Query-rule
operations require their corresponding authoring, review, publication or testing
permissions.

Only supported integration and administration operations appear in this reference.
Private demonstration-installation endpoints are excluded from the OpenAPI schema.

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

DNA manifests declare a single `biomarkers` file. Ingestion separates its HRD, MSI
and TMB measurements into the corresponding analyses. Declare alignment resources
with `case_bam`, `case_bai`, `control_bam` and `control_bai` when they are available.
DNA translocations use SnpEff-annotated VCF input; RNA fusions use their separate
caller-evidence input format.

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
)

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
                product_overview=PRODUCT_OVERVIEW,
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
