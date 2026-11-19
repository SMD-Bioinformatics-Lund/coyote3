# Reference

| Command | Python module | Responsibility |
| --- | --- | --- |
| `coyote-relay-submit` | `coyote_relay.submit` | Upload, journal acceptance, poll and acknowledge. |
| `coyote-relay-validate` | `coyote_relay.validate` | Validate a manifest and declared input paths. |
| `coyote-relay-login` | `coyote_relay.login` | Authenticate using the HTTP client. |
| `coyote-relay-worker` | `coyote_relay.worker` | Run Celery on the configured ingestion queue. |

Each command also supports `python -m` with the listed module. The worker's Celery
application is `coyote_relay.celery_app:celery_app`.

## API extension

The `coyote.api.routers` entry-point group registers `relay` with the factory
`coyote_relay.api:routers`. The factory imports HTTP dependencies only when the
server loads it. The base CLI remains usable without FastAPI or the server.

Installed routes retain their `/api/v1/internal/ingest/` URLs. Their contracts and
permissions appear in the running server's OpenAPI reference. A broken or
conflicting installed extension prevents API startup instead of silently omitting
ingestion functionality.

## Durable tasks

Task names are owned by `coyote.application.ingest.messages`. API publication and
the worker use the same allowlist:

- `coyote_relay.tasks.ingest_sample_bundle`
- `coyote_relay.tasks.insert_collection_document`
- `coyote_relay.tasks.insert_collection_documents`
- `coyote_relay.tasks.upsert_collection_document`
- `coyote_relay.tasks.dispatch_pending_jobs`
- `coyote_relay.tasks.ingest_watch_directory_once`

Execution messages contain a retained `job_id`, not a submitted clinical payload.
The dispatcher recovers jobs after publication interruption or an expired claim.
It does not invent an alternative write path.

Core interfaces are `IngestJobRunner` and `IngestJobRepository` in
`coyote.application.ingest.worker`, and `ManifestWatcher` and `ManifestWatchSettings`
in `coyote.application.ingest.watcher`. Reusing these workflows
with another persistence or task host requires explicit ports, including an
authorized executor and transaction completion callback. The service's concrete
worker binds these ports to `coyote-server` and its MongoDB adapter.
