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

1. Systems transport targeted actions or classifications through structured Pydantic body definitions.
2. Required authorization policies validate standard execution permissions automatically derived through token extraction.
3. Successful validation leads to database updates and audit events.

## Engineering Standards

When adding or changing routes:

1. Pick a canonical OpenAPI tag from `api/interfaces/http/tags.py`.
2. Implement or extend strictly typed input schemas within `api/contracts/`.
3. Map endpoints natively through FastAPI router modules linking to authorization interceptors.
4. Decouple domain functions via constructor-injected implementations within standard service structures.
5. Expand targeted unit and integration suites located inside explicit `tests/api` suites before submission.
6. Run the relevant automated checks before submitting the change.
