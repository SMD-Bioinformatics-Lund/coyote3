# Changelog

## 1.0.0

- Independently installable ingestion submission, validation and login commands.
- Optional worker installation using the configured server and MongoDB adapter.
- Core-owned durable execution and manifest scanning through explicit host ports.
- Package-owned worker, submission and smoke tests; GPL-3.0-only licensing.

Worker messages use `coyote_ingest.tasks.*`. Drain the previous ingestion worker
and broker queue before upgrading. Do not delete durable ingestion jobs: the new
dispatcher recovers retained pending or expired jobs using their existing IDs.
The old `coyote_api.tasks.ingest.*` message names are not registered.
