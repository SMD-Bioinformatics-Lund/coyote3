# Deployment Guide

This guide covers deployment and routine upgrade work for Coyote3.

## Scope
- **Standard Deployment**: Repeatable container-based deployment and upgrades.
- **Initial Provisioning**: For first-time environment setup, refer to the [Center Deployment Guide](center_deployment_guide.md) and the [Initial Deployment Checklist](initial_deployment_checklist.md).

## Release Metadata
Check the release metadata before starting a deployment:

```bash
# Capture version and build context
export COYOTE3_VERSION="$(python coyote/__version__.py)"
export GIT_COMMIT="$(git rev-parse --short HEAD)"
export BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

## Deployment Commands

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
curl -f "http://${COYOTE3_HOST:-localhost}:${COYOTE3_API_PORT:-5818}/api/v1/health"

# Check internal metrics
curl -f "http://${COYOTE3_HOST:-localhost}:${COYOTE3_API_PORT:-5818}/api/v1/internal/metrics" \
  -H "X-Internal-Token: ${INTERNAL_API_TOKEN}"
```

## Safety Guardrails

- **Environment Identity**: Production deployment is blocked without a valid `.coyote3_env`.
- **Immutable Versioning**: Use of floating `local` tags is prohibited in production; `COYOTE3_VERSION` is enforced for all image resolutions.
- **Durable Volume Protection**: Destructive volume operations (`down -v`) are blocked in production unless `COYOTE3_ALLOW_PROD_VOLUME_PRUNE=1` is set.
- **Cache Persistence**: Redis instances are pinned to specific versioned images (`7.4.3`) to prevent state corruption during floating tag updates.

## Upgrades And Patches

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
