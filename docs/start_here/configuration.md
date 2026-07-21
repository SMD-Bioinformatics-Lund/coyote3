# Configuration And Environments

Coyote3 uses one copied environment file per deployment environment and keeps
runtime wiring inside the application and Compose stacks. The environment file is
for center-owned values only: identity, public mount details, secrets, database
connection, data paths, operational limits, and optional integrations.

## Environment Files

Copy the single template for the environment you are deploying:

```bash
cp deploy/env/example.env .coyote3_dev_env
cp deploy/env/example.env .coyote3_stage_env
cp deploy/env/example.env .coyote3_test_env
cp deploy/env/example.env .coyote3_env
```

Then update the copied file. Local `.coyote3_*_env` files are ignored by git and
must not be committed.

!!! info "One environment selector"

    `ENV_NAME` is the environment selector. Use values such as `development`,
    `testing`, `staging`, or `production`. Coyote3 does not use separate
    `DEVELOPMENT=1` or `TESTING=1` flags.

## Browser Entry Points

Each environment exposes a single nginx HTTP entrypoint. Web UI, API, public
pages, and the documentation site are routed through that one port.

| Setting | Meaning |
| --- | --- |
| `COYOTE3_PORT` | Host port exposed by nginx for the selected environment. |
| `SCRIPT_NAME` | Browser-facing mount prefix, for example `/coyote3_dev`. Use an empty string only for root deployments. |
| `PUBLIC_BASE_URL` | Public origin without the script prefix, for example `https://localhost` or `https://example.org`. |

For local development with:

```env
COYOTE3_PORT='6801'
SCRIPT_NAME='/coyote3_dev'
PUBLIC_BASE_URL='https://localhost'
```

the mounted browser URLs are:

| URL | Purpose |
| --- | --- |
| `https://localhost/coyote3_dev/` | Authenticated web UI through Apache or another front proxy. |
| `https://localhost/coyote3_dev/public/catalog` | Public catalog UI. |
| `https://localhost/coyote3_dev/api/v1/docs` | Swagger UI. |
| `https://localhost/coyote3_dev/docs-site/` | MkDocs documentation site. |

When a local nginx proxy is accessed directly, the same paths are available on
`http://localhost:${COYOTE3_PORT}`.

!!! note "Internal service URLs"

    Redis, Celery broker/result URLs, API health paths, and docs upstream URLs
    are internal service wiring. They are fixed in the application or Compose
    files and are not configured in the center environment file.

## Data Mounts

The host data root is mounted into containers at `/data`.

| Setting | Meaning |
| --- | --- |
| `COYOTE3_DATA_HOST_ROOT` | Host directory made visible to API and worker containers. |
| `REPORTS_BASE_PATH` | Container path where report artifacts are written. |
| `CELERY_INGEST_STAGING_DIR` | Container path used for staged async upload jobs. |
| `COYOTE3_INGEST_WATCH_DIR` | Container path scanned by the watch-folder ingest task. |

Example:

```env
COYOTE3_DATA_HOST_ROOT='/home/center/coyote3-data'
REPORTS_BASE_PATH='/data/reports'
CELERY_INGEST_STAGING_DIR='/data/ingest_staging'
COYOTE3_INGEST_WATCH_DIR='/data/incoming'
```

If sample manifests contain absolute file paths, mount the host directory so the
same path is readable inside API and worker containers, or update manifests to
use the container-visible `/data/...` paths.

!!! info "Host paths in watched manifests"

    The Compose deployment mounts `COYOTE3_DATA_HOST_ROOT` at the fixed
    container path `/data`. The watch-folder ingest task translates manifest
    paths under `COYOTE3_DATA_HOST_ROOT` to `/data/...` before parsing sample
    files. This lets centers keep host-owned manifest paths while the API and
    worker read the files through the same container mount.

## Environment Variable Reference

The canonical template is `deploy/env/example.env`.

| Variable | Required | Expected Value | Purpose |
| --- | --- | --- | --- |
| `ENV_NAME` | Yes | `development`, `testing`, `staging`, or `production` | Selects runtime behavior and labels audit/log context. |
| `COYOTE3_DB` | Yes | MongoDB database name | Primary application database. |
| `BAM_DB` | Yes | MongoDB database name | BAM-service database used for sample BAM lookups. |
| `ORGANIZATION_NAME` | Yes | Center/service display name | Used on login, public, contact, and support pages. |
| `SECRET_KEY` | Yes | High-entropy secret | Signs application security state. |
| `INTERNAL_API_TOKEN` | Yes | High-entropy token | Authenticates trusted service-to-service internal API calls. |
| `API_SESSION_SALT` | Yes | High-entropy salt | Derives stored browser API session hashes. |
| `PASSWORD_TOKEN_SALT` | Yes | High-entropy salt | Derives invite and password-reset action token hashes. |
| `COYOTE3_PORT` | Yes | Host port | One exposed nginx entrypoint for UI, API, public pages, and docs. |
| `SCRIPT_NAME` | Yes | Empty string or `/prefix` | Public URL mount prefix used by browser routing and generated links. |
| `PUBLIC_BASE_URL` | Link-generating deployments | Public origin without `SCRIPT_NAME` | Origin used for links generated outside an active browser request, such as password reset email links. |
| `CORS_ORIGINS` | Production | Comma-separated origins | Allowed browser origins for API calls. |
| `COYOTE3_CONTAINER_MEM_LIMIT` | No | Compose memory value such as `2g` | Per-container memory limit. |
| `COYOTE3_CONTAINER_CPU_LIMIT` | No | Compose CPU value such as `2.0` | Per-container CPU limit. |
| `MONGO_ROOT_USERNAME` | With compose Mongo | Username | Optional compose-managed Mongo root account. |
| `MONGO_ROOT_PASSWORD` | With compose Mongo | Secret password | Optional compose-managed Mongo root password. |
| `MONGO_APP_USER` | With compose Mongo | Username | Application Mongo user created by compose Mongo init. |
| `MONGO_APP_PASSWORD` | With compose Mongo | Secret password | Application Mongo password. |
| `MONGO_URI` | Yes | MongoDB URI | API and worker MongoDB connection string. |
| `CACHE_ENABLED` | No | `1` or `0` | Enables Redis-backed application cache use. |
| `CACHE_REQUIRED` | No | `1` or `0` | Makes cache connection failure fatal at startup when enabled. |
| `CACHE_REDIS_CONNECT_TIMEOUT` | No | Seconds | Redis connection timeout. |
| `CACHE_REDIS_SOCKET_TIMEOUT` | No | Seconds | Redis socket timeout. |
| `DASHBOARD_SUMMARY_CACHE_TTL_SECONDS` | No | Seconds | Hot-cache lifetime for dashboard summaries. |
| `DASHBOARD_SUMMARY_SNAPSHOT_MAX_AGE_SECONDS` | No | Seconds | Maximum accepted dashboard snapshot age. |
| `DASHBOARD_SUMMARY_SNAPSHOT_TTL_SECONDS` | No | Seconds | Persistent dashboard snapshot retention. |
| `API_WORKERS` | No | Positive integer | Uvicorn worker process count for non-dev stacks. |
| `APP_DNS` | No | DNS server IP | Optional Docker DNS override for restricted center networks. |
| `SESSION_COOKIE_SECURE` | Production | `1` or `0` | Marks API session cookies HTTPS-only. |
| `API_SESSION_COOKIE_NAME` | Yes | Cookie name | Browser API session cookie name, unique per mounted environment. |
| `API_SESSION_TTL_SECONDS` | No | Seconds | Browser API session lifetime. |
| `API_SESSION_COOKIE_SAMESITE` | No | `lax`, `strict`, or `none` | Browser session cookie SameSite policy. |
| `AUDIT_RETENTION_DAYS` | No | Days | Audit event retention window. |
| `LOG_SERVICE_NAME` | No | Service label | Structured log service name. |
| `LOG_FILE_ENABLED` | No | `1` or `0` | Enables on-disk JSONL logs in addition to stdout. |
| `LOG_RETENTION_DAYS` | No | Days | Disk log retention window. |
| `LOG_GZIP_AFTER_DAYS` | No | Days | Age after which nightly maintenance gzips old logs. |
| `LOG_LEVEL` | No | Python logging level | Minimum runtime log level. |
| `NOTIFICATION_RETENTION_DAYS` | No | Days | Notification retention window. |
| `COYOTE3_DATA_HOST_ROOT` | Yes | Host path | Host data root mounted into containers at `/data`. |
| `REPORTS_BASE_PATH` | Yes | Container path | Report output directory. |
| `CELERY_INGEST_STAGING_DIR` | Yes | Container path | Async ingest upload staging directory. |
| `CELERY_DEFAULT_QUEUE` | No | Queue name | Default Celery queue. |
| `CELERY_INGEST_QUEUE` | No | Queue name | Queue used for ingest tasks. |
| `CELERY_LOG_LEVEL` | No | Logging level | Celery worker log level. |
| `CELERY_WORKER_CONCURRENCY` | No | Positive integer | Celery worker process concurrency. |
| `CELERY_TASK_TIME_LIMIT` | No | Seconds | Hard Celery task timeout. |
| `CELERY_TASK_SOFT_TIME_LIMIT` | No | Seconds | Soft Celery task timeout. |
| `CELERY_RESULT_EXPIRES` | No | Seconds | Celery result expiry. |
| `CELERY_WORKER_PREFETCH_MULTIPLIER` | No | Positive integer | Celery prefetch control. Use `1` for long ingest tasks. |
| `COYOTE3_MAINTENANCE_HOUR` | No | `0` to `23` | Local hour for scheduled maintenance. |
| `COYOTE3_INGEST_WATCH_ENABLED` | No | `1` or `0` | Enables scheduled watch-folder ingest. |
| `COYOTE3_INGEST_WATCH_DIR` | Watcher enabled | Container path | Directory scanned for ingest manifests. |
| `COYOTE3_INGEST_WATCH_FILENAME` | No | File name or glob | Manifest name pattern, for example `coyote3.yaml` or `*.yaml`. |
| `COYOTE3_INGEST_DONE_SUFFIX` | No | File suffix | Suffix applied after successful watch-folder ingest. |
| `COYOTE3_INGEST_FAILED_SUFFIX` | No | File suffix | Suffix applied after failed watch-folder ingest. |
| `COYOTE3_INGEST_WATCH_INTERVAL_SECONDS` | No | Seconds | Beat interval for watch-folder scanning. |
| `COYOTE3_INGEST_WATCH_UPDATE_EXISTING` | No | `1` or `0` | Allows watch ingest to replace an existing sample. |
| `COYOTE3_INGEST_WATCH_INCREMENT` | No | `1` or `0` | Enables incremental naming behavior where supported. |
| `LDAP_HOST` | LDAP deployments | Hostname or URI | LDAP server host. |
| `LDAP_BASE_DN` | LDAP deployments | Distinguished name | LDAP search base. |
| `LDAP_USER_LOGIN_ATTR` | LDAP deployments | Attribute name, usually `mail` | LDAP login lookup attribute. |
| `LDAP_BINDDN` | LDAP deployments | Distinguished name | LDAP bind identity. |
| `LDAP_SECRET` | LDAP deployments | Secret password | LDAP bind password. |
| `LDAP_USER_DN` | LDAP deployments | Relative distinguished name | User subtree below base DN. |
| `GENS_URI` | No | URL | Optional Gens integration. |
| `IGV_URI` | No | URL | Optional IGV integration. |
| `KNOWLEDGEBASE_PLUGINS` | No | Comma-separated list | Optional Mongo-backed knowledgebase handlers. Supported values: `all`, `civic`, `iarc_tp53`, `brca`, `oncokb`, `cosmic`, `hgnc`. |
| `COYOTE3_ASSAY_CATALOG_YAML` | No | File path | Center-owned assay catalog narrative and matrix metadata. |
| `CONTACT_CONFIG_PATH` | No | File path | Center-owned public contact TOML file. |
| `ONCOKB_BASE_URL` | No | URL | Public OncoKB API base URL. |
| `ONCOKB_PUBLIC_LOOKUPS_ENABLED` | No | `1` or `0` | Enables public OncoKB lookup buttons and enrichment jobs. |
| `ONCOKB_REQUEST_TIMEOUT_SECONDS` | No | Seconds | Public OncoKB request timeout. |
| `ONCOKB_PUBLIC_BATCH_SIZE` | No | Positive integer | Batch size for OncoKB public enrichment. |
| `CLINPGX_BASE_URL` | No | URL | Public ClinPGx API base URL. |
| `CLINPGX_PUBLIC_LOOKUPS_ENABLED` | No | `1` or `0` | Enables ClinPGx lookup buttons. |
| `CLINPGX_REQUEST_TIMEOUT_SECONDS` | No | Seconds | ClinPGx request timeout. |
| `SMTP_HOST` | Mail deployments | Hostname | SMTP relay host. |
| `SMTP_PORT` | Mail deployments | Port | SMTP relay port. |
| `SMTP_USERNAME` | Mail deployments | Username or empty | SMTP username if required. |
| `SMTP_PASSWORD` | Mail deployments | Secret password or empty | SMTP password if required. |
| `SMTP_USE_TLS` | Mail deployments | `1` or `0` | Enables STARTTLS. |
| `SMTP_USE_SSL` | Mail deployments | `1` or `0` | Enables implicit SSL. |
| `SMTP_FROM_EMAIL` | Mail deployments | Email address | Sender for invite and password reset messages. |
| `SMTP_FROM_NAME` | Mail deployments | Display name | Sender display name. |
| `PASSWORD_TOKEN_TTL_SECONDS` | No | Seconds | Invite/reset token lifetime. |
| `API_RATE_LIMIT_ENABLED` | No | `1` or `0` | Enables API rate limiting. |
| `API_RATE_LIMIT_REQUESTS_PER_MINUTE` | No | Positive integer | API rate limit threshold. |
| `API_RATE_LIMIT_WINDOW_SECONDS` | No | Seconds | API rate limit window. |
| `WEB_RATE_LIMIT_ENABLED` | No | `1` or `0` | Enables public web-route rate limiting. |
| `WEB_RATE_LIMIT_REQUESTS_PER_MINUTE` | No | Positive integer | Web route rate limit threshold. |
| `WEB_RATE_LIMIT_WINDOW_SECONDS` | No | Seconds | Web route rate limit window. |

!!! tip "Generating secrets"

    Generate each secret independently. A practical local command is
    `openssl rand -hex 32`. Use longer token-safe values if your center policy
    requires them. Do not reuse the same value across environments.

## Values Not Stored In Env Files

The following values are intentionally derived or internal:

| Value | Source |
| --- | --- |
| Application version | `api/version.py`; compose wrappers export this transiently for image names. |
| Git commit and build time | Build metadata injected by CI or compose wrappers, not hand-edited env values. |
| Redis URLs and Celery broker/result URLs | Compose service names such as `redis://coyote3_redis_dev:6379/0`. |
| API health path | Fixed endpoint `/api/v1/health`. |
| Documentation/help URL | Derived as `${PUBLIC_BASE_URL}${SCRIPT_NAME}/docs-site/`. |
| Repository and issue links | `api/config/contact.toml` `[codebase]` and `[[links]]` entries. |
| API session and audit collection names | Fixed internal collections `api_sessions` and `audit_events`. |
| Container data root | Fixed container path `/data`; only the host root is configurable. |
| MANE source | Database-backed HGNC/MANE annotation metadata, not a runtime file path. |

## Center Contact Configuration

`CONTACT_CONFIG_PATH` points to a TOML file that drives the public Contact page.
The committed default is `api/config/contact.toml`. Centers may copy that file
to a site-controlled path, edit the content, and set `CONTACT_CONFIG_PATH` to
that path in the environment file.

```toml
[organization]
name = "Coyote3"
department = "Clinical Genomics"
description = "Clinical genomics interpretation, review, and reporting service."

[[contacts]]
label = "Clinical support"
role = "Interpretation and report questions"
email = "clinical-support@example.org"
phone = "+46 ..."
description = "Questions about interpretation, report content, or clinical review workflow."

[codebase]
repository_url = "https://github.com/SMD-Bioinformatics-Lund/coyote3"
bug_report_url = "https://github.com/SMD-Bioinformatics-Lund/coyote3/issues/new?template=bug_report.md"
feature_request_url = "https://github.com/SMD-Bioinformatics-Lund/coyote3/issues/new?template=feature_request.md"
support_request_url = "https://github.com/SMD-Bioinformatics-Lund/coyote3/issues/new?template=support_request.md"
```

!!! info "Organization identity"

    `ORGANIZATION_NAME` is authoritative for the organization display name.
    The contact TOML stores richer public contact details.

!!! tip "Issue links"

    Bug reports, feature requests, and support requests are product/repository
    links, not deployment secrets. Configure them in `contact.toml` so the
    About page, Contact page, and user dropdown all show the same links.

## Configuration Boundaries

API-owned configuration lives under `api/config/`:

- `app_config.py` selects runtime settings.
- `constants.py` defines product vocabularies.
- `runtime.py` exposes backend helper functions.
- `coyote3_collections.toml` maps repository collection names.
- `contact.toml` stores center-owned public contact content.

UI-owned configuration stays under `frontend/`:

- `frontend/vite.config.ts` owns Vite behavior and `SCRIPT_NAME` routing.
- Tailwind and CSS files own presentation tokens.
- `frontend/src/lib/` owns frontend formatting and API helpers.

Clinical rules and collection contracts belong in backend Pydantic contracts and
domain services. The frontend consumes those contracts rather than duplicating
clinical logic.
