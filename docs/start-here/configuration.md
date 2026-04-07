# Configuration Model

## Environment files

- `.coyote3_env` (prod-style)
- `.coyote3_stage_env` (stage)
- `.coyote3_dev_env` (dev)
- `.coyote3_test_env` (test stack and CI-like local runs)

Template sources:

- `deploy/env/example.prod.env`
- `deploy/env/example.stage.env`
- `deploy/env/example.dev.env`
- `deploy/env/example.test.env`

Each template is intentionally secret-safe (`CHANGE_ME_*`) and mirrors the
runtime env file shape, so centers can copy and fill values without guessing.

## Standard host-port allocation

Use these non-overlapping ranges by default:

| Environment | Proxy (optional) | Web | Docs | API | Redis | Mongo |
| --- | --- | --- | --- | --- | --- | --- |
| `prod` (`.coyote3_env`) | `5815` | `5816` | `5821` | `5818` | `5819` | `5820` |
| `stage` (`.coyote3_stage_env`) | `8804` | `8805` | `8809` | `8806` | `8807` | `8808` |
| `dev` (`.coyote3_dev_env`) | n/a | `6801` | `6805` | `6802` | `6803` | `6804` |
| `test` (`.coyote3_test_env`) | n/a | `6811` | `6815` | `6812` | `6813` | `6814` |

## Critical variables

Security-sensitive:

- `SECRET_KEY`
- `INTERNAL_API_TOKEN`
- `PASSWORD_TOKEN_SALT`
- `MONGO_ROOT_USERNAME`
- `MONGO_ROOT_PASSWORD`
- `MONGO_APP_USER`
- `MONGO_APP_PASSWORD`

Core runtime:

- `COYOTE3_DB`
- `MONGO_URI`
- port vars for your target profile (`COYOTE3_*_WEB_PORT`, `COYOTE3_*_API_PORT`, `COYOTE3_*_REDIS_PORT`, `COYOTE3_*_MONGO_PORT`)
- docs endpoint vars (`COYOTE3_*_DOCS_PORT`, `HELP_CENTER_URL`)
- optional reverse-proxy endpoint vars (`COYOTE3_PROXY_PORT`, `COYOTE3_STAGE_PROXY_PORT`)
- optional per-service runtime caps (`*_CONTAINER_MEM_LIMIT`, `*_CONTAINER_CPU_LIMIT`)
- `API_WORKERS` (non-dev API worker count for uvicorn)
- `CACHE_REDIS_URL` (Redis endpoint for API/UI cache backends)
- `CACHE_ENABLED` (`1` enables cache backend initialization)
- `CACHE_REQUIRED` (`1` fail-fast if Redis is unavailable; `0` degrade to no-op cache)
- `CACHE_REDIS_CONNECT_TIMEOUT`, `CACHE_REDIS_SOCKET_TIMEOUT` (seconds)
- `DASHBOARD_SUMMARY_CACHE_TTL_SECONDS` (Redis summary cache TTL)
- `DASHBOARD_SUMMARY_SNAPSHOT_MAX_AGE_SECONDS` (max age for persisted dashboard snapshot reuse)
- `DASHBOARD_SUMMARY_SNAPSHOT_TTL_SECONDS` (Mongo TTL retention for snapshot documents)
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM_EMAIL`, `SMTP_USE_TLS`, `SMTP_USE_SSL`
- `WEB_APP_BASE_URL` (required for invite/reset links)
- `API_RATE_LIMIT_ENABLED`, `API_RATE_LIMIT_REQUESTS_PER_MINUTE`, `API_RATE_LIMIT_WINDOW_SECONDS`
- `WEB_RATE_LIMIT_ENABLED`, `WEB_RATE_LIMIT_REQUESTS_PER_MINUTE`, `WEB_RATE_LIMIT_WINDOW_SECONDS`

Help/docs URL model:

- `HELP_CENTER_URL`: primary URL for standalone docs container.
- UI does not serve docs pages directly; all help/docs links should point to `HELP_CENTER_URL`.

## What each env key means

The `.coyote3*env` files now intentionally match their `deploy/env/example.*.env`
templates one-for-one. If you need to understand a key, use the groups below as
the source of truth.

### Core app secrets

| Key | Meaning | Notes |
| --- | --- | --- |
| `SECRET_KEY` | Main Flask/API secret used for signed session and security-sensitive app state. | Required in all non-test environments. Rotate carefully. |
| `INTERNAL_API_TOKEN` | Shared token for selected internal/system routes. | Treat like a secret; do not expose to browsers. |
| `API_SESSION_SALT` | Salt used for API session token signing/derivation. | Keep stable per environment. |
| `PASSWORD_TOKEN_SALT` | Salt for password reset / invite token generation. | Required anywhere local-password flows are enabled. |

### Runtime identity

| Key | Meaning | Notes |
| --- | --- | --- |
| `ENV_NAME` | Human-readable runtime profile label. | Examples: `production`, `staging`, `development`, `test`. |
| `COYOTE3_DB` | Main application Mongo database name. | Runtime and bootstrap scripts use this. |
| `SESSION_COOKIE_NAME` | Cookie name used by the Flask UI runtime. | Keep unique per environment to avoid browser collisions. |
| `API_SESSION_COOKIE_NAME` | Cookie name used by the FastAPI runtime. | Keep unique per environment. |
| `SCRIPT_NAME` | URL base path prefix when the app is hosted below `/`. | `/coyote3`, `/coyote3_dev`, etc. |

### MongoDB

| Key | Meaning | Notes |
| --- | --- | --- |
| `MONGO_ROOT_USERNAME` | Mongo root/admin username. | Used for bootstrap/admin operations and compose health checks. |
| `MONGO_ROOT_PASSWORD` | Mongo root/admin password. | Only applied on first initialization of an empty Mongo volume. |
| `MONGO_APP_USER` | Least-privilege runtime Mongo username. | Used by the application via `MONGO_URI`. |
| `MONGO_APP_PASSWORD` | Password for the runtime Mongo user. | Must match `MONGO_URI`. |
| `MONGO_URI` | Application Mongo connection URI. | Normally points at the compose service host for that environment. |
| `COYOTE3_MONGO_PORT` / `COYOTE3_STAGE_MONGO_PORT` / `COYOTE3_DEV_MONGO_PORT` / `COYOTE3_TEST_MONGO_PORT` | Host port exposed for Mongo in that environment. | Used by local scripts and manual admin commands. |

Important behavior:

- `MONGO_INITDB_ROOT_*` in compose only matters the first time an empty Mongo volume is created.
- If the volume already exists, changing `MONGO_ROOT_PASSWORD` in the env file does not change the stored password inside Mongo.
- `MONGO_URI` should match `MONGO_APP_USER` and `MONGO_APP_PASSWORD`.

### Redis and cache behavior

| Key | Meaning | Notes |
| --- | --- | --- |
| `CACHE_REDIS_URL` | Redis URL used by API/UI cache layers. | Usually points at the compose Redis service. |
| `DASHBOARD_SUMMARY_CACHE_TTL_SECONDS` | Hot Redis cache lifetime for dashboard summary payloads. | Short TTL, fast refresh. |
| `DASHBOARD_SUMMARY_SNAPSHOT_MAX_AGE_SECONDS` | Max age for reusing a Mongo snapshot before recomputing. | Warm-cache freshness threshold. |
| `DASHBOARD_SUMMARY_SNAPSHOT_TTL_SECONDS` | TTL retention window for persisted dashboard snapshots. | Physical deletion is handled by Mongo TTL index. |

### Host port mappings

| Key | Meaning | Notes |
| --- | --- | --- |
| `COYOTE3_WEB_PORT` / `COYOTE3_STAGE_WEB_PORT` / `COYOTE3_DEV_WEB_PORT` / `COYOTE3_TEST_WEB_PORT` | Host port for the Flask UI container. | Browser entrypoint for that environment. |
| `COYOTE3_API_PORT` / `COYOTE3_STAGE_API_PORT` / `COYOTE3_DEV_API_PORT` / `COYOTE3_TEST_API_PORT` | Host port for the FastAPI container. | Used by scripts and API checks. |
| `COYOTE3_DOCS_PORT` / `COYOTE3_STAGE_DOCS_PORT` / `COYOTE3_DEV_DOCS_PORT` / `COYOTE3_TEST_DOCS_PORT` | Host port for the docs container. | Standalone MkDocs site. |
| `COYOTE3_REDIS_PORT` / `COYOTE3_STAGE_REDIS_PORT` / `COYOTE3_DEV_REDIS_PORT` / `COYOTE3_TEST_REDIS_PORT` | Host port for Redis. | Mostly for local inspection/debugging. |
| `COYOTE3_PROXY_PORT` / `COYOTE3_STAGE_PROXY_PORT` | Optional reverse-proxy port. | Only used where the proxy service is enabled. |

### Optional container runtime limits

| Key | Meaning | Notes |
| --- | --- | --- |
| `COYOTE3_CONTAINER_MEM_LIMIT` and env-specific variants | Docker memory limit per container in that stack. | Compose-only tuning. |
| `COYOTE3_CONTAINER_CPU_LIMIT` and env-specific variants | Docker CPU limit per container in that stack. | Compose-only tuning. |
| `API_WORKERS` | Uvicorn worker count for non-dev API containers. | Higher for stage/prod, lower for test. |

### Build metadata

| Key | Meaning | Notes |
| --- | --- | --- |
| `COYOTE3_VERSION` | Image/runtime version label. | Used in container names and UI display. |
| `GIT_COMMIT` | Build-time Git commit label. | Optional metadata. |
| `BUILD_TIME` | Build timestamp label. | Optional metadata. |

### App behavior

| Key | Meaning | Notes |
| --- | --- | --- |
| `FLASK_DEBUG` | Enables Flask debug mode where appropriate. | `1` in dev only. |
| `DEVELOPMENT` | Runtime behavior toggle for development mode. | Influences config selection. |
| `TESTING` | Runtime behavior toggle for test mode. | Used by tests/stack setup. |
| `APP_DNS` | Preferred DNS server passed to containers. | Compose/runtime networking convenience. |
| `REPORTS_BASE_PATH` | Filesystem base path for report output. | Must match mounted storage layout. |

### LDAP authentication

| Key | Meaning | Notes |
| --- | --- | --- |
| `LDAP_HOST` | LDAP server URI. | Empty when LDAP is disabled. |
| `LDAP_BASE_DN` | LDAP base DN for user lookup. | Required in real LDAP deployments. |
| `LDAP_BINDDN` | Service account bind DN for LDAP queries. | Required when bind auth is used. |
| `LDAP_SECRET` | Password/secret for the LDAP bind account. | Secret; keep out of git. |

### CORS

| Key | Meaning | Notes |
| --- | --- | --- |
| `CORS_ORIGINS` | Comma-separated browser origins allowed to call the API. | Use explicit hostnames in stage/prod. |

### Center contact information

These keys drive the contact/help information shown in the UI:

- `CONTACT_CLINICAL_EMAIL`
- `CONTACT_RESEARCH_EMAIL`
- `CONTACT_SAMPLES_EMAIL`
- `CONTACT_PHONE_MAIN`
- `CONTACT_PHONE_URGENT`
- `CONTACT_ADDRESS`

Leave them blank in local/dev/test if you do not need them.

### Optional integrations

| Key | Meaning | Notes |
| --- | --- | --- |
| `GENS_URI_OLD` | Legacy Gens link base used by an older UI path. | Still used by the DNA findings UI. |
| `GENS_URI` | Current Gens integration base URL. | Optional. |
| `IGV_URI` | IGV integration base URL. | Optional. |

### SMTP and user lifecycle

| Key | Meaning | Notes |
| --- | --- | --- |
| `SMTP_HOST` | SMTP relay hostname. | Usually organization relay. |
| `SMTP_PORT` | SMTP relay port. | Commonly `25` or `587`. |
| `SMTP_USERNAME` | SMTP auth username. | Blank for relay-without-auth setups. |
| `SMTP_PASSWORD` | SMTP auth password. | Blank when not used. |
| `SMTP_USE_TLS` | Use STARTTLS. | `1` or `0`. |
| `SMTP_USE_SSL` | Use implicit SSL/TLS. | `1` or `0`. |
| `SMTP_FROM_EMAIL` | Sender address for app emails. | Invite/reset emails use this. |
| `SMTP_FROM_NAME` | Display name for app emails. | Usually `Coyote3`. |
| `WEB_APP_BASE_URL` | Public browser base URL for UI links. | Used in invite/reset links. |
| `HELP_CENTER_URL` | Public docs/help URL. | UI help links point here. |
| `PASSWORD_TOKEN_TTL_SECONDS` | Lifetime for password invite/reset tokens. | Default one hour. |

### Request rate limiting

| Key | Meaning | Notes |
| --- | --- | --- |
| `API_RATE_LIMIT_ENABLED` | Turns API request limiting on/off. | `1` enables middleware enforcement. |
| `API_RATE_LIMIT_REQUESTS_PER_MINUTE` | API request budget per identity/window. | Tune for machine/API clients. |
| `API_RATE_LIMIT_WINDOW_SECONDS` | API rate-limit window size in seconds. | Usually `60`. |
| `WEB_RATE_LIMIT_ENABLED` | Turns web request limiting on/off. | Used by Flask-side limiter. |
| `WEB_RATE_LIMIT_REQUESTS_PER_MINUTE` | Web request budget per identity/window. | Lower than API by default. |
| `WEB_RATE_LIMIT_WINDOW_SECONDS` | Web rate-limit window size in seconds. | Usually `60`. |

## Redis cache model

Redis is the shared cache backend for both runtimes:

- API runtime cache namespace: `coyote3_cache:api:*`
- UI runtime cache namespace: `coyote3_cache:web:*`

Operational behavior:

- `CACHE_REQUIRED=1`: startup fails when Redis cannot be reached (strict mode).
- `CACHE_REQUIRED=0`: startup continues with disabled/no-op cache (degraded mode).
- Cache backend is not an in-process memory cache replacement for production.
- Dashboard summary uses a two-layer cache: Redis (hot) + Mongo `dashboard_metrics` snapshot (warm).
- Snapshot retention is enforced by a Mongo TTL index on `dashboard_metrics.updated_at`.
- Sample home lists use Redis keys with a version token (`samples:list:version`).
- Sample mutations (delete, report save, sample/filter updates) bump the version token immediately.
- As a result, sample-home pages reflect state changes right after write operations without waiting for TTL expiry.

Dashboard summary cache controls (different purposes):

- `DASHBOARD_SUMMARY_CACHE_TTL_SECONDS`
  Fast Redis cache lifetime for summary payload reuse.
- `DASHBOARD_SUMMARY_SNAPSHOT_MAX_AGE_SECONDS`
  Freshness threshold for reusing Mongo snapshot payloads before recomputing.
- `DASHBOARD_SUMMARY_SNAPSHOT_TTL_SECONDS`
  Mongo TTL retention window for physical deletion of old snapshot documents.

Recommended relationship:

- `DASHBOARD_SUMMARY_CACHE_TTL_SECONDS < DASHBOARD_SUMMARY_SNAPSHOT_MAX_AGE_SECONDS <= DASHBOARD_SUMMARY_SNAPSHOT_TTL_SECONDS`

Example (valid dev profile):

```env
DASHBOARD_SUMMARY_CACHE_TTL_SECONDS='30'
DASHBOARD_SUMMARY_SNAPSHOT_MAX_AGE_SECONDS='120'
DASHBOARD_SUMMARY_SNAPSHOT_TTL_SECONDS='300'
```

Image/version policy:

- Compose stacks pin Redis to `redis:7.4.3` (no floating `latest` tag).

## SMTP and user lifecycle settings

Coyote3 now supports provider-aware login and local-user lifecycle flows:

- `auth_type=coyote3` users authenticate locally and can use:
  - admin invite (set-password link)
  - forgot-password reset link
  - authenticated password change
- `auth_type=ldap` users authenticate via LDAP.

### Login identifier and email format rules

For local users, Coyote3 accepts center-local addresses and normal internet-style addresses.

Accepted:

- `admin@your-center.org`
- `admin@coyote3.local`
- uppercase input is normalized to lowercase (for example `ADMIN@COYOTE3.LOCAL` -> `admin@coyote3.local`)

Minimum validation enforced:

- must contain `@`
- local part must be non-empty
- domain part must be non-empty

Rejected:

- `admin` (missing `@`)
- `@coyote3.local` (missing local part)
- `admin@` (missing domain part)

Note:

- This validation is intentionally basic to support private/reserved center domains (for example `.local`) in isolated deployments.

### Role level baseline

Use this RBAC level baseline in role seed/bootstrap documents:

| Role | Level |
| --- | --- |
| `external` | `1` |
| `viewer` | `5` |
| `intern` | `7` |
| `user` | `9` |
| `manager` | `99` |
| `developer` | `9999` |
| `admin` | `99999` |

If role levels drift from this baseline, permission gates that rely on
`min_level` checks can deny valid users unexpectedly.

Recommended SMTP baseline for centers using the Skane relay:

```env
SMTP_HOST='mxis.skane.se'
SMTP_PORT='25'
SMTP_USERNAME=''
SMTP_PASSWORD=''
SMTP_USE_TLS='0'
SMTP_USE_SSL='0'
SMTP_FROM_EMAIL='CHANGE_ME_FROM_EMAIL'
SMTP_FROM_NAME='Coyote3'
```

If relay delivery fails or SMTP is not configured, invite/reset still returns
manual setup URL metadata and a warning (no hard crash).

## Strict behavior by profile

Production and development should require explicit secrets. Test profile may use fixed CI-safe values.

Validate env quickly:

```bash
bash scripts/validate_env_secrets.sh .coyote3_env
bash scripts/validate_env_secrets.sh .coyote3_stage_env
bash scripts/validate_env_secrets.sh .coyote3_dev_env
```

For end-to-end operational checks (contract integrity, seed validation, first-run bootstrap, and verification commands), see:
[Operations / Maintenance And Quality](../operations/maintenance-and-quality.md).
