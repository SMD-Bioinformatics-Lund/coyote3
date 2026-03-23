# Troubleshooting Guide

Developer-focused troubleshooting for common local and deployment issues.

## Dashboard slow response

Symptoms:

- dashboard page takes several seconds to load
- API logs show repeated expensive aggregation queries

Checks:

1. Verify Redis is reachable from API container.
2. Confirm dashboard cache keys are being read/written.
3. Confirm invalidation hooks run after data mutations.
4. Check Mongo indexes used by dashboard aggregations.

Quick probe:

```bash
docker logs coyote3_api_${COYOTE3_VERSION:-local} 2>&1 | rg "dashboard|cache|redis"
```

## Login failure for mixed auth users

Symptoms:

- valid LDAP user cannot login
- local user hits LDAP path by mistake
- UI says `Authentication backend unavailable` even when credentials look correct

Checks:

1. Confirm user doc exists in DB.
2. Confirm `login_type` value is correct (`coyote3` or `ldap`).
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

1. Verify `HELP_CENTER_URL` env value.
2. Verify docs container is healthy and published on configured port.
3. Rebuild docs image after nav/content updates.

## Use the operations guide when needed

For production incidents and runbook-level actions, also review [Operations / Troubleshooting](../operations/troubleshooting.md).
