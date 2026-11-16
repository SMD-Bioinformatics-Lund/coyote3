# Coyote MongoDB adapter

<!-- badges:start -->
![coyote-server: 1.0.0](https://img.shields.io/badge/coyote--server-1.0.0-4F46A5?style=flat) ![Python: >=3.12](https://img.shields.io/badge/Python-%3E%3D3.12-3776AB?style=flat&logo=python&logoColor=white) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

MongoDB repositories, query compilation, record codecs, collection/index contracts
and transactional persistence for Coyote. The adapter depends on the core and ships
with the API in `coyote-server`. Importing the adapter does not import or start the API.

## Documentation

Start with the [adapter guide](docs/README.md).

- [Getting started](docs/getting-started.md): install the server and construct connections.
- [Usage](docs/usage.md): understand its supported workflow.
- [Configuration](docs/configuration.md): supply the inputs the adapter owns.
- [Reference](docs/reference.md): find entry points, interfaces and errors.
- [Development](docs/development.md): edit and test the adapter, then build the server.

## Distribution and component identity

The `coyote-server` distribution contains the `coyote_mongo` and `coyote_api`
namespaces. Its shared version, dependencies and build configuration belong to the
[root pyproject.toml](../../pyproject.toml). This directory retains adapter source,
documentation and tests; its [pyproject.toml](pyproject.toml) configures adapter tests
and coverage. See [CHANGELOG.md](CHANGELOG.md) for adapter component changes.

Badges describe package metadata and technology, not clinical validation.
GNU GPL version 3 only; see [LICENSE.txt](LICENSE.txt) and
[COPYRIGHT.txt](COPYRIGHT.txt) for copyright and affiliation, with additional
notices in [NOTICE.txt](NOTICE.txt).
