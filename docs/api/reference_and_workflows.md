# API Routing Architecture and Workflows

## Route Layout

The backend exposes REST JSON endpoints grouped by domain under `api/routers/`:

- `auth.py`: Authentication, token exchange, and password management.
- `samples.py`: Sample retrieval and update routes.
- `small_variants.py`: SNV and Indel-based read operations.
- `cnvs.py`: Copy Number Variant retrieval contexts.
- `translocations.py`: Broad structural translocation queries.
- `fusions.py`: Transcribed RNA fusion boundary endpoints.
- `biomarkers.py`: Genomic-level diagnostic indicator endpoints.
- `reports.py`: Report preview and save routes.
- `users.py`, `roles.py`, `permissions.py`: Administrative routes for access control.
- `dashboard.py`, `coverage.py`, `public.py`: Dashboard, coverage, and public-facing routes.
- `internal.py`: Internal service and ingest routes.

## Health Endpoint

Use the health endpoint to check that the API is up:

```bash
curl -f "http://${COYOTE3_HOST:-localhost}:${COYOTE3_API_PORT:-5818}/api/v1/health"
```

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
1. Implement or extend strictly typed input schemas within `api/contracts/`.
2. Map endpoints natively through FastAPI router modules linking to authorization interceptors.
3. Decouple domain functions via constructor-injected implementations within standard Service structures.
4. Expand targeted unit and integration suites located inside explicit `tests/api` suites before submission.
5. Run the relevant automated checks before submitting the change.
