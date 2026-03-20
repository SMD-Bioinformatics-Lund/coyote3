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

| Environment | Web | Docs | API | Redis | Mongo |
| --- | --- | --- | --- | --- | --- |
| `prod` (`.coyote3_env`) | `5816` | `5821` | `5818` | `5819` | `5820` |
| `stage` (`.coyote3_stage_env`) | `8805` | `8809` | `8806` | `8807` | `8808` |
| `dev` (`.coyote3_dev_env`) | `6801` | `6805` | `6802` | `6803` | `6804` |
| `test` (`.coyote3_test_env`) | `6811` | `6815` | `6812` | `6813` | `6814` |

## Critical variables

Security-sensitive:

- `SECRET_KEY`
- `COYOTE3_FERNET_KEY`
- `INTERNAL_API_TOKEN`
- `MONGO_ROOT_USERNAME`
- `MONGO_ROOT_PASSWORD`
- `MONGO_APP_USER`
- `MONGO_APP_PASSWORD`

Core runtime:

- `COYOTE3_DB`
- `MONGO_URI`
- port vars for your target profile (`COYOTE3_*_WEB_PORT`, `COYOTE3_*_API_PORT`, `COYOTE3_*_REDIS_PORT`, `COYOTE3_*_MONGO_PORT`)
- docs endpoint vars (`COYOTE3_*_DOCS_PORT`, `HELP_CENTER_URL`)
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

Help/docs URL model:

- `HELP_CENTER_URL`: primary URL for standalone docs container.
- UI does not serve docs pages directly; all help/docs links should point to `HELP_CENTER_URL`.

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
