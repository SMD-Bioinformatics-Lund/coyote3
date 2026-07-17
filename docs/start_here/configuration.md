# Configuration And Environments

This document describes how Coyote3 configuration is organized across environments.

## Environment Files

Application behavior is controlled by environment files (`.coyote3_env*`). Templates live in `deploy/env/`:

- **Production**: Managed via `.coyote3_env` (Ref: `example.prod.env`).
- **Staging**: Managed via `.coyote3_stage_env` (Ref: `example.stage.env`).
- **Development**: Managed via `.coyote3_dev_env` (Ref: `example.dev.env`).
- **Continuous Validation**: Managed via `.coyote3_test_env` (Ref: `example.test.env`).

Use these templates as the starting point for each environment.

## Default Port Layout

Each environment exposes one HTTP entrypoint through nginx. Web UI, API, and
docs remain on internal container ports and are routed through the proxy:

| Domain Layer | Production | Staging | Development | Test/CI |
| --- | --- | --- | --- | --- |
| **HTTP proxy** | `5815` | `8804` | `6801` | `6811` |
| **MongoDB** | `5820` | `8808` | `6804` | `6814` |

Routes:

- `/` -> Web UI
- `/api/` -> FastAPI
- `/docs-site/` -> documentation site

Redis is internal-only. MongoDB is only exposed when the optional `with-mongo`
profile is used.

### Customizing Ports

The HTTP proxy host port is configurable via environment variables. Override it
in your `.coyote3_env` file or export it before running `docker compose`:

| Environment Variable | Default | Service |
| --- | --- | --- |
| `COYOTE3_PORT` | `5815` | Production HTTP proxy |
| `COYOTE3_STAGE_PORT` | `8804` | Staging HTTP proxy |
| `COYOTE3_DEV_PORT` | `6801` | Development HTTP proxy |
| `COYOTE3_TEST_PORT` | `6811` | Test HTTP proxy |
| `COYOTE3_MONGO_PORT` | `5820` | MongoDB — optional (`--profile with-mongo`) |
| `COYOTE3_STAGE_MONGO_PORT` | `8808` | Staging MongoDB — optional (`--profile with-mongo`) |
| `COYOTE3_DEV_MONGO_PORT` | `6804` | Development MongoDB — optional (`--profile with-mongo`) |
| `COYOTE3_TEST_MONGO_PORT` | `6814` | Test MongoDB — optional (`--profile with-mongo`) |

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
- `WEB_APP_BASE_URL`: Public web URL used for generated links.
- `HELP_CENTER_URL`: Documentation or help URL shown in the web UI.

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

## Environmental Verification

Validate environment files before deployment:

```bash
# Execute environment configuration validation
bash scripts/validate_env_secrets.sh .coyote3_env
```

For maintenance checks and seed verification, see [Operations / Maintenance and Quality](../operations/maintenance_and_quality.md).
