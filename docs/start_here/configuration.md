# Configuration And Environments

This document describes how Coyote3 configuration is organized across environments.

## Environment Files

Application behavior is controlled by environment files (`.coyote3_env*`). The single template is `deploy/env/example.env`:

- **Production**: copy `deploy/env/example.env` to `.coyote3_env`.
- **Staging**: copy `deploy/env/example.env` to `.coyote3_stage_env`.
- **Development**: copy `deploy/env/example.env` to `.coyote3_dev_env`.
- **Continuous Validation**: copy `deploy/env/example.env` to `.coyote3_test_env`.

After copying, update `ENV_NAME`, `DEVELOPMENT`, `TESTING`, `COYOTE3_DB`, `MONGO_URI`, HTTP ports, data paths, secrets, and integration URLs for the target environment.

## Default Port Layout

Each environment exposes one HTTP entrypoint through nginx. Web UI, API, and
docs remain on internal container ports and are routed through the proxy:

| Domain Layer | Production | Staging | Development | Test/CI |
| --- | --- | --- | --- | --- |
| **HTTP proxy** | `5815` | `8804` | `6801` | `6811` |

Internal proxy targets:

- `/` -> Web UI
- `/api/` -> FastAPI
- `/docs-site/` -> documentation site
- `/public/` -> unauthenticated public catalog and reference UI

When `SCRIPT_NAME` is set, user-facing URLs include that prefix. For example,
with `SCRIPT_NAME=/coyote3_dev` and `COYOTE3_DEV_PORT=6801`, the browser URLs are:

- `http://localhost:6801/coyote3_dev/` -> Web UI
- `http://localhost:6801/coyote3_dev/public/catalog` -> public catalog
- `http://localhost:6801/coyote3_dev/api/v1/docs` -> Swagger UI
- `http://localhost:6801/coyote3_dev/docs-site/` -> documentation site

The unprefixed `/api/` and `/docs-site/` paths remain internal proxy targets for
container health checks and reverse proxies that remove the public mount prefix
before forwarding.

Redis and compose-managed MongoDB are internal-only. When the optional
`with-mongo` profile is used, the MongoDB container is reachable by Coyote3
services on the Docker network, not through a host port. For local development
against a host MongoDB, point `MONGO_URI` at the host service instead.

!!! warning "Bounded service restart policy"

    Coyote3 app containers use bounded `on-failure:5` restart policies. A broken
    frontend build, API import error, or worker crash should stop after a small
    number of attempts instead of creating continuous Docker network interface
    churn. Use `docker compose logs <service>` and fix the failure before
    starting the service again.

### Customizing Ports

The HTTP proxy host port is configurable via environment variables. Override it
in the copied `.coyote3_*_env` file or export it before running `docker compose`:

| Environment Variable | Default | Service |
| --- | --- | --- |
| `COYOTE3_PORT` | `5815` | Production HTTP proxy |
| `COYOTE3_STAGE_PORT` | `8804` | Staging HTTP proxy |
| `COYOTE3_DEV_PORT` | `6801` | Development HTTP proxy |
| `COYOTE3_TEST_PORT` | `6811` | Test HTTP proxy |

Example — run the production HTTP proxy on port 9000 instead of 5815:

```bash
export COYOTE3_PORT=9000
docker compose -f deploy/compose/docker-compose.yml up -d
```

> **Note**: Internal container ports (3000 or 8000 for web, 8001 for API, 6379 for Redis, 27017 for MongoDB) are fixed and should not be changed.

### Data Mounts

Runtime data paths are mounted through a data-root pair, not hardcoded in the
Compose files:

| Environment Variable | Default | Purpose |
| --- | --- | --- |
| `COYOTE3_DATA_HOST_ROOT` | `/data` | Host-side data root mounted into app containers |
| `COYOTE3_DATA_CONTAINER_ROOT` | `/data` | Container-side data root |

Paths such as `REPORTS_BASE_PATH`, `CELERY_INGEST_STAGING_DIR`, and
`COYOTE3_INGEST_WATCH_DIR` should live under `COYOTE3_DATA_CONTAINER_ROOT`.
When sample manifests contain absolute file paths, set the container root to the
same path used in those manifests.

Example for local development data under `/data/coyote3`:

```env
COYOTE3_DATA_HOST_ROOT='/data/coyote3'
COYOTE3_DATA_CONTAINER_ROOT='/data/coyote3'
COYOTE3_INGEST_WATCH_DIR='/data/coyote3/ingest'
```

## Repository Configuration Boundaries

Coyote3 keeps API and UI configuration inside the component that owns it.

API-owned configuration lives under `api/config/`:

- `app_config.py` selects production, staging, development, and test runtime settings.
- `constants.py` defines product vocabularies such as assay categories, analysis types, auth providers, file keys, list types, and permission categories.
- `runtime.py` exposes stable helper functions for the rest of the backend.
- `coyote3_collections.toml` maps logical repository collection attributes to MongoDB collection names.

The root-level `config/` directory is not used for API runtime configuration. New API TOML files should be added under `api/config/` and loaded relative to that package.

UI-owned configuration stays under `frontend/`:

- `frontend/vite.config.ts` owns Vite development and build behavior.
- `frontend/tailwind.config.*` or theme files own UI theme tokens when present.
- `frontend/src/lib/` owns frontend-only formatting and presentation helpers.
- `frontend/public/` owns static UI assets.

The UI should consume backend contracts and metadata for clinical rules. It should not duplicate API constants unless the value is strictly presentational.

## Critical Configuration Parameters

### Cryptographic And Identity Secrets
These parameters are security-sensitive. They should be unique per environment and must not be committed to version control:
- `SECRET_KEY`: key used for session signing and data protection.
- `INTERNAL_API_TOKEN`: Shared secret for service-to-service requests.
- `PASSWORD_TOKEN_SALT`: Cryptographic salt for user lifecycle link generation.
- `MONGO_APP_PASSWORD`: Identity secret for least-privilege database access.

### Core Execution Definitions
- `MONGO_URI`: Connection string for MongoDB.
- `CACHE_REDIS_URL`: Connection string for Redis.
- `API_WORKERS`: Worker count for the FastAPI service.
- `SCRIPT_NAME`: External URL prefix when the application is mounted below the domain
  root by Apache or another reverse proxy. Use an empty value for root deployments
  and a leading-slash value such as `/coyote3` for subpath deployments.
- `WEB_APP_BASE_URL`: Public web URL used for generated links.
- `HELP_CENTER_URL`: Documentation or help URL shown in the web UI.

!!! info "Subpath deployments"

    `SCRIPT_NAME` is the only source of truth for the browser-facing prefix.
    FastAPI uses it as `root_path`, Vite uses it as the React basename and static
    asset base, and the compose nginx proxy renders exact prefixed routes from
    the same value at startup. Internal service calls and container health checks
    continue to use the stable `/api/v1/...` routes.
    Public unauthenticated UI routes are browser-facing and are served below the
    same prefix, for example `/coyote3/public/catalog`.
    The mount root accepts both `/coyote3` and `/coyote3/`; the frontend
    normalizes the slashless form before React Router starts.

## Caching

Coyote3 uses a layered caching model:
- **Hot Tier (Redis)**: request and session-adjacent cache data.
- **Warm Tier (MongoDB)**: stored snapshots of dashboard or summary data.
- **Cache Requirements**: `CACHE_REQUIRED` controls whether Redis failure is fatal or tolerated.

### Dashboard Cache Tuning
The following settings control dashboard cache freshness and retention:
- `DASHBOARD_SUMMARY_CACHE_TTL_SECONDS`: Maximum age for localized hot-cache data.
- `DASHBOARD_SUMMARY_SNAPSHOT_MAX_AGE_SECONDS`: Refresh threshold for persistent Mongo snapshots.
- `DASHBOARD_SUMMARY_SNAPSHOT_TTL_SECONDS`: Physical retention period for historical dashboard data.

## Access Control And Identity

The platform supports multiple authentication providers and keeps local and centralized authentication separate.

### Role Levels
Assigned role levels provide the baseline for permission evaluation.

| Role Designation | Access Level | Professional Scope |
| --- | --- | --- |
| `viewer` | `5` | Unprivileged clinical oversight. |
| `user` | `9` | Standard diagnostic interpretation and reporting. |
| `manager` | `99` | Departmental oversight and review. |
| `admin` | `99999` | System-wide configuration and security control. |

### Identity Normalization
Login identifiers are normalized to reduce duplicates and mismatches:
- All email-style identifiers are normalized to lowercase.
- Validation requires explicit local and domain segment definitions to ensure organizational alignment.

## Service Integration Guidelines

### SMTP and Communication
Mail relay defaults for Skane (MXIS):
- `SMTP_HOST`: Standardized relay host `mxis.skane.se`.
- `SMTP_PORT`: Standardized port `25` (Unauthenticated).
- `SMTP_FROM_EMAIL`: Authorized organizational sender address.

### External Analytic Integrations
The platform enables optional one-way deep-linking to secondary analytic platforms such as Gens and IGV through the `GENS_URI` and `IGV_URI` directives.

## Local Migration Workspace

One-off migration, repair, or local data-conversion scripts belong under `migration_scripts/`. That directory is ignored by git so center-specific scripts, sample paths, and scratch payloads do not pollute normal reviews.

Use `scripts/` only for supported bootstrap, backup, restore, validation, seed, and operations commands. Promote any migration that must become part of supported operations into `scripts/` with tests and documentation.

## Environmental Verification

Validate environment files before deployment:

```bash
# Execute environment configuration validation
bash scripts/validate_env_secrets.sh .coyote3_env
```

For maintenance checks and seed verification, see [Operations / Maintenance and Quality](../operations/maintenance_and_quality.md).
