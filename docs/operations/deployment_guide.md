# Deployment Guide

## Trusted proxy configuration

Set `FORWARDED_ALLOW_IPS` to the ingress proxy's IP or a dedicated trusted proxy
network CIDR. The loopback-only default does not trust arbitrary container clients.
Never use `*` on a shared network. The API uses the ASGI-resolved client address for
audit and rate limiting; it does not parse untrusted forwarded headers itself.

The supplied Nginx gateway replaces `X-Forwarded-For` with its peer address. If an
external center proxy is in front, this is the center proxy's address unless the
center configures trusted real-IP handling at that edge. Set
`COYOTE3_NGINX_PUBLIC_SCHEME=https` only when the public entry point enforces TLS;
the gateway does not trust an incoming `X-Forwarded-Proto` value. Restrict direct
API and gateway exposure according to this trust boundary.

This guide is the deployment command and runtime reference for an installed
Coyote3 environment. It covers normal release deployment and maintenance.

For the complete step-by-step production procedure, begin with
[Production deployment](../start_here/production_deployment.md). This page is
the deployment command and architecture reference.

> **Important: migrating existing Coyote v3 data**
>
> A centre moving an existing Coyote v3 database must follow the dedicated
> [v3 data migration procedure](upgrade_from_v3.md). Do not use the standard
> deployment sequence as a substitute for that procedure.
>

## Scope

- **Standard deployment**: Repeatable container-based release deployment.
- **Initial Provisioning**: For first-time environment setup, refer to the [Center Deployment Guide](center_deployment_guide.md) and the [Initial Deployment Checklist](initial_deployment_checklist.md).

## Release Metadata

The application version is defined in `api/version.py`. The
`scripts/compose-with-version.sh` wrapper reads that file and exports transient
Compose variables for image names and build metadata. Do not store
`COYOTE3_VERSION`, `COYOTE3_IMAGE_TAG`, `GIT_COMMIT`, or `BUILD_TIME` in copied env files.
The wrapper reads `ENV_NAME` from the selected env file (an exported shell value
takes precedence). Development/dev, testing/test, staging/stage, and production/prod
select image suffixes `-dev`, `-test`, and `-stage`; production uses the plain
release version without a suffix. API documentation, UI, and docs version labels
follow the same rule.
Both modern and legacy Compose use these tags without an extra image-selection file.
Use literal values for `ENV_NAME`. Base files serve compiled images; dev overlays
are only for live editing.

Logging defaults to `INFO` for production/prod and `DEBUG` elsewhere. `LOG_LEVEL`
in the env file overrides that default. `CELERY_LOG_LEVEL` defaults to the effective
`LOG_LEVEL` and can independently override worker and beat logging.

API, worker, and beat container output uses readable UTC timestamps, severity,
service and logger names, messages, and request identifiers where available.
Exceptions retain their multiline tracebacks. Daily log files retain structured
JSON for diagnostics and error monitoring. Routine MongoDB driver messages below
WARNING and successful Uvicorn health probes are suppressed; application DEBUG
messages and failed health requests remain visible.

## Deployment Commands

These commands use the independently configured MongoDB service endpoints.
Initialize self-hosted databases before starting the application; managed
services require no MongoDB Compose profile. See
[MongoDB service topology](../architecture/mongodb_topology.md).

## MongoDB baseline

The modern and legacy Compose-managed services use the pinned `mongo:7.0.41`
image. Modern Docker uses its default seccomp policy; the legacy definitions
contain the older engine's scoped compatibility exceptions. The archive utilities
separately use `mongo:8.2` tools images.

MongoDB is a stateful clinical dependency. Use a pinned release line rather
than a floating image tag, apply the vendor's documented upgrade path for an
existing deployment, and validate a backup restore before changing the server
major version.

## Redis authentication and storage

Compose requires `REDIS_PASSWORD` for Redis, the cache, workers, and beat.
Generate it with `openssl rand -hex 32` and store it in the untracked deployment
environment file. Use at least 64 hexadecimal characters for URL-safe credentials.
Recreate Redis and API/worker/beat containers together when rotating credentials.
Do not remove the Redis volume or flush broker databases. Redis has no published
host port and must remain private to the application network.

Cache values use MongoDB Extended JSON, never Python pickle. Older or unreadable
values are cache misses and are recomputed. Cache entries are not durable clinical
records. No legacy deserializer is retained.

## Center storage mounts

The base and development stacks mount no clinical input storage. There are no
assumed `/access`, `/media`, or `/fs1` directories, and the host data root is not
automatically mirrored at the same path inside a container. Only application-owned
data (`/data`) and logs (`/app/logs`) have standard container locations; their host
roots remain configurable.

Each center defines its own number of input mounts, host locations, container
locations, and access modes in a private Compose override:

```bash
cp deploy/compose/docker-compose.storage.example.yml .coyote3_storage.yml
```

Copy the template once and edit only `.coyote3_storage.yml` for your deployment.
This filename is already in `.gitignore`: local mount changes do not appear in
Git status, and pulling repository updates leaves the file untouched. Keep the
tracked Compose files and example templates unchanged. New template changes can
be reviewed and applied to your local override when needed.

For legacy Docker Compose, copy `deploy/legacy/docker-compose.storage.example.yml`
instead; its mount syntax supports Compose 1.29.2.

For the example's single mount, add `CENTER_INPUT_SOURCE` (an absolute host
directory) and `CENTER_INPUT_TARGET` (an absolute container directory) to your
untracked environment file. Edit the override to add any additional mounts or use
center-specific environment variable names. These two example variables are not
application configuration keys or a limit on storage locations.

To preserve paths exactly, use the same absolute path for each mount's `source`
and `target`. Add one YAML list entry per directory; Compose does not expand a
comma-separated environment variable into multiple mounts. Source directories
must already be accessible on the deployment host.

Pass the override last on every deployment command:

```bash
./scripts/compose-with-version.sh --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml -f .coyote3_storage.yml up -d --build
```

For development, include `-f deploy/compose/docker-compose.dev.yml` before the
storage override and use the development environment file. Compose merges mounts
by container target. Do not shadow `/app`, `/data`, or `/app/logs` unintentionally.
Include the same override for config validation, recreation, and maintenance.

For example, a legacy remote-development deployment using compiled images uses:

```bash
./scripts/compose-with-version.sh -p coyote3-dev --env-file .coyote3_dev_env \
  -f deploy/legacy/docker-compose.yml \
  -f .coyote3_storage.yml up -d
```

The wrapper selects image tags from `ENV_NAME`. If application code or startup commands changed,
build `api` with the same file list before recreating API, worker, and beat;
all three use the shared API image. Mount-only changes do not require rebuilding.

Keep any other overlays used by your deployment before `.coyote3_storage.yml`.

API, worker, and beat need consistent paths for shared inputs. Paths in ingest
manifests and file-reading configuration must refer to the chosen **container**
locations, not inaccessible host paths. Existing deployments must explicitly add
their previous input mounts before recreating containers. IGV workstation paths
are independent and remain configured through `IGV_DATA_ROOT` and ASP settings.

The example uses read-only mounts and refuses to create missing host directories.
Prepare storage and container UID/GID permissions before deployment. Use response
acknowledgements for read-only ingestion; file-based acknowledgements require
explicit write access to their directory. NFS/SMB storage can be mounted by the host
or supplied through center-owned Compose volumes. Do not commit operational paths,
mount credentials, or the private override.

## Optional load generator

The self-hosted Locust overlay, `deploy/compose/docker-compose.loadtest.yml`, is
standalone and opt-in under the `loadtest` profile. It runs only the generator; it does not start
or provision Coyote3. Deploy an isolated synthetic application first and target its
Nginx entrypoint with the configured prefix, not the API container port. The Locust
UI is bound to localhost on port `8089`, and local credentials/configuration JSON
are mounted read-only from `.coyote3_load`; only `load-results` is writable persistent
output. It joins the pre-created external `COYOTE3_LOAD_NETWORK` (default
`coyote3-loadtest-net`). Supply generator configuration, not the application's database
environment file. Keep the overlay out of normal production startup.
Use the [load-testing guide](../testing/load_testing.md) for the exact setup and
execution commands, workload selection, and result handling.

## Environment warnings

Set `ENV_NAME` consistently for the API, frontend and documentation builds. Compose
passes it to all three. Non-production deployments display a warning in the login
page, application header, Swagger UI, ReDoc and the deployed documentation pages.
`production` and `prod` suppress the warning. The label is independent of database
names and storage paths; never use a sample's analysis environment for this banner.

Frontend and documentation labels are compiled into their assets. Rebuild them
when changing `ENV_NAME`; for the development stack's mounted `site/` directory run
`ENV_NAME=development .venv/bin/python -m mkdocs build --strict`. Standalone public
documentation builds without `ENV_NAME` have no deployment label. Direct Vite
development defaults to `development`.

## Multiple input directories

An override can contain any number of mounts. For example, a center using `/fs1`
and `/access` can replace the example's mount list with:

```yaml
x-center-inputs: &center-inputs
  - type: bind
    source: ${CENTER_FS1_SOURCE:?Set the host input directory}
    target: /fs1
    read_only: true
    bind:
      create_host_path: false
  - type: bind
    source: ${CENTER_ACCESS_SOURCE:?Set the host input directory}
    target: /access
    read_only: true
    bind:
      create_host_path: false

services:
  api:
    volumes: *center-inputs
  worker:
    volumes: *center-inputs
  beat:
    volumes: *center-inputs
```

Set the two source variables in the private environment file. `/data` is already
mounted writable from `COYOTE3_DATA_HOST_ROOT`; setting that variable to `/data`
mounts the host `/data` there. Do not replace it with a read-only input mount:
ingest staging and application output need write access. To expose a separate
read-only input tree from host `/data`, mount that tree at another container target
such as `/inputs/data`, then use that target in manifests. These example paths are
not required center locations. Validate the merged stack with `docker compose`
using the same `--env-file` and `-f` arguments followed by `config --quiet`.

## Frontend builds

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
`IGV_URI` and `IGV_DATA_ROOT` are public Vite build inputs. Changing one requires a new frontend
image because it changes the generated browser bundle. Do not place secrets in
these values.

### Production deployment

Production deployments require the production environment file and explicit versioning.
The network named by `COYOTE3_APP_NETWORK` must exist before any application
environment is started. The following `/28` example reserves 16 addresses and
provides approximately 13 assignable container addresses after Docker reserves
the network, gateway, and broadcast addresses. This covers the seven application
services and leaves room for limited worker or API scaling:

```bash
docker network create \
  --driver bridge \
  --subnet 172.29.110.0/28 \
  --ip-range 172.29.110.0/28 \
  --gateway 172.29.110.1 \
  coyote3-prod-app-net
```

Choose a private subnet that does not overlap the host, VPN, center, Kubernetes,
or existing Docker networks. The CIDR controls the allocation pool; services
still communicate by Compose DNS names rather than fixed container IPs.

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  up -d --build
```

### Staging and development

All environments use `docker-compose.yml` as the service contract. Development,
staging, and test files are overlays that change only the behavior required by
that environment. Always provide the base file first and the overlay second.
The environment filename is supplied with `--env-file`; Compose files do not
contain a local filename and therefore work with any operator-selected name.
Create each environment's configured network once before its first deployment,
for example `coyote3-stage-app-net` or `coyote3-dev-app-net`.

Example non-overlapping pools for environments hosted on the same machine are:

| Environment | Network | Example subnet | Gateway |
| --- | --- | --- | --- |
| Production | `coyote3-prod-app-net` | `172.29.110.0/28` | `172.29.110.1` |
| Staging | `coyote3-stage-app-net` | `172.29.110.16/28` | `172.29.110.17` |
| Development | `coyote3-dev-app-net` | `172.29.110.32/28` | `172.29.110.33` |
| Testing | `coyote3-test-app-net` | `172.29.110.48/28` | `172.29.110.49` |

Create each required pool once. These commands may be run on a host that keeps
all four environments isolated:

```bash
docker network create --driver bridge --subnet 172.29.110.0/28 \
  --ip-range 172.29.110.0/28 --gateway 172.29.110.1 coyote3-prod-app-net
docker network create --driver bridge --subnet 172.29.110.16/28 \
  --ip-range 172.29.110.16/28 --gateway 172.29.110.17 coyote3-stage-app-net
docker network create --driver bridge --subnet 172.29.110.32/28 \
  --ip-range 172.29.110.32/28 --gateway 172.29.110.33 coyote3-dev-app-net
docker network create --driver bridge --subnet 172.29.110.48/28 \
  --ip-range 172.29.110.48/28 --gateway 172.29.110.49 coyote3-test-app-net
```

Set `COYOTE3_APP_NETWORK` in each environment file to the corresponding name.
Do not assign static container IPs; Compose DNS names such as `api`, `worker`,
`redis`, and `frontend` are the stable service addresses.

```bash
# Staging deployment
./scripts/compose-with-version.sh \
  --env-file .coyote3_stage_env \
  -f deploy/compose/docker-compose.yml -f deploy/compose/docker-compose.stage.yml \
  up -d --build

# Development deployment
./scripts/compose-with-version.sh \
  --env-file .coyote3_dev_env \
  -f deploy/compose/docker-compose.yml -f deploy/compose/docker-compose.dev.yml \
  up -d --build
```

The CLI environment file supplies values used while Compose renders the model.
The base file explicitly forwards application settings through each service's
`environment` mapping, so the API, worker, and scheduler receive the same
validated values without mounting or naming the host env file inside a
container.

Service keys are stable in every environment: `frontend`, `docs`, `api`,
`worker`, `beat`, `redis`, and `proxy`. Compose project names identify the
environment. For example, the development overlay produces uniform names such
as `coyote3_dev-api-1` and `coyote3_dev-redis-1`. Avoid explicit
`container_name` declarations: Compose-managed names prevent collisions and
retain support for service scaling.

## Post-deployment checks

Check service health after each deployment:

```bash
set -a
. ./.coyote3_env
set +a

APP_URL="${PUBLIC_BASE_URL%/}${SCRIPT_NAME}"

# Check container status
./scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  ps

# Check API health
curl -f "$APP_URL/api/v1/health"

# Check protected internal metrics through the deployment prefix
curl -f "$APP_URL/api/v1/internal/metrics" \
  -H "X-Internal-Token: ${INTERNAL_API_TOKEN}"
```

## Safety guardrails

- **Environment Identity**: Production deployment is blocked without a valid `.coyote3_env`.
- **Immutable Versioning**: Use of floating `local` tags is prohibited in production; the compose wrapper injects the version from `api/version.py` for all image resolutions.
- **Durable Data Protection**: The deployment wrapper rejects destructive volume operations (`down -v`) in every environment. Normal teardown stops and removes containers only; it never removes Compose volumes or the host-mounted MongoDB data directory.
- **Queue persistence**: Redis uses the `redis-data` volume, AOF with `appendfsync always`, and `noeviction`. Cache, broker, and task results use Redis databases 0, 1, and 2 respectively. MongoDB ingest receipts provide delivery recovery independently of task-result retention. See [transaction and queue deployment requirements](../architecture/transactions_and_ingest_recovery.md#deployment-and-rollout).

## Upgrades

For upgrades:

1. **Verification**: Validate environment schema and compose integrity using `validate_env_secrets.sh`.
2. **Execution**: Update the containerized services with `compose-with-version.sh`.
3. **Maintenance**: Run only the RBAC, index, or stored-data procedure named by the release notes.
4. **Validation**: Execute the established health and functional verification suite.

## Rollback Strategy

If a deployment fails badly:

1. Immediately suspend the target orchestration stack.
2. Revert to the previous known-good image version.
3. If data corruption has occurred during migration, initiate the restoration of the most recent database snapshot.
4. Confirm operational recovery through the secondary verification suite.
