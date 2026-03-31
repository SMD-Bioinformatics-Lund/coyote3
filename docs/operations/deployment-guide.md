# Deployment Guide

## Scope

- Initial center setup: use [Center Deployment Guide](center-deployment-guide.md)
- Regular deployments and upgrades: use this guide

Canonical boundaries:

- The initial onboarding/bootstrap command sequence lives in
  [Initial Deployment Checklist](initial-deployment-checklist.md).
- This guide is intentionally for repeatable deployments after bootstrap is complete.

## Release metadata

```bash
export COYOTE3_VERSION="$(python coyote/__version__.py)"
export GIT_COMMIT="$(git rev-parse --short HEAD)"
export BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

## Deploy dev

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_dev_env \
  -f deploy/compose/docker-compose.dev.yml \
  up -d --build
```

## Deploy stage

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_stage_env \
  -f deploy/compose/docker-compose.stage.yml \
  up -d --build
```

Optional single-entry reverse proxy for stage:

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_stage_env \
  -f deploy/compose/docker-compose.stage.yml \
  --profile with-proxy \
  up -d --build
```

## Deploy prod

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  up -d --build
```

Optional single-entry reverse proxy for prod:

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  --profile with-proxy \
  up -d --build
```

Production guardrails:

- `.coyote3_env` is mandatory for production deployment.
- `COYOTE3_VERSION` is mandatory for production compose naming/tags (no `local` fallback).
- Production volume deletion guard: `./scripts/compose-with-version.sh -f deploy/compose/docker-compose.yml down -v`
  is blocked unless `COYOTE3_ALLOW_PROD_VOLUME_PRUNE=1` is explicitly set.

## Post-deploy checks

```bash
./scripts/compose-with-version.sh -f deploy/compose/docker-compose.yml ps
curl -f "http://${COYOTE3_HOST:-localhost}:${COYOTE3_API_PORT:-5818}/api/v1/health"
```

Docs/help checks (standalone docs container):

```bash
curl -f "${HELP_CENTER_URL:-http://localhost:5821/}"
curl -f "${HELP_CENTER_URL:-http://localhost:5821/}operations/deployment-guide/"
```

Cache/runtime checks:

```bash
# Verify Redis service is running (compose-managed stacks)
docker compose --env-file .coyote3_env -f deploy/compose/docker-compose.yml ps redis_coyote3

# Verify API worker count setting (from env)
grep -E '^API_WORKERS=' .coyote3_env

# Verify dashboard cache tuning values
grep -E '^DASHBOARD_SUMMARY_(CACHE_TTL_SECONDS|SNAPSHOT_MAX_AGE_SECONDS|SNAPSHOT_TTL_SECONDS)=' .coyote3_env
```

Notes:

- Redis image is pinned (`redis:7.4.3`) across compose stacks.
- API process concurrency is controlled by `API_WORKERS` in non-dev stacks.
- MkDocs is rebuilt at image build time and served by a dedicated docs container.
- Dashboard snapshot retention is enforced by Mongo TTL on `dashboard_metrics.updated_at`.
- Default container CPU/memory limits are configurable per environment via `*_CONTAINER_MEM_LIMIT` and `*_CONTAINER_CPU_LIMIT`.
- API and web request throttling are configurable with:
  - `API_RATE_LIMIT_ENABLED`, `API_RATE_LIMIT_REQUESTS_PER_MINUTE`, `API_RATE_LIMIT_WINDOW_SECONDS`
  - `WEB_RATE_LIMIT_ENABLED`, `WEB_RATE_LIMIT_REQUESTS_PER_MINUTE`, `WEB_RATE_LIMIT_WINDOW_SECONDS`

Mongo TTL verification (run in Mongo shell):

```javascript
db.dashboard_metrics.getIndexes().filter(i => i.name === "updated_at_ttl_1")
```

Expected:

- `expireAfterSeconds` equals `DASHBOARD_SUMMARY_SNAPSHOT_TTL_SECONDS`.

Quick checks:

```bash
PYTHONPATH=. python -m pytest -q -m api tests/api/routers/test_system_routes.py tests/api/routers/test_reports_routes.py
```

Internal metrics scrape check:

```bash
curl -f "http://${COYOTE3_HOST:-localhost}:${COYOTE3_API_PORT:-5818}/api/v1/internal/metrics" \
  -H "X-Internal-Token: ${INTERNAL_API_TOKEN}"
```

## Subsequent updates

Use this flow for regular upgrades after initial bootstrap is complete.

1. Pull latest code/tag and review changelog.
2. Update environment file only if new variables were introduced.
3. Validate secrets and compose:

```bash
scripts/validate_env_secrets.sh --env-file .coyote3_stage_env
docker compose --env-file .coyote3_stage_env -f deploy/compose/docker-compose.stage.yml config -q
```

4. Deploy updated containers:

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_stage_env \
  -f deploy/compose/docker-compose.stage.yml \
  up -d --build
```

5. Run post-deploy health + API quick checks.
6. If ingest contract/schema changed, run collection update/seed calls via:
   - `POST /api/v1/internal/ingest/collection`
   - `POST /api/v1/internal/ingest/collection/bulk`
   - Use authenticated admin user (session/bearer token) and `ignore_duplicates=true` for safe reruns.
7. For sample reprocessing, use `update_existing=true` on sample-bundle only with an authenticated user that has `edit_sample`.

## Rollback approach

1. bring down target stack
2. redeploy previous known-good image/tag
3. verify health and route quick checks
4. restore DB snapshot if data migration caused damage
