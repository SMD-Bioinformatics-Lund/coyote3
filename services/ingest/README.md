# Coyote Ingest

<!-- badges:start -->
![coyote-ingest: 1.0.0](https://img.shields.io/badge/coyote--ingest-1.0.0-4F46A5?style=flat) ![Python: >=3.12](https://img.shields.io/badge/Python-%3E%3D3.12-3776AB?style=flat&logo=python&logoColor=white) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

Submission tools and a worker service for Coyote ingestion. Install the base package
to validate manifests, authenticate and submit files to a running API. Install the
`worker` extra on the application host to execute durable ingestion jobs and scan
configured manifest directories.

The core package owns parsing, validation, clinical writes, job execution and
manifest acknowledgement rules. This package binds those workflows to CLI, Celery
and the server's configured persistence, authentication and audit services. The
server publishes named jobs without importing this package.

## Documentation

Start with the [ingestion guide](docs/README.md).

- [Getting started](docs/getting-started.md): install submission tools or the worker.
- [Usage](docs/usage.md): submit bundles and monitor durable results.
- [Configuration](docs/configuration.md): provide credentials and host settings.
- [Reference](docs/reference.md): commands, messages and workflow ownership.
- [Development](docs/development.md): editable installation, tests and coverage.

Version and dependencies belong to [pyproject.toml](pyproject.toml). Changes are
listed in [CHANGELOG.md](CHANGELOG.md). Badges describe package metadata, not
clinical validation. GNU GPL version 3 only; see [LICENSE.txt](LICENSE.txt),
[COPYRIGHT.txt](COPYRIGHT.txt) and [NOTICE.txt](NOTICE.txt).
