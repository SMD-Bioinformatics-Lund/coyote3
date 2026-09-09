# Configuration And Environments

## Annotation vocabulary and sample profiles

`reporting.annotation_tumor_types` in `api/config/center/clinical_vocabulary.toml`
maps assay-group identifiers to non-empty tumor descriptors used by the automatic
Tier III annotation generator. Unlisted groups contribute an empty descriptor.
Changes require clinical review and an API/worker restart.

Sample catalog requests default to the deployed environment. The frontend explicitly
sends `profile_scope`; `all` selects all authorized profiles, never bypassing user
scope. The unused `sample_view` query parameter is not part of the request contract.

## Environment Files

Coyote3 uses one copied environment file per deployment environment. It contains
database connections, secrets, storage paths, public URLs, and supported runtime
overrides. Compose wiring stays in the deployment files.

Copy the single template for the environment you are deploying:

```bash
cp deploy/env/example.env .coyote3_dev_env
cp deploy/env/example.env .coyote3_stage_env
cp deploy/env/example.env .coyote3_test_env
cp deploy/env/example.env .coyote3_env
```

Then update the copied file. Local `.coyote3_*_env` files are ignored by git and
must not be committed.

Compose's `--env-file` supplies interpolation values; it does not automatically
pass every variable into every container. The Compose files explicitly forward
runtime settings, use deployment settings for ports and mounts, and supply
frontend build arguments. Recreate affected containers after changing runtime
values; rebuild the production frontend after changing its build-time settings
such as `ENV_NAME`, `SCRIPT_NAME`, `GENS_URI`, or `IGV_DATA_ROOT`. Rebuild the API
image when changing its build-time `COYOTE3_UID` or `COYOTE3_GID`.

MongoDB provisioning values (`MONGO_ROOT_*`, `MONGO_APP_*`, replica-set settings,
and MongoDB storage paths) are used only by `docker-compose.mongo.yml` and its
enabled profiles. They can be omitted from an external-MongoDB deployment's
private environment file. MongoDB users and replica configuration are initialized
only for a new deployment; editing these variables does not rotate existing
database passwords or reconfigure an existing replica set. Connection URIs must
contain the actual credentials and reachable member addresses.

### Minimum deployment values

Most environment variables have supported application or Compose defaults.
Every center must review and set only this core deployment contract:

| Variable | Why it must be supplied |
| --- | --- |
| `COYOTE3_MONGO_URI` | Selects the reachable MongoDB deployment and application credentials. |
| `COYOTE3_DB` | Selects the primary application database explicitly. |
| `IDENTITY_DB` | Selects the dedicated identity and security database explicitly. |
| `KNOWLEDGEBASE_DB` | Selects the dedicated external knowledgebase database explicitly. |
| `BAM_DB` | Selects the BAM-service database explicitly. |
| `SECRET_KEY` | Signs invitation and password-reset action tokens. |
| `INTERNAL_API_TOKEN` | Authenticates trusted internal service requests. |
| `PASSWORD_TOKEN_SALT` | Separates password-token signing from other signed data. |
| `COYOTE3_DATA_HOST_ROOT` | Provides persistent sample, ingest, and report storage. |
| `COYOTE3_REPORTS_HOST_ROOT` | Optionally separates saved report artifacts from ingest storage. |
| `COYOTE3_LOGS_HOST_ROOT` | Provides persistent application log storage. |
| `COYOTE3_APP_NETWORK` | Selects the pre-created Docker network. |
| `PUBLIC_BASE_URL` | Required by Compose for generated public links. |
| `REDIS_PASSWORD` | Authenticates the Compose-managed Redis service and its clients. |

Set `ENV_NAME` explicitly even though a runtime default exists. Set
`SCRIPT_NAME`, organization/time-zone values, LDAP, SMTP, and integration URLs
according to the deployment. Replace all placeholder secrets; the template is
not a ready-to-run production configuration.

## Center-Owned Configuration Files

Environment variables carry deployment wiring and secrets. Center policy is
kept in versioned configuration files under `api/config/center/` so it can be reviewed
as a clinical/configuration change rather than hidden in application code.

| File | Format | Detailed field reference | Purpose |
| --- | --- | --- | --- |
| `center/contact.toml` | TOML | [Contact table](../operations/center_configuration_files.md#contacttoml) | Center-owned organization, support, service-hour, and repeatable contact-card content. |
| `center/clinical_vocabulary.toml` | TOML | [Vocabulary table](../operations/center_configuration_files.md#clinical_vocabularytoml) | Center-owned authentication providers, sample-manifest file keys, required family inputs, and analysis-to-file bindings. Assay groups and sequencing-platform capabilities are fixed software workflow identifiers. |
| `center/clinical_query_policy.toml` | TOML | [Query-policy table](../operations/center_configuration_files.md#clinical_query_policytoml) | Released SNV evidence models plus independent typed CNV, translocation, fusion, and PGX exception scopes. |
| `center/collections.toml` | TOML | [Collection table](../operations/center_configuration_files.md#collectionstoml) | Database and collection names used by the persistence adapter. |
| `center/filter_flag_metadata.yaml` | YAML | [Flag table](../operations/center_configuration_files.md#filter_flag_metadatayaml) | Human-facing variant flag labels, severity, and tooltip descriptions. |

See [Center Configuration Reference](../operations/center_configuration_files.md)
for every file-backed center configuration, its fields, allowed values, owning
workflow, and change protocol. See
[Clinical Vocabulary Configuration](../operations/clinical_vocabulary.md) for
the detailed manifest-key and analysis-binding contract.

Public assay catalog wording and display structure are database-backed center
content. Use the structured **Admin > Public Assay Catalog** builder to edit
it; JSON is available only for portable import and export. It is not a file in
`center/`.

> **Info: One environment selector**
>
>
> `ENV_NAME` is the environment selector. Use values such as `development`,
> `testing`, `staging`, or `production`. Coyote3 does not use separate
> `DEVELOPMENT=1` or `TESTING=1` flags.
>

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

> **Note: Internal service URLs**
>
>
> Redis, Celery broker/result URLs, API health paths, and docs upstream URLs
> are internal service wiring. They are fixed in the application or Compose
> files and are not configured in the center environment file.
>

## Data Mounts

The base Compose stack mounts one center-owned host data root into API, worker,
and beat at `/data`. It does not automatically mount the original host path.
Add input directories in a private Compose override when manifests reference
other absolute paths. See `deploy/compose/docker-compose.storage.example.yml`
for read-only, same-path input mounts.

| Setting | Meaning |
| --- | --- |
| `COYOTE3_DATA_HOST_ROOT` | Host directory mounted by Compose at `/data` in each ingest-capable container. |
| `COYOTE3_REPORTS_HOST_ROOT` | Optional separate host directory mounted at `/data/coyote3/reports`. |
| `/data/coyote3/reports` | Fixed container location for report artifacts. |
| `/data/coyote3/ingest_staging` | Fixed container location for staged async upload jobs. |
| `/data/coyote3/copied_sample_files/yaml` | Fixed container location scanned for ingest manifests. |

Example:

```env
COYOTE3_DATA_HOST_ROOT='/srv/coyote3/data'
COYOTE3_REPORTS_HOST_ROOT='/srv/coyote3/reports'
```

Saved HTML and PDF reports are stored on disk; MongoDB stores report records
and their artifact references. With this example, report artifacts are stored
under `/srv/coyote3/reports` on the host, retaining their report subdirectories.
Create the report directory with write access for the configured application
UID/GID (default `10001:10001`). API, worker, and beat share this mount.

If `COYOTE3_REPORTS_HOST_ROOT` is empty or omitted, the host location remains
`COYOTE3_DATA_HOST_ROOT/coyote3/reports`. When changing an existing deployment,
copy the complete report directory to the new root while report writers are
stopped, preserving permissions and subdirectories, then recreate the containers.
The container path stays unchanged, so stored artifact references remain valid.
Changing the variable does not move existing files. Include this directory in
the center's backup process alongside MongoDB backups.

Pipeline manifests may use paths relative to the manifest or absolute paths
visible inside the ingest containers. A host path is readable only if an
explicit mount exposes it at the declared location. Stored file paths retain
the pipeline's declared references.

> **Info: Container path contract**
>
>
> Report output, upload staging, and watched manifests use `/data/coyote3/...`
> locations. Separate source mounts may be read-only; staging and output mounts
> must remain writable. Configure the same input mounts on API, worker, and beat.
>

## Environment Variable Reference

The table covers every variable in `deploy/env/example.env` plus optional
overrides supported by runtime or deployment configuration. TOML and YAML keys are **not**
environment variables and are documented in the linked center-configuration
tables above.

Some environment variables select database instances rather than duplicate
collection configuration. `COYOTE3_DB` is bound to `[primary]`, `IDENTITY_DB`
to `[identity]`, `KNOWLEDGEBASE_DB` to `[knowledgebase]`, and `BAM_DB` to `[bam]` in
`center/collections.toml`. Physical collection names remain TOML values.

> **Warning: HTTPS session cookies**
>
>
> Session cookies are HTTPS-only whenever the request uses HTTPS. Coyote3
> reads `X-Forwarded-Proto` when it is deployed behind a reverse proxy. Plain
> HTTP remains available only as a local-development fallback and emits an
> API runtime warning. There is no environment variable that can weaken this
> policy in a deployed HTTPS environment.
>

Built-in Mongo-backed knowledgebases are always registered. Their collections
may be empty when a center has not loaded reference data, but repository
registration is not configurable through an environment variable.

| Variable | Required | Expected Value | Purpose |
| --- | --- | --- | --- |
| `ENV_NAME` | Required by Compose | `development`, `testing`, `staging`, or `production` | Selects runtime behavior and labels audit/log context. Set it explicitly in copied env files so operators can identify the target immediately. |
| `COYOTE3_DB` | Deployed environments; local default `coyote3_dev` | MongoDB database name | Environment-specific primary database, independent of the URI path and authSource. |
| `IDENTITY_DB` | Explicit per environment | MongoDB database name | Users, RBAC, sessions, and audit. Never share this namespace between environments on the same deployment; notifications remain in the primary database. |
| `KNOWLEDGEBASE_DB` | Default `coyote3_knowledgebases` | MongoDB database name | Shared platform datasets on `KNOWLEDGEBASE_MONGO_URI`; no per-environment copy unless explicitly configured. |
| `BAM_DB` | Yes | MongoDB database name | BAM-service database used for sample BAM lookups. |
| `ORGANIZATION_NAME` | No; default `Coyote3` | Center/service display name | Used on login, public, contact, and support pages. |
| `LOCAL_TIME_ZONE` | No; default `UTC` | IANA timezone such as `Europe/Stockholm` | Local display timezone for browser-rendered dates and container-local schedules. Database timestamps remain UTC. |
| `SECRET_KEY` | Yes | High-entropy secret | Signs invite and password-reset action tokens. Browser sessions are opaque, server-stored tokens and do not use this value. |
| `INTERNAL_API_TOKEN` | Yes | High-entropy token | Authenticates trusted service-to-service internal API calls through the internal-token header. |
| `PASSWORD_TOKEN_SALT` | Yes | High-entropy salt | Separates invite and password-reset token signing from other application signing operations. |
| `COYOTE3_PORT` | No; compose profile default | Host port | One exposed nginx entrypoint for UI, API, public pages, and docs. |
| `SCRIPT_NAME` | No; default empty | Empty string or `/prefix` | Public URL mount prefix used by browser routing and generated links. |
| `PUBLIC_BASE_URL` | Required by Compose | Public origin without `SCRIPT_NAME` | Origin used for links generated outside an active browser request, such as password reset email links. |
| `COYOTE3_CONTAINER_MEM_LIMIT` | No | Compose memory value; default `2g` | Per-container memory limit. |
| `COYOTE3_CONTAINER_CPU_LIMIT` | No | Compose CPU value; default `2.0` | Per-container CPU limit. |
| `COYOTE3_APP_NETWORK` | Yes | Existing Docker network name | External network shared by the UI, API, worker, scheduler, Redis, documentation, and reverse proxy. Compose requires this network and never creates it. Use one network per deployment environment. |
| `MONGO_ROOT_USERNAME` | Self-hosted MongoDB | Username | MongoDB administrative username used only for database deployment and maintenance. |
| `MONGO_ROOT_PASSWORD` | Self-hosted MongoDB | Secret password | MongoDB administrative password. |
| `MONGO_APP_USER` | Self-hosted MongoDB | Username | Application MongoDB username created during first database initialization. |
| `MONGO_APP_PASSWORD` | Self-hosted MongoDB | Secret password | Application MongoDB password. |
| `COYOTE3_MONGO_URI` | Yes | MongoDB URI | API, worker, and beat MongoDB connection string. It must target a replica set or sharded cluster and include `replicaSet=<name>` for a replica set. |
| `IDENTITY_MONGO_URI` | Defaults to app URI | MongoDB URI | Independent identity endpoint, with its own authentication and replica-set options. |
| `KNOWLEDGEBASE_MONGO_URI` | Defaults to app URI | MongoDB URI | Independent shared knowledgebase endpoint. Prefer a reader account for normal application access. |
| `BAM_MONGO_URI` | Defaults to app URI | MongoDB URI | Independent BAM-service endpoint. |
| `MONGO_URI` | Legacy input only | MongoDB URI | Fallback when the explicit app URI is absent; explicit logical-service URIs take precedence. |
| `MONGO_MAX_POOL_SIZE` | No | Positive integer; default `100` | Maximum PyMongo connections per application process. Size this with `API_WORKERS` and MongoDB capacity. |
| `MONGO_MIN_POOL_SIZE` | No | Non-negative integer; default `0` | Minimum idle PyMongo connections retained per process. |
| `MONGO_CONNECT_TIMEOUT_MS` | No | Milliseconds; default `10000` | Maximum time allowed to establish a MongoDB socket. |
| `MONGO_SERVER_SELECTION_TIMEOUT_MS` | No | Milliseconds; default `30000` | Maximum time allowed to find a suitable replica-set member. |
| `MONGO_WAIT_QUEUE_TIMEOUT_MS` | No | Milliseconds; default `10000` | Maximum wait for a pooled connection before failing the request. |
| `MONGO_READ_CONCERN_LEVEL` | No | MongoDB read-concern level; default `majority` | Consistency level used by application database reads. |
| `MONGO_WRITE_CONCERN_W` | No | `majority` or an acknowledgement count; default `majority` | Replica acknowledgement required for application writes. |
| `MONGO_WRITE_CONCERN_JOURNAL` | No | `1` or `0`; default `1` | Requires acknowledged writes to reach the journal. |
| `COYOTE3_MONGO_DATA_HOST_ROOT` | Self-hosted MongoDB | Absolute host path | Persistent host directory bind-mounted at `/data/db`. |
| `COYOTE3_MONGO_BACKUP_HOST_ROOT` | Only with the optional backup overlay | Existing absolute host directory | Mounted at `/backup` only when `docker-compose.mongo-backup.yml` is included. Omit the variable and overlay when backups are handled externally. |
| `COYOTE3_MONGO_KEYFILE_HOST_PATH` | Self-hosted MongoDB | Absolute host path | Replica-set keyfile used for member authentication. |
| `MONGO_UID`, `MONGO_GID` | Both Mongo Compose profiles | Positive numeric host UID/GID | Required database owner IDs; used by MongoDB, health checks, and initializers in modern and legacy Compose. |
| `KNOWLEDGEBASE_REPLICA_SET_NAME` | Optional `mongo-kb` profile | Replica-set identifier | Independent KB replica-set name, default `coyote3-kb-rs`. |
| `KNOWLEDGEBASE_REPLICA_MEMBER_HOST` | Optional `mongo-kb` profile | `host:port` | Advertised KB member address, default `mongo-kb:27017`. |
| `KNOWLEDGEBASE_MONGO_DATA_HOST_ROOT` | Optional `mongo-kb` profile | Absolute host path | One persistent dbPath for the KB instance, separate from app MongoDB storage. |
| `KNOWLEDGEBASE_MONGO_KEYFILE_HOST_PATH` | Optional `mongo-kb` profile | Secret file path | Member authentication keyfile for the KB replica set. |
| `KNOWLEDGEBASE_MONGO_ROOT_USERNAME`, `KNOWLEDGEBASE_MONGO_ROOT_PASSWORD` | Optional `mongo-kb` profile | Administrative credentials | First-time database provisioning only. |
| `KNOWLEDGEBASE_MONGO_APP_USER`, `KNOWLEDGEBASE_MONGO_APP_PASSWORD` | Optional `mongo-kb` profile | Reader credentials | Normal KB application user, created in admin on first initialization. |
| `MONGO_REPLICA_SET_NAME` | Self-hosted MongoDB | Replica-set identifier | Persistent MongoDB replica-set name, normally `coyote3-rs`. |
| `MONGO_REPLICA_MEMBER_HOST` | Self-hosted MongoDB | `host:port` | Stable member address stored in replica-set metadata. It must resolve from both MongoDB and application containers. |
| `COYOTE3_MONGO_PORT` | Optional Docker MongoDB | Host port | Host port published by the independently deployed MongoDB container. It is not used by the application when `COYOTE3_MONGO_URI` targets another MongoDB service. |
| `COYOTE3_MONGO_BIND_ADDRESS` | Optional Docker MongoDB | Host IP address | Interface used to publish app MongoDB's port; service URIs remain independently configured. |
| `CACHE_REQUIRED` | No | `1` or `0` | Requires Redis at startup when `1` (default). Set `0` only to allow an intentional degraded no-op cache when Redis is unavailable. |
| `CACHE_REDIS_CONNECT_TIMEOUT` | No | Seconds | Redis connection timeout. |
| `CACHE_REDIS_SOCKET_TIMEOUT` | No | Seconds | Redis socket timeout. |
| `REDIS_PASSWORD` | Required by Compose | Unique URL-safe secret; generate with `openssl rand -hex 32` | Redis authentication and embedded credentials in cache, broker, and result URLs. Not an application account password. |
| `DASHBOARD_METRIC_CACHE_TTL_SECONDS` | No | Seconds; default `300` | Freshness limit for each independently cached dashboard metric. Celery Beat schedules background refreshes at half this interval, with a minimum interval of 30 seconds. |
| `DASHBOARD_METRIC_CACHE_RETENTION_SECONDS` | No | Seconds; default `3600` | Redis retention for unused dashboard metric entries. This must be at least as long as the freshness limit. |
| `API_WORKERS` | No | Positive integer; supported default `1` | Uvicorn process count per API container. The built-in Prometheus counters are process-local, so the supported deployment uses one process per container. Scale with additional API containers only when the external monitoring stack aggregates each instance separately. |
| `FORWARDED_ALLOW_IPS` | Review for proxied deployments | Trusted proxy IPs or CIDRs; default `127.0.0.1` | Uvicorn's trust list for forwarded headers. Configure the actual ingress proxy or dedicated proxy network; do not use `*`. |
| `COYOTE3_NGINX_PUBLIC_SCHEME` | Review for TLS deployments | `http` or `https`; default `http` | Scheme emitted by Nginx in `X-Forwarded-Proto`; `https` also enables HSTS. This does not configure TLS itself. Use `https` only behind a TLS-enforcing entrypoint. |
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
| `NOTIFICATION_RETENTION_DAYS` | No | Days; default `180` | Personal/workflow notification visibility window; records are retained. Broadcast expiry is set by its sender. |
| `COYOTE3_DATA_HOST_ROOT` | Yes | Host path | Host data root mounted into containers at `/data`. |
| `COYOTE3_REPORTS_HOST_ROOT` | No | Host path | Writable report artifact root mounted at `/data/coyote3/reports`; empty or omitted uses `COYOTE3_DATA_HOST_ROOT/coyote3/reports`. |
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
| `AUTHENTICATION_PROVIDERS` | No | Comma-separated list of implemented providers: `local`, `ldap`, for example `local` or `local,ldap` | Login-provider override; Compose defaults to `local,ldap`. A host-run process without this setting uses the configured TOML list. |
| `LDAP_HOST` | When LDAP is enabled for this deployment | Hostname or URI | LDAP server host. A missing value does not block API startup; an LDAP login returns a configuration error until it is supplied. |
| `LDAP_PORT` | No | Empty or port `1`-`65535` | Overrides a URI port. When empty, uses the URI port or defaults to 389 for LDAP and 636 for LDAPS. |
| `LDAP_USE_SSL` | No | Boolean; default `0` | Implicit TLS from connection establishment. An `ldaps://` host also selects this mode. |
| `LDAP_USE_TLS` | No | Boolean; default `1` | StartTLS before search-account and user binds on a non-LDAPS connection. Ignored when implicit TLS is selected. |
| `LDAP_CONNECT_TIMEOUT` | No | Positive seconds; default `10` | Bounds connection establishment and socket receive waits. |
| `LDAP_VERIFY_CERT` | No | Boolean; default `1` | Set `0` to disable server certificate and hostname verification. TLS encryption remains controlled by `LDAP_USE_TLS` and `LDAP_USE_SSL`. |
| `LDAP_CA_CERTS_FILE` | No | Empty or container-visible PEM CA bundle path | Empty uses system CA trust. A center-issued CA bundle must be mounted read-only into the API container. Used when certificate verification is enabled. |
| `LDAP_BASE_DN` | LDAP deployments | Distinguished name | Complete LDAP search base, including any intended user subtree. |
| `LDAP_USER_LOGIN_ATTR` | LDAP deployments | Attribute name, usually `mail` | LDAP login lookup attribute. |
| `LDAP_BINDDN` | Directory search with a service account | Distinguished name | Read-only search-account identity; configure together with `LDAP_SECRET`, or leave both empty for anonymous search if the directory permits it. |
| `LDAP_SECRET` | When `LDAP_BINDDN` is supplied | Secret password | Directory search-account password, not the password entered by the person logging in. |
| `GENS_URI` | No | URL | Optional Gens integration. |
| `IGV_URI` | No | URL | Optional IGV integration. |
| `IGV_DATA_ROOT` | No | Workstation path prefix | Root prepended to ASP-resolved relative paths, for example `/R:` or `/mnt/alignments`; independent of API mounts. Assay folders and BED files are configured in ASP `igv`. |
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
| `SMTP_FROM_EMAIL` | Mail deployments | Email address; default `no-reply@coyote3.local` | Unmonitored sender for account invitations and general messages. |
| `SMTP_SECURITY_FROM_EMAIL` | Mail deployments | Email address; default `security@coyote3.local` | Unmonitored sender for password and account-security messages. |
| `SMTP_INFO_FROM_EMAIL` | Mail deployments | Email address; default `info@coyote3.local` | Unmonitored sender for broadcasts. Configure all senders on a relay-authorized center domain in production. |
| `SMTP_FROM_NAME` | Mail deployments | Display name | Sender display name. |
| `PASSWORD_TOKEN_TTL_SECONDS` | No | Seconds | Invite/reset token lifetime. |
| `API_RATE_LIMIT_ENABLED` | No | `1` or `0`; default `1` | Enables API rate limiting. |
| `API_RATE_LIMIT_REQUESTS_PER_MINUTE` | No | Positive integer; default `600` | API rate limit threshold. |
| `API_RATE_LIMIT_WINDOW_SECONDS` | No | Seconds; default `60` | API rate limit window. |
| `API_CSRF_ENABLED` | No | `1` or `0`; default `1` | Enforces a per-session CSRF header for cookie-authenticated mutation requests. Keep enabled outside isolated tests. |

API request throttling uses the `API_RATE_LIMIT_*` settings. There is no separate
application limiter for frontend pages or documentation assets; configure that
policy at the ingress proxy. Configure center DNS through Docker or a private
Compose service `dns` override rather than an application environment variable.

The browser UI and API are served from the same origin. The API does not configure
CORS response headers or an environment-controlled cross-origin allowlist.
`PUBLIC_BASE_URL` controls generated links, not browser cross-origin permissions.

### LDAP Authentication

LDAP login requires an existing active Coyote3 account in the configured identity
database. Its `auth_type` must include `ldap`; the login identifier is matched to
the account's email. The directory verifies the password, while Coyote3 owns role,
permission, assay, and environment assignments. LDAP login does not automatically
create an account or copy directory groups into roles.

1. Enable `ldap` in `AUTHENTICATION_PROVIDERS` alongside `local` when local recovery
   accounts are needed.
2. Configure `LDAP_HOST`, the complete `LDAP_BASE_DN`, and `LDAP_USER_LOGIN_ATTR`.
   The default attribute is `mail`; another attribute must contain the same login
   identifier as the Coyote3 account email. To restrict search to a subtree, use
   a full base such as `ou=people,dc=example,dc=org`. A search-account DN is not a
   substitute for the search base.
3. Supply both `LDAP_BINDDN` and `LDAP_SECRET` for service-account lookup, or leave
   both empty only when anonymous searches are supported by the directory.
4. Select a transport and configure CA trust. Recreate the API after changing
   configuration. Setting a CA path does not mount the file into the container.

| Transport | `LDAP_HOST` example | `LDAP_USE_SSL` | `LDAP_USE_TLS` | Default port |
| --- | --- | --- | --- | --- |
| LDAP with StartTLS | `ldap://directory.example.org` | `0` | `1` | 389 |
| LDAPS | `ldaps://directory.example.org` | `1` | `0` | 636 |

Both transport flags accept `1`, `true`, `yes`, or `on` for true, and `0` or
`false` for false. LDAPS takes precedence and never attempts a second StartTLS
upgrade. With a plain LDAP host and both flags disabled, binds are unencrypted;
do not use that configuration for production credentials.

The API searches with an escaped equality filter, requires exactly one matching
entry, and then binds using its DN and the submitted password. Missing or ambiguous
entries, failed binds, timeouts, and LDAP errors deny login. Searches and binds are
read-only; automatic referrals are disabled so credentials are not forwarded to
another directory endpoint. Connections are unbound after use. Directory passwords
are not stored in Coyote3.

By default, TLS verifies the server certificate and hostname using system trust or
`LDAP_CA_CERTS_FILE`. A private directory CA must be trusted by the API container;
a client certificate is not required merely to verify the server. Set
`LDAP_VERIFY_CERT=0` for an explicit deployment exception. This retains configured
TLS encryption but disables certificate-chain, expiry, and hostname checks, so the
directory server's identity is not verified. See the
[ldap3 transport reference](https://ldap3.readthedocs.io/en/latest/ssltls.html)
for the underlying TLS behavior.

Before enabling LDAP for users, verify a valid login, an incorrect password,
an unregistered account, an inactive account, and a certificate-trust failure in
the target deployment. Automated tests use a synthetic in-memory directory and
mocked transport failures; they do not establish center network or CA readiness.

### Fixed application defaults

The following values are application contracts and are intentionally not
included in the center environment file: the API log service label (`api`),
the Celery queues (`default` and `ingest`), and the public API roots for
OncoKB and ClinPGx. They are defined in the application configuration so every
deployment uses the same supported service behavior.

> **Tip: Generating secrets**
>
>
> Generate each secret independently. A practical local command is
> `openssl rand -hex 32`. Use longer token-safe values if your center policy
> requires them. Do not reuse the same value across environments.
>

## Values Not Stored In Env Files

The following values are intentionally derived or internal:

| Value | Source |
| --- | --- |
| Application version | `api/version.py`; compose wrappers export this transiently for image names. |
| Git commit and build time | Build metadata injected by CI or compose wrappers, not hand-edited env values. |
| Redis URLs and Celery broker/result URLs | Internal Compose wiring through `redis`: cache uses database 0, broker database 1, and task results database 2. |
| API health path | Fixed endpoint `/api/v1/health`. |
| Documentation/help URL | Derived as `${PUBLIC_BASE_URL}${SCRIPT_NAME}/docs-site/`. |
| Repository and issue links | `api/config/application_metadata.py`; these are repository-owned product links. |
| API session and audit collection names | The `api_sessions_collection` and `audit_events_collection` mappings under `[identity]` in `center/collections.toml`. Both collections are stored in `IDENTITY_DB`. |
| Container data root | Fixed container path `/data`; only the host root is configurable. |
| MANE transcript reference data | The `hgnc_collection` in the configured application database. It supplies MANE and clinical transcript metadata used by transcript selection; no environment variable or filesystem path is required. |

## Timestamp Display

All persisted timestamps are stored as UTC values in MongoDB and audit records.
The React UI converts those timestamps to the configured `LOCAL_TIME_ZONE`
before showing absolute dates, detailed audit timestamps, comment timestamps,
report dates, and admin table dates. Relative labels such as `7 d ago` are
calculated from the same UTC instant.

> **Info: Timezone value**
>
>
> Use an IANA timezone name, for example `Europe/Stockholm`. Do not store
> local wall-clock timestamps in MongoDB. If an ingest source emits an ISO
> timestamp without a timezone suffix, Coyote3 treats it as UTC and converts it
> for display.
>

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

> **Info: Organization identity**
>
>
> `ORGANIZATION_NAME` is authoritative for the organization display name.
> The contact TOML stores richer public contact details.
>

> **Tip: Named contacts**
>
>
> Add one `[[contacts.people]]` table for each recipient. The Contact and
> About pages render each person on a separate line as `Name (email)`, with
> the complete line linked using `mailto:`. This avoids ambiguous shared
> mailbox strings and keeps each support route readable.
>

> **Info: Product links**
>
>
> Bug reports, feature requests, and support requests are product/repository
> links, not deployment secrets or center settings. They are defined once in
> `api/config/application_metadata.py`; the About page, Contact page, and
> user dropdown receive the same generated links.
>

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
