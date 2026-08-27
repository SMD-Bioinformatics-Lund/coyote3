# API Routing Architecture and Workflows

## Route Layout

The backend exposes REST JSON endpoints under stable `/api/v1/...` URLs.
Swagger groups those endpoints by clinical or operational responsibility:
clinical samples, DNA findings, RNA findings, coverage, reporting,
knowledgebases, public catalog, admin operations, access control, and internal
ingest/maintenance.

Python router modules are physically grouped under
`api/interfaces/http/{clinical,admin,public,operations,knowledgebase}`. The
OpenAPI groups describe the product API and are intentionally kept stable even
if Python module names change. See [API Organization](api_organization.md) for
the full grouping model.

## Health Endpoint

Use the health endpoint to check that the API is up:

```bash
curl -f "http://${COYOTE3_HOST:-localhost}:${COYOTE3_PORT:-5815}/api/v1/health"
```

## Authentication

Protected API routes accept the Coyote3 API session token through either the
configured HTTP-only session cookie or `Authorization: Bearer <token>`. API-only
clients obtain that token by creating a session with
`POST /api/v1/auth/sessions` and reading the `Set-Cookie` response header.

See [API Authentication](authentication.md) for Swagger usage, cookie-jar
examples, bearer-token examples, and prefix-aware URLs.

## Common Request Patterns

### Read Flows

A typical read flow looks like this:

1. Resolve the sample through `samples.py`.
2. Query the relevant finding collections such as variants, CNVs, or fusions.
3. Build the response payload from those results and the matching configuration data.

### Write Flows

For write operations:

1. The client submits the action or classification through a typed request
   body.
2. The API authenticates the caller and checks the permission required by the
   endpoint.
3. The application service validates the operation and writes through the
   repository layer.
4. Clinically or operationally significant changes produce an audit event.

## Engineering Standards

When adding or changing routes:

1. Pick a canonical OpenAPI tag from `api/interfaces/http/tags.py`.
2. Implement or extend typed request and response schemas in `api/contracts/`.
3. Add the endpoint to the appropriate FastAPI router and apply its explicit
   authentication and permission dependencies.
4. Put use-case coordination in an application service and inject its
   repository dependencies through the runtime container.
5. Add focused unit tests and API contract tests under `tests/`.
6. Run the relevant automated checks before submitting the change.
