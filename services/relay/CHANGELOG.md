# Changelog

## v1.0.0

- Use core as the single owner of reusable models and manifest validation; the
  base install supports structural checks and `--clinical` without reporting or
  alignment dependencies.
- Maintain Relay with Core and server in the application workspace and shared
  lockfile, while retaining its independently installable wheel and submission CLI.
- Use HTTPX directly without installing the application Python client.
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
