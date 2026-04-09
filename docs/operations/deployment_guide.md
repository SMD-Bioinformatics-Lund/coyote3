# Platform Deployment and Lifecycle Orchestration

This guide establishes the authoritative protocols for the deployment and longitudinal maintenance of the Coyote3 platform.

## Scope and Objectives
- **Standard Deployment**: Repeatable container orchestration and platform upgrades.
- **Initial Provisioning**: For first-time environment setup, refer to the [Center Deployment Guide](center_deployment_guide.md) and the [Initial Deployment Checklist](initial_deployment_checklist.md).

## Release Metadata Extraction
Maintainers must verify the release coordinates before initiating any deployment sequence:

```bash
# Capture platform versioning and build context
export COYOTE3_VERSION="$(python coyote/__version__.py)"
export GIT_COMMIT="$(git rev-parse --short HEAD)"
export BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

## Standard Deployment Sequences

### Production Environment Deployment
Production deployments require explicit environment commitment and enforced versioning.

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  up -d --build
```

### Staging and Development Deployment
Orchestration for non-production environments utilizes dedicated profile templates to ensure isolation.

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

## Post-Deployment Validation Protocols

Immediate verification of service health is mandatory after every orchestration change:

```bash
# Verify container operational status
./scripts/compose-with-version.sh -f deploy/compose/docker-compose.yml ps

# Confirm API health gateway availability
curl -f "http://${COYOTE3_HOST:-localhost}:${COYOTE3_API_PORT:-5818}/api/v1/health"

# Execute internal telemetry scrape
curl -f "http://${COYOTE3_HOST:-localhost}:${COYOTE3_API_PORT:-5818}/api/v1/internal/metrics" \
  -H "X-Internal-Token: ${INTERNAL_API_TOKEN}"
```

## Operational Safety Guardrails

- **Environment Identity**: Deployment to production is strictly blocked without a valid `.coyote3_env` specification.
- **Immutable Versioning**: Use of floating `local` tags is prohibited in production; `COYOTE3_VERSION` is enforced for all image resolutions.
- **Durable Volume Protection**: Destructive volume operations (`down -v`) are systematically blocked in production clusters unless `COYOTE3_ALLOW_PROD_VOLUME_PRUNE=1` is explicitly defined.
- **Cache Persistence**: Redis instances are pinned to specific versioned images (`7.4.3`) to prevent state corruption during floating tag updates.

## Upgrade and Patch Orchestration

Maintenance and upgrades follow a structured four-phase protocol:

1. **Verification**: Validate environment schema and compose integrity using `validate_env_secrets.sh`.
2. **Execution**: Perform the rolling update of containerized services using the standardized `compose-with-version.sh` orchestration.
3. **Synchronization**: If an ingestion contract modification has occurred, execute collection synchronization via the `/api/v1/internal/ingest` endpoints.
4. **Validation**: Execute the established health and functional verification suite.

## Remediation and Rollback Strategy

In the event of a catastrophic operational failure:
1. Immediately suspend the target orchestration stack.
2. Revert to the previous known-good image version.
3. If data corruption has occurred during migration, initiate the restoration of the most recent database snapshot.
4. Confirm operational recovery through the secondary verification suite.
