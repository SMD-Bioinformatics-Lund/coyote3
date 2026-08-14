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

### Minimum deployment values

Most environment variables have supported application or Compose defaults.
Every center must review and set only this core deployment contract:

| Variable | Why it must be supplied |
| --- | --- |
| `MONGO_URI` | Selects the reachable MongoDB deployment and application credentials. |
| `COYOTE3_DB` | Selects the primary application database explicitly. |
| `BAM_DB` | Selects the BAM-service database explicitly. |
| `SECRET_KEY` | Signs invitation and password-reset action tokens. |
| `INTERNAL_API_TOKEN` | Authenticates trusted internal service requests. |
| `PASSWORD_TOKEN_SALT` | Separates password-token signing from other signed data. |
| `CORS_ORIGINS` | Names the browser origin permitted to call the API. |
| `COYOTE3_DATA_HOST_ROOT` | Provides persistent sample, ingest, and report storage. |
| `COYOTE3_LOGS_HOST_ROOT` | Provides persistent application log storage. |

Set `ENV_NAME` explicitly even though a runtime default exists. Set
`SCRIPT_NAME`, `PUBLIC_BASE_URL`, organization/time-zone values, LDAP, SMTP,
and integration URLs only when required by the deployment. The remaining
variables in `example.env` are documented overrides with safe defaults.

## Center-Owned Configuration Files

Environment variables carry deployment wiring and secrets. Center policy is
kept in versioned configuration files under `api/config/center/` so it can be reviewed
as a clinical/configuration change rather than hidden in application code.

| File | Format | Detailed field reference | Purpose |
| --- | --- | --- | --- |
| `center/contact.toml` | TOML | [Contact table](../operations/center_configuration_files.md#contacttoml) | Center-owned organization, support, service-hour, and repeatable contact-card content. |
| `center/clinical_vocabulary.toml` | TOML | [Vocabulary table](../operations/center_configuration_files.md#clinical_vocabularytoml) | Center-owned authentication providers, sample-manifest file keys, required family inputs, and analysis-to-file bindings. Assay groups and sequencing-platform capabilities are fixed software workflow identifiers. |
| `center/clinical_query_policy.toml` | TOML | [Query-policy table](../operations/center_configuration_files.md#clinical_query_policytoml) | Released SNV evidence models, population-frequency fields, and restricted clinical exception scopes. |
| `center/collections.toml` | TOML | [Collection table](../operations/center_configuration_files.md#collectionstoml) | Database and collection names used by the persistence adapter. |
| `center/assay_catalog.yaml` | YAML | [Catalog table](../operations/center_configuration_files.md#assay_catalogyaml) | Public assay-catalog narrative fields that do not belong in clinical records. |
| `center/filter_flag_metadata.yaml` | YAML | [Flag table](../operations/center_configuration_files.md#filter_flag_metadatayaml) | Human-facing variant flag labels, severity, and tooltip descriptions. |

See [Center Configuration Reference](../operations/center_configuration_files.md)
for every center-owned TOML/YAML file, its fields, allowed values, owning
workflow, and change protocol. See
[Clinical Vocabulary Configuration](../operations/clinical_vocabulary.md) for
the detailed manifest-key and analysis-binding contract.

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

Compose mounts one center-owned host data root into API, worker, and beat
containers twice: at the fixed runtime location `/data`, and again at its
original host path. The fixed mount owns application workspaces; the identical
host-path mount lets pipeline manifests retain their original file references.

| Setting | Meaning |
| --- | --- |
| `COYOTE3_DATA_HOST_ROOT` | Host directory mounted by Compose at `/data` and at the same absolute path inside each ingest-capable container. |
| `/data/coyote3/reports` | Fixed container location for report artifacts. |
| `/data/coyote3/ingest_staging` | Fixed container location for staged async upload jobs. |
| `/data/coyote3/copied_sample_files/yaml` | Fixed container location scanned for ingest manifests. |

Example:

```env
COYOTE3_DATA_HOST_ROOT='/srv/coyote3/data'
```

Pipeline manifests may use either paths relative to the manifest, absolute
`/data/...` paths, or absolute paths below `COYOTE3_DATA_HOST_ROOT`. Host-root
paths are retained in sample file records so persisted provenance matches the
pipeline output.

!!! info "Container path contract"

    The Compose deployment mounts `COYOTE3_DATA_HOST_ROOT` at both `/data` and
    its original absolute path. Report output, upload staging, and watched
    manifests use fixed `/data/coyote3/...` locations. Pipeline-declared source
    files retain their original host paths and are readable through the
    identical-path mount.

## Environment Variable Reference

Every entry in the following table is an environment variable from the
canonical `deploy/env/example.env` template. TOML and YAML keys are **not**
environment variables and are documented in the linked center-configuration
tables above.

Some environment variables select configuration rather than duplicate it:
`COYOTE3_DB` selects the matching application-database table in
`center/collections.toml`, and `BAM_DB` selects the BAM-service table. The
physical collection names themselves remain TOML values.

!!! warning "HTTPS session cookies"

    Session cookies are HTTPS-only whenever the request uses HTTPS. Coyote3
    reads `X-Forwarded-Proto` when it is deployed behind a reverse proxy. Plain
    HTTP remains available only as a local-development fallback and emits an
    API runtime warning. There is no environment variable that can weaken this
    policy in a deployed HTTPS environment.

Built-in Mongo-backed knowledgebases are always registered. Their collections
may be empty when a center has not loaded reference data, but repository
registration is not configurable through an environment variable.

| Variable | Required | Expected Value | Purpose |
| --- | --- | --- | --- |
| `ENV_NAME` | No; default `production` at runtime | `development`, `testing`, `staging`, or `production` | Selects runtime behavior and labels audit/log context. Set it explicitly in copied env files so operators can identify the target immediately. |
| `COYOTE3_DB` | Yes | MongoDB database name | Primary application database. The database in `MONGO_URI` must match this value. |
| `BAM_DB` | Yes | MongoDB database name | BAM-service database used for sample BAM lookups. |
| `ORGANIZATION_NAME` | No; default `Coyote3` | Center/service display name | Used on login, public, contact, and support pages. |
| `LOCAL_TIME_ZONE` | No; default `UTC` | IANA timezone such as `Europe/Stockholm` | Local display timezone for browser-rendered dates and container-local schedules. Database timestamps remain UTC. |
| `SECRET_KEY` | Yes | High-entropy secret | Signs invite and password-reset action tokens. Browser sessions are opaque, server-stored tokens and do not use this value. |
| `INTERNAL_API_TOKEN` | Yes | High-entropy token | Authenticates trusted service-to-service internal API calls through the internal-token header. |
| `PASSWORD_TOKEN_SALT` | Yes | High-entropy salt | Separates invite and password-reset token signing from other application signing operations. |
| `COYOTE3_PORT` | No; compose profile default | Host port | One exposed nginx entrypoint for UI, API, public pages, and docs. |
| `SCRIPT_NAME` | No; default empty | Empty string or `/prefix` | Public URL mount prefix used by browser routing and generated links. |
| `PUBLIC_BASE_URL` | Link-generating deployments | Public origin without `SCRIPT_NAME` | Origin used for links generated outside an active browser request, such as password reset email links. |
| `CORS_ORIGINS` | Production | Comma-separated origins | Allowed browser origins for API calls. |
| `COYOTE3_CONTAINER_MEM_LIMIT` | No | Compose memory value; default `2g` | Per-container memory limit. |
| `COYOTE3_CONTAINER_CPU_LIMIT` | No | Compose CPU value; default `2.0` | Per-container CPU limit. |
| `MONGO_ROOT_USERNAME` | Self-hosted MongoDB | Username | MongoDB administrative username used only for database deployment and maintenance. |
| `MONGO_ROOT_PASSWORD` | Self-hosted MongoDB | Secret password | MongoDB administrative password. |
| `MONGO_APP_USER` | Self-hosted MongoDB | Username | Application MongoDB username created during first database initialization. |
| `MONGO_APP_PASSWORD` | Self-hosted MongoDB | Secret password | Application MongoDB password. |
| `MONGO_URI` | Yes | MongoDB URI | API and worker MongoDB connection string. |
| `MONGO_MAX_POOL_SIZE` | No | Positive integer; default `100` | Maximum PyMongo connections per application process. Size this with `API_WORKERS` and MongoDB capacity. |
| `MONGO_MIN_POOL_SIZE` | No | Non-negative integer; default `0` | Minimum idle PyMongo connections retained per process. |
| `MONGO_CONNECT_TIMEOUT_MS` | No | Milliseconds; default `10000` | Maximum time allowed to establish a MongoDB socket. |
| `MONGO_SERVER_SELECTION_TIMEOUT_MS` | No | Milliseconds; default `30000` | Maximum time allowed to find a suitable replica-set member. |
| `MONGO_WAIT_QUEUE_TIMEOUT_MS` | No | Milliseconds; default `10000` | Maximum wait for a pooled connection before failing the request. |
| `MONGO_READ_CONCERN_LEVEL` | No | MongoDB read-concern level; default `majority` | Consistency level used by application database reads. |
| `MONGO_WRITE_CONCERN_W` | No | `majority` or an acknowledgement count; default `majority` | Replica acknowledgement required for application writes. |
| `MONGO_WRITE_CONCERN_JOURNAL` | No | `1` or `0`; default `1` | Requires acknowledged writes to reach the journal. |
| `COYOTE3_MONGO_DATA_HOST_ROOT` | Self-hosted MongoDB | Absolute host path | Persistent host directory bind-mounted at `/data/db`. |
| `COYOTE3_MONGO_BACKUP_HOST_ROOT` | Self-hosted MongoDB | Absolute host path | Host backup directory bind-mounted at `/backup`. |
| `COYOTE3_MONGO_KEYFILE_HOST_PATH` | Self-hosted MongoDB | Absolute host path | Replica-set keyfile used for member authentication. |
| `COYOTE3_MONGO_NETWORK` | Optional Docker MongoDB | Docker network name | Network owned by the independently deployed MongoDB stack. Application services do not join it. |
| `MONGO_REPLICA_SET_NAME` | Self-hosted MongoDB | Replica-set identifier | Persistent MongoDB replica-set name, normally `coyote3-rs`. |
| `MONGO_REPLICA_MEMBER_HOST` | Self-hosted MongoDB | `host:port` | Stable member address stored in replica-set metadata. It must resolve from both MongoDB and application containers. |
| `COYOTE3_MONGO_PORT` | Optional Docker MongoDB | Host port | Host port published by the independently deployed MongoDB container. It is not used by the application when `MONGO_URI` targets another MongoDB service. |
| `COYOTE3_MONGO_BIND_ADDRESS` | Optional Docker MongoDB | Host IP address | Host interface used when publishing MongoDB's port. The application still connects only through `MONGO_URI`. |
| `CACHE_REQUIRED` | No | `1` or `0` | Requires Redis at startup when `1` (default). Set `0` only to allow an intentional degraded no-op cache when Redis is unavailable. |
| `CACHE_REDIS_CONNECT_TIMEOUT` | No | Seconds | Redis connection timeout. |
| `CACHE_REDIS_SOCKET_TIMEOUT` | No | Seconds | Redis socket timeout. |
| `DASHBOARD_SUMMARY_CACHE_TTL_SECONDS` | No | Seconds; default `60` | Hot-cache lifetime for dashboard summaries. |
| `DASHBOARD_SUMMARY_SNAPSHOT_MAX_AGE_SECONDS` | No | Seconds; default `300` | Maximum accepted dashboard snapshot age. |
| `DASHBOARD_SUMMARY_SNAPSHOT_TTL_SECONDS` | No | Seconds; default `604800` | Persistent dashboard snapshot retention. |
| `API_WORKERS` | No | Positive integer; supported default `1` | Uvicorn process count per API container. The built-in Prometheus counters are process-local, so the supported deployment uses one process per container. Scale with additional API containers only when the external monitoring stack aggregates each instance separately. |
| `APP_DNS` | No | DNS server IP | Optional Docker DNS override for restricted center networks. |
| `API_SESSION_COOKIE_NAME` | No; default `coyote3_api_session` | Cookie name | Browser API session cookie name. Override it when multiple mounted environments share one browser origin. |
| `API_SESSION_TTL_SECONDS` | No | Seconds; default `43200` | Browser API session lifetime. |
| `API_SESSION_COOKIE_SAMESITE` | No | `lax`, `strict`, or `none`; default `lax` | Browser session cookie SameSite policy. |
| `AUDIT_RETENTION_DAYS` | No | Days; default `730` | Audit event retention window. |
| `LOG_FILE_ENABLED` | No | `1` or `0`; default `1` | Enables on-disk JSONL logs in addition to stdout. |
| `LOG_RETENTION_DAYS` | No | Days; default `30` | Disk log retention window. |
| `LOG_GZIP_AFTER_DAYS` | No | Days; default `1` | Age after which nightly maintenance gzips old logs. |
| `LOG_LEVEL` | No | Python logging level | Minimum runtime log level. |
| `COYOTE3_LOGS_HOST_ROOT` | Yes | Absolute host path | Shared host log directory bind-mounted at `/app/logs` in the API, worker, and beat containers. |
| `COYOTE3_UID` | No | Positive integer; default `10001` | Numeric UID used by application containers. The data and log host roots must be writable by this UID or its configured group. |
| `COYOTE3_GID` | No | Positive integer; default `10001` | Numeric GID used by application containers. Use group ownership when direct UID ownership is unsuitable. |
| `NOTIFICATION_RETENTION_DAYS` | No | Days; default `180` | Notification retention window. |
| `COYOTE3_DATA_HOST_ROOT` | Yes | Host path | Host data root mounted into containers at `/data`. |
| `CELERY_LOG_LEVEL` | No | Logging level | Celery worker log level. |
| `CELERY_WORKER_CONCURRENCY` | No | Positive integer; Compose default `2` | Celery worker process concurrency. |
| `CELERY_TASK_TIME_LIMIT` | No | Seconds; default `7200` | Hard Celery task timeout. |
| `CELERY_TASK_SOFT_TIME_LIMIT` | No | Seconds; default `6900` | Soft Celery task timeout. |
| `CELERY_RESULT_EXPIRES` | No | Seconds; default `86400` | Celery result expiry. |
| `CELERY_WORKER_PREFETCH_MULTIPLIER` | No | Positive integer; default `1` | Celery prefetch control. Use `1` for long ingest tasks. |
| `CELERY_INSPECTION_TIMEOUT_SECONDS` | No | Seconds; default `1.5` | Maximum wait for each Celery worker-inspection request shown in application controls. |
| `COYOTE3_MAINTENANCE_HOUR` | No | `0` to `23`; default `2` | Local hour for scheduled maintenance. |
| `COYOTE3_INGEST_WATCH_ENABLED` | No | `1` or `0` | Enables scheduled watch-folder ingest. |
| `COYOTE3_INGEST_WATCH_FILENAME` | No | File name or glob | Manifest name pattern, for example `coyote3.yaml` or `*.yaml`. |
| `COYOTE3_INGEST_DONE_SUFFIX` | No | File suffix | Suffix applied after successful watch-folder ingest. |
| `COYOTE3_INGEST_FAILED_SUFFIX` | No | File suffix | Suffix applied after failed watch-folder ingest. |
| `COYOTE3_INGEST_WATCH_INTERVAL_SECONDS` | No | Seconds | Beat interval for watch-folder scanning. |
| `COYOTE3_INGEST_WATCH_UPDATE_EXISTING` | No | `1` or `0` | Allows watch ingest to replace an existing sample. |
| `COYOTE3_INGEST_WATCH_INCREMENT` | No | `1` or `0` | Enables incremental naming behavior where supported. |
| `AUTHENTICATION_PROVIDERS` | No | Comma-separated list of implemented providers: `local`, `ldap`, for example `local` or `local,ldap` | Deployment override for login providers displayed by the UI. When omitted, the configured TOML list is used. |
| `LDAP_HOST` | When LDAP is enabled for this deployment | Hostname or URI | LDAP server host. A missing value does not block API startup; an LDAP login returns a configuration error until it is supplied. |
| `LDAP_BASE_DN` | LDAP deployments | Distinguished name | LDAP search base. |
| `LDAP_USER_LOGIN_ATTR` | LDAP deployments | Attribute name, usually `mail` | LDAP login lookup attribute. |
| `LDAP_BINDDN` | LDAP deployments | Distinguished name | LDAP bind identity. |
| `LDAP_SECRET` | LDAP deployments | Secret password | LDAP bind password. |
| `LDAP_USER_DN` | LDAP deployments | Relative distinguished name | User subtree below base DN. |
| `GENS_URI` | No | URL | Optional Gens integration. |
| `IGV_URI` | No | URL | Optional IGV integration. |
| `ONCOKB_PUBLIC_LOOKUPS_ENABLED` | No | `1` or `0` | Enables public OncoKB detail lookups and the administrator-triggered HGNC-backed reference refresh. |
| `ONCOKB_REQUEST_TIMEOUT_SECONDS` | No | Seconds | Timeout for all public OncoKB requests, including the reference refresh. |
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
| `API_RATE_LIMIT_ENABLED` | No | `1` or `0`; default `1` | Enables API rate limiting. |
| `API_RATE_LIMIT_REQUESTS_PER_MINUTE` | No | Positive integer; default `600` | API rate limit threshold. |
| `API_RATE_LIMIT_WINDOW_SECONDS` | No | Seconds; default `60` | API rate limit window. |
| `API_CSRF_ENABLED` | No | `1` or `0`; default `1` | Enforces a per-session CSRF header for cookie-authenticated mutation requests. Keep enabled outside isolated tests. |
| `WEB_RATE_LIMIT_ENABLED` | No | `1` or `0` | Enables public web-route rate limiting. |
| `WEB_RATE_LIMIT_REQUESTS_PER_MINUTE` | No | Positive integer | Web route rate limit threshold. |
| `WEB_RATE_LIMIT_WINDOW_SECONDS` | No | Seconds | Web route rate limit window. |

### Fixed application defaults

The following values are application contracts and are intentionally not
included in the center environment file: the API log service label (`api`),
the Celery queues (`default` and `ingest`), and the public API roots for
OncoKB and ClinPGx. They are defined in the application configuration so every
deployment uses the same supported service behavior.

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
| Redis URLs and Celery broker/result URLs | Internal Compose wiring through the stable `redis` service name, for example `redis://redis:6379/0`. |
| API health path | Fixed endpoint `/api/v1/health`. |
| Documentation/help URL | Derived as `${PUBLIC_BASE_URL}${SCRIPT_NAME}/docs-site/`. |
| Repository and issue links | `api/config/application_metadata.py`; these are repository-owned product links. |
| API session and audit collection names | Fixed internal collections `api_sessions` and `audit_events`. |
| Container data root | Fixed container path `/data`; only the host root is configurable. |
| MANE transcript reference data | The `hgnc_collection` in the configured application database. It supplies MANE and clinical transcript metadata used by transcript selection; no environment variable or filesystem path is required. |

## Timestamp Display

All persisted timestamps are stored as UTC values in MongoDB and audit records.
The React UI converts those timestamps to the configured `LOCAL_TIME_ZONE`
before showing absolute dates, detailed audit timestamps, comment timestamps,
report dates, and admin table dates. Relative labels such as `7 d ago` are
calculated from the same UTC instant.

!!! info "Timezone value"

    Use an IANA timezone name, for example `Europe/Stockholm`. Do not store
    local wall-clock timestamps in MongoDB. If an ingest source emits an ISO
    timestamp without a timezone suffix, Coyote3 treats it as UTC and converts it
    for display.

## Center Contact Configuration

Each `[[contacts]]` entry is rendered as one responsive support card in the
Contact page. A center may provide any number of entries; no application code
or layout setting needs to change when a contact channel is added or removed.

`api/config/center/contact.toml` drives the public Contact page. Edit the
center-owned file in place and deploy it with the application; configuration
paths are intentionally not environment variables.

```toml
[organization]
name = "Coyote3"
department = "Clinical Genomics"

[[contacts]]
label = "Clinical support"
role = "Interpretation and report questions"
phone = "+46 ..."
description = "Questions about interpretation, report content, or clinical review workflow."

[[contacts.people]]
name = "Clinical Support Team"
email = "clinical-support@example.org"

```

!!! info "Organization identity"

    `ORGANIZATION_NAME` is authoritative for the organization display name.
    The contact TOML stores richer public contact details.

!!! tip "Named contacts"

    Add one `[[contacts.people]]` table for each recipient. The Contact and
    About pages render each person on a separate line as `Name (email)`, with
    the complete line linked using `mailto:`. This avoids ambiguous shared
    mailbox strings and keeps each support route readable.

!!! info "Product links"

    Bug reports, feature requests, and support requests are product/repository
    links, not deployment secrets or center settings. They are defined once in
    `api/config/application_metadata.py`; the About page, Contact page, and
    user dropdown receive the same generated links.

## Configuration Boundaries

API-owned configuration lives under `api/config/`:

- `app_config.py` selects runtime settings.
- `constants.py` defines product vocabularies.
- `runtime.py` exposes backend helper functions.
- `center/collections.toml` maps repository collection names.
- `application_metadata.py` stores repository-owned description and codebase links.
- `center/contact.toml` stores center-owned organization, support, hours, and repeatable contact cards.

UI-owned configuration stays under `frontend/`:

- `frontend/vite.config.ts` owns Vite behavior and `SCRIPT_NAME` routing.
- Tailwind and CSS files own presentation tokens.
- `frontend/src/lib/` owns frontend formatting and API helpers.

Clinical rules and collection contracts belong in backend Pydantic contracts and
domain services. The frontend consumes those contracts rather than duplicating
clinical logic.
