# Deployment Runbook

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

## Rollback approach

1. bring down target stack
2. redeploy previous known-good image/tag
3. verify health and route smoke tests
4. restore DB snapshot if data migration caused damage
