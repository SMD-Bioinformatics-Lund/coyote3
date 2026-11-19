# Packages and integrations

<!-- badges:start -->
![Coyote4: 4.0.0](https://img.shields.io/badge/Coyote4-4.0.0-4F46A5?style=flat) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

Use the HTTP API to connect another application. Use core operations only when
building a trusted host that supplies authentication, authorization and storage.
For a full Coyote installation, follow the [installation guide](../deployment/README.md).

## Application packages

| Package | Responsibility | Documentation |
| --- | --- | --- |
| Coyote Core | Shared models, validation, analysis and reporting workflows | [Coyote Core guide](../../core/docs/README.md) |
| Server | FastAPI host and MongoDB adapter, distributed together | [API guide](../../api/docs/README.md), [MongoDB guide](../../adapters/mongo/docs/README.md) |
| Atlas | HGNC/VEP reference resources and publication | [Atlas guide](../../services/atlas/docs/README.md) |
| Demo | Synthetic data and installation in isolated targets | [Demo guide](../../services/demo/docs/README.md) |
| Frontend | React review and administration interface | [Frontend guide](../../frontend/docs/README.md) |

## Coyote Relay

Relay provides pipeline submission commands, ingestion routes and workers. The
application installs a reviewed Git revision. Its source, CLI options and tests
are maintained in a separate repository.

[Relay documentation](https://github.com/SMD-Bioinformatics-Lund/coyote-relay/blob/dev/docs/README.md)

## Coyote pyClient

pyClient provides synchronous and asynchronous Python access to a running Coyote
API for external scripts, notebooks and applications. It is maintained separately
and is not installed by the Coyote application.

[pyClient documentation](https://github.com/SMD-Bioinformatics-Lund/coyote-pyclient/blob/dev/docs/README.md)

## Develop across packages

- [Editable development with uv](uv-development.md): prepare the workspace and run local services.
- [Application operations](application-core.md): supply trusted host capabilities to core.
- [Package boundaries](package-boundaries.md): understand ownership and dependencies.
- [Version compatibility](compatibility.md): select and build compatible releases.
