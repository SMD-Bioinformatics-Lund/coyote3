# Changelog

## 1.0.0

- Name the package Coyote Relay, with its own transparent SVG logo.
- Configure API submissions through `COYOTE_RELAY_*` variables or CLI options.
- Register authenticated ingestion routes in the API and its OpenAPI documentation
  when installed alongside the server.
- Independently installable ingestion submission, validation and login commands.
- Optional worker installation using the configured server and MongoDB adapter.
- Core-owned durable execution and manifest scanning through explicit host ports.
- Package-owned worker, submission and smoke tests; GPL-3.0-only licensing.

Worker messages use `coyote_relay.tasks.*`. Drain the previous ingestion worker
and broker queue before upgrading. Do not delete durable ingestion jobs: the new
dispatcher recovers retained pending or expired jobs using their existing IDs.
The old `coyote_api.tasks.ingest.*` and `coyote_ingest.tasks.*` message names are not registered.
