# Troubleshooting Guide

Developer-focused troubleshooting for common local and deployment issues.

## Dashboard slow response

Symptoms:

- dashboard page takes several seconds to load
- API logs show repeated expensive aggregation queries

Checks:

1. Confirm the Celery worker and beat scheduler are running.
2. Confirm Redis is reachable from the API and worker containers.
3. Check that writes invalidate the metric associated with the changed collection.
4. Confirm `api.tasks.maintenance.refresh_dashboard_metrics` is running on schedule.
5. Request the slow `/api/v1/dashboard/metrics/...` endpoint directly to identify the affected aggregate.
6. Check the MongoDB indexes used by that metric's source repositories.

Quick probe:

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_dev_env \
  -f deploy/compose/docker-compose.yml \
  -f deploy/compose/docker-compose.dev.yml \
  logs api worker beat 2>&1 | rg "dashboard|metric|refresh"
```

Dashboard payloads are independent Redis cache entries. There is no MongoDB
dashboard snapshot document to repair. A stale entry remains readable while a
worker replaces it; a missing entry is calculated by the first request.

## Login failure for mixed auth users

Symptoms:

- valid LDAP user cannot login
- local user hits LDAP path by mistake
- UI says `Authentication backend unavailable` even when credentials look correct

Checks:

1. Confirm user doc exists in DB.
2. Confirm `auth_type` is a provider list, for example `["ldap"]`, `["local"]`, or `["local", "ldap"]`.
3. Verify LDAP connectivity for LDAP users.
4. Verify password hash and local auth flow for local users.
5. Verify local-user email/username shape:
   - accepted: `local@domain` including private domains like `.local`
   - rejected: missing `@`, empty local part, or empty domain part
6. If this error appears, check API logs for auth session serialization/validation errors.

## Mail not configured

Expected behavior:

- app should warn and continue running
- user invite/reset mail operations should fail gracefully with actionable warning

Checks:

1. Validate SMTP env vars for active environment.
2. Confirm SMTP host/port connectivity from container.
3. Confirm `SMTP_FROM_EMAIL` is valid for the relay policy.

## Docs URL mismatch

Symptoms:

- Help links open wrong URL

Checks:

1. Verify `PUBLIC_BASE_URL` and `SCRIPT_NAME` in the active env file.
2. Open `${PUBLIC_BASE_URL}${SCRIPT_NAME}/docs-site/` and verify the docs container is healthy.
3. Rebuild docs image after nav/content updates.

## Use the operations guide when needed

For production incidents and operations-level actions, also review [Operations / Troubleshooting](../operations/troubleshooting.md).
