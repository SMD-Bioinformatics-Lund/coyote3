# Deployment Guide

This guide covers deployment and routine upgrade work for Coyote3.

## Scope
- **Standard Deployment**: Repeatable container-based deployment and upgrades.
- **Initial Provisioning**: For first-time environment setup, refer to the [Center Deployment Guide](center_deployment_guide.md) and the [Initial Deployment Checklist](initial_deployment_checklist.md).

## Release Metadata

The application version is defined in `api/version.py`. The
`scripts/compose-with-version.sh` wrapper reads that file and exports transient
Compose variables for image names and build metadata. Do not store
`COYOTE3_VERSION`, `GIT_COMMIT`, or `BUILD_TIME` in copied env files.

## Deployment Commands

## Frontend Asset Lifecycle

The frontend uses Vite with the Tailwind Vite plugin. Tailwind classes and CSS
are compiled as part of the Vite bundle; there is no separate Tailwind process.

- **Development**: `npm run dev` starts Vite's file watcher. Saving a React,
  CSS, or Tailwind theme file recompiles the affected assets in memory and
  updates the browser through hot module replacement. The development
  container remains running.
- **Production, staging, and UI test deployments**: `docker compose build`
  builds `coyote3-frontend` from `docker/Dockerfile.frontend`. That image
  contains the immutable `frontend/dist` output and serves it through Nginx.
  Starting or restarting the container never runs `npm install` or
  `npm run build`.

`SCRIPT_NAME`, `ORGANIZATION_NAME`, `LOCAL_TIME_ZONE`, `GENS_URI`, and
`IGV_URI` are public Vite build inputs. Changing one requires a new frontend
image because it changes the generated browser bundle. Do not place secrets in
these values.

### Production Deployment
Production deployments require the production environment file and explicit versioning.

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  up -d --build
```

### Staging And Development
Non-production environments use their own compose files and env files.

```bash
# Staging deployment
./scripts/compose-with-version.sh \
  --env-file .coyote3_stage_env \
  -f deploy/compose/docker-compose.stage.yml \
  up -d --build

# Development deployment
./scripts/compose-with-version.sh \
  --env-file .coyote3_dev_env \
  -f deploy/compose/docker-compose.dev.yml \
  up -d --build
```

## Post-Deployment Checks

Check service health after each deployment:

```bash
# Check container status
./scripts/compose-with-version.sh -f deploy/compose/docker-compose.yml ps

# Check API health
curl -f "http://${COYOTE3_HOST:-localhost}:${COYOTE3_PORT:-5815}/api/v1/health"

# Check internal metrics
curl -f "http://${COYOTE3_HOST:-localhost}:${COYOTE3_PORT:-5815}/api/v1/internal/metrics" \
  -H "X-Internal-Token: ${INTERNAL_API_TOKEN}"
```

## Safety Guardrails

- **Environment Identity**: Production deployment is blocked without a valid `.coyote3_env`.
- **Immutable Versioning**: Use of floating `local` tags is prohibited in production; the compose wrapper injects the version from `api/version.py` for all image resolutions.
- **Durable Volume Protection**: Destructive volume operations (`down -v`) are blocked in production unless `COYOTE3_ALLOW_PROD_VOLUME_PRUNE=1` is set.
- **Cache Persistence**: Redis instances are pinned to specific versioned images (`7.4.3`) to prevent state corruption during floating tag updates.

## Upgrades

For upgrades:

1. **Verification**: Validate environment schema and compose integrity using `validate_env_secrets.sh`.
2. **Execution**: Update the containerized services with `compose-with-version.sh`.
3. **Synchronization**: If an ingestion contract modification has occurred, execute collection synchronization via the `/api/v1/internal/ingest` endpoints.
4. **Validation**: Execute the established health and functional verification suite.

## Rollback Strategy

If a deployment fails badly:
1. Immediately suspend the target orchestration stack.
2. Revert to the previous known-good image version.
3. If data corruption has occurred during migration, initiate the restoration of the most recent database snapshot.
4. Confirm operational recovery through the secondary verification suite.
