# Configuration

Relay's login and submission commands read only their own connection variables and
explicitly selected credential variables. They do not discover application environment files or load database
credentials. A process manager, shell or pipeline supplies the environment.

Explicit command-line values take precedence over environment values. The API URL
is required; there is no implicit localhost destination. Include the deployment's
mount prefix, but not `/api/v1`.

| Environment variable | CLI option | Used by |
| --- | --- | --- |
| `COYOTE_RELAY_API_URL` | `--base-url` | Login and submission |
| `COYOTE_RELAY_AUTH` | `--auth` | Submission: `internal`, `bearer` or `ingest`; default `internal` |
| `COYOTE_RELAY_TOKEN` | `--token`, `--token-file`, or `--token-env` | Token login and submission |
| `COYOTE_RELAY_USERNAME` | `--username` | Password login |
| `COYOTE_RELAY_PASSWORD` | `--password` or `--password-env` | Password login |
| `COYOTE_RELAY_PROVIDER` | `--provider` | Password login: `local` or `ldap` |
| `COYOTE_RELAY_CA_BUNDLE` | `--ca-bundle` | Login and submission using a center's trusted CA file |

The credential source options are mutually exclusive. `--token-env NAME` and
`--password-env NAME` select exactly that variable; a missing selected value never
falls back to another credential. Without an explicit token source, both commands
read `COYOTE_RELAY_TOKEN`. Existing deployment variable names can be selected
explicitly, for example `--auth bearer --token-env API_BEARER_TOKEN`.

Passwords and tokens must not be committed, included in manifests or copied into
logs. Prefer environment variables or `--token-file` over literal credential
arguments, which can appear in shell history and process listings. Login prints a
session token only when `--print-token` is explicitly requested. Submission keeps
credentials out of its receipts and curl argument list.

HTTP and HTTPS application URLs are supported. URLs containing credentials, query
strings or fragments are rejected. HTTPS certificate verification remains enabled;
`--ca-bundle` supplies trusted certificates rather than disabling verification.

## Worker configuration

The optional worker uses the server configuration loader and its existing
environment variables. It does not create another environment discovery mechanism
or second set of database defaults. In particular, configure:

| Setting | Purpose |
| --- | --- |
| `CELERY_BROKER_URL` | Broker used by API, beat and workers. |
| `CELERY_RESULT_BACKEND` | Celery result backend. |
| `CELERY_TASK_TIME_LIMIT` | Worker limit used when deriving durable lease duration. |
| `COYOTE4_INGEST_WATCH_ENABLED` | Schedule directory scans from server beat. |
| `ENV_NAME` | Select the environment's mounted storage directory. |
| `COYOTE4_INGEST_WATCH_FILENAME` | Manifest basename discovered by the watcher. |
| `COYOTE4_INGEST_WATCH_LOCK_PATH` | Host lock preventing overlapping scans. |

The ingestion queue name comes from the server factory default
`runtime.CELERY_INGEST_QUEUE`; it is not an environment-variable override. The
watch directory is derived by the server as
`/data/coyote4_<environment>/copied_sample_files/yaml`, using its normalized
environment name, for example `production` becomes `prod`.

The worker also needs the server's explicit MongoDB endpoint/name pairs, runtime
paths and center configuration. Its service account must have the same required
ingestion capabilities as the previous worker deployment. Files referenced by
manifests must be readable from the worker's mounted paths.

Live application task controls remain authoritative for `sample_ingest` and
`collection_writes`. Disabling a family leaves accepted work pending. The worker
does not bypass the control or acknowledge a disabled manifest.
