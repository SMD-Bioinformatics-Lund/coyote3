# Architecture

The base `coyote-relay` distribution depends on `coyote-core` and
`coyote-pyclient`. Submission tools use the core contracts to validate manifests
and the HTTP API to submit work. They do not need database credentials or server
implementation imports.

The `worker` extra adds `coyote-server`, which contains the API host and MongoDB
adapter. The ingestion process reuses that host's reviewed configuration,
restricted worker identity, credential revalidation, persistence and audit
composition. The server has no required Relay dependency and publishes task names
without importing worker code.

The `api` extra also adds `coyote-server`. Installing Relay alongside that server
registers its routers through the `coyote.api.routers` entry-point group. At startup,
the API loads installed routers and includes their endpoints in OpenAPI. Without
Relay, those ingestion routes are absent. HTTP authentication, CSRF, permission and
assay/environment checks remain enforced by the server's existing dependencies.
An invalid installed extension stops application creation instead of being silently
ignored.

| Owner | Responsibility |
| --- | --- |
| Core | Parsers, ingestion rules, clinical writes, durable job lifecycle and stable manifest acknowledgement. |
| Relay | CLI connection configuration, ingestion HTTP routes, Celery entry points, scan locking and worker composition. |
| API server | HTTP authentication, extension discovery, live task controls, host configuration and beat scheduling. |
| MongoDB adapter | Durable job persistence, fenced leases and write transactions. |

API publication uses message names from the core allowlist and sends only a job
identifier. A worker reads the retained job, checks live task controls, claims an
exclusive lease and invokes the authorized core operation. Managed credentials
are revalidated before writes. The job completion callback runs in the same
transaction as the ingested data. Duplicate delivery recovers the stored result.

`IngestJobRunner` depends on the `IngestJobRepository` protocol and injected host
callbacks. It classifies failures using the host's classifier, retains failed
input for retry, and removes staging only after a confirmed successful result.
`ManifestWatcher` receives explicit immutable settings and parsing, submission,
execution and audit callbacks. It leaves changed, busy, disabled or temporarily
failed manifests available for another scan. The host owns filesystem locking;
the core owns the acknowledgement decision.

These interfaces allow another worker transport or persistence host without
adding a database dependency to core. A replacement host must still implement
the authorization, lease fencing and transaction-completion guarantees; merely
calling parsers is not a complete ingestion service.
