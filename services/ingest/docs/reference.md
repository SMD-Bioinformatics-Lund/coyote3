# Reference

| Command | Python module | Responsibility |
| --- | --- | --- |
| `coyote-ingest-submit` | `coyote_ingest.submit` | Upload, journal acceptance, poll and acknowledge. |
| `coyote-ingest-validate` | `coyote_ingest.validate` | Validate a manifest and declared input paths. |
| `coyote-ingest-login` | `coyote_ingest.login` | Authenticate using the HTTP client. |
| `coyote-ingest-worker` | `coyote_ingest.worker` | Run Celery on the configured ingestion queue. |

Each command also supports `python -m` with the listed module. The worker's Celery
application is `coyote_ingest.celery_app:celery_app`.

Task names are owned by `coyote.application.ingest.messages`. API publication and
the worker use the same allowlist:

- `coyote_ingest.tasks.ingest_sample_bundle`
- `coyote_ingest.tasks.insert_collection_document`
- `coyote_ingest.tasks.insert_collection_documents`
- `coyote_ingest.tasks.upsert_collection_document`
- `coyote_ingest.tasks.dispatch_pending_jobs`
- `coyote_ingest.tasks.ingest_watch_directory_once`

Execution messages contain a retained `job_id`, not a submitted clinical payload.
The dispatcher recovers jobs after publication interruption or an expired claim.
It does not invent an alternative write path.

Core interfaces are `IngestJobRunner` and `IngestJobRepository` in
`coyote.application.ingest.worker`, and `ManifestWatcher` and `ManifestWatchSettings`
in `coyote.application.ingest.watcher`. Reusing these workflows
with another persistence or task host requires explicit ports, including an
authorized executor and transaction completion callback. The service's concrete
worker binds these ports to `coyote-server` and its MongoDB adapter.
