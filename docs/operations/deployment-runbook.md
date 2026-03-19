# Deployment Runbook

## Scope

- First-time center bootstrap: use [Center Onboarding Pack](center-onboarding-pack.md)
- Day-2+ deployments and upgrades: use this runbook

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

## Deploy prod

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  up -d --build
```

## Post-deploy checks

```bash
./scripts/compose-with-version.sh -f deploy/compose/docker-compose.yml ps
curl -f "http://${COYOTE3_HOST:-localhost}:${COYOTE3_API_PORT:-5816}/api/v1/health"
```

Smoke tests:

```bash
PYTHONPATH=. python -m pytest -q -m api tests/api/routers/test_system_routes.py tests/api/routers/test_reports_routes.py
```

## Subsequent updates (day-2+)

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

5. Run post-deploy health + API smoke checks.
6. If ingest contract/schema changed, run collection update/seed calls via:
   - `POST /api/v1/internal/ingest/collection`
   - `POST /api/v1/internal/ingest/collection/bulk`
7. For sample reprocessing, use `update_existing=true` on sample-bundle only with an authenticated user that has `edit_sample`.

## Rollback approach

1. bring down target stack
2. redeploy previous known-good image/tag
3. verify health and route smoke tests
4. restore DB snapshot if data migration caused damage
