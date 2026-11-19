<div align="center" markdown="1">

![Coyote Relay](src/coyote_relay/assets/coyote-relay-logo.svg)

*Pipeline submission tools and ingestion workers for Coyote.*

<!-- badges:start -->
![coyote-relay: 1.0.0](https://img.shields.io/badge/coyote--relay-1.0.0-4F46A5?style=flat) ![Python: >=3.12](https://img.shields.io/badge/Python-%3E%3D3.12-3776AB?style=flat&logo=python&logoColor=white) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

</div>

---

**Documentation:** [Read the guides](docs/README.md)

**Source Code:** [Coyote application workspace](../../README.md)

---

Pipeline submission tools, an optional API extension and a worker service for
Coyote ingestion. Install the base package to validate manifests, authenticate and
submit files to a running API. Install the `api` extra with the server to expose
ingestion routes in its API documentation. Install the `worker` extra to execute
durable ingestion jobs and scan configured manifest directories.

Core owns reusable models, manifest structure, clinical validation, parsing,
clinical writes, job execution and
manifest acknowledgement rules. Relay binds those workflows to CLI, HTTP and Celery
using the host's configured persistence, authentication and audit services. The
server discovers installed routers through the `coyote.api.routers` entry point
and publishes named jobs without importing worker modules. Relay is an optional
server extension and an independently installable distribution, maintained with
Core and the server in this workspace.

## Documentation

- [Getting started](docs/getting-started.md): install submission tools or the worker.
- [Usage](docs/usage.md): submit bundles and monitor durable results.
- [Configuration](docs/configuration.md): provide credentials and host settings.
- [Reference](docs/reference.md): commands, messages and workflow ownership.
- [Development](docs/development.md): editable installation, tests and coverage.

Version and dependencies belong to [pyproject.toml](pyproject.toml). Changes are
listed in [CHANGELOG.md](CHANGELOG.md). Badges describe package metadata, not
clinical validation. GNU GPL version 3 only; see [LICENSE.txt](LICENSE.txt),
[COPYRIGHT.txt](COPYRIGHT.txt) and [NOTICE.txt](NOTICE.txt).
