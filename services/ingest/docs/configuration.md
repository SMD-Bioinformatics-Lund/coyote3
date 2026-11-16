# Configuration

Submission commands take their API URL, manifest path and credential options
explicitly. Inspect each command's `--help` for its current options. Credentials
must not be committed with manifests or copied into log output. Submission does
not load the application's database credentials.

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
