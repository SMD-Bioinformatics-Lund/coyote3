# Coyote API and workers

<!-- badges:start -->
![coyote-api: 1.0.0](https://img.shields.io/badge/coyote--api-1.0.0-4F46A5?style=flat) ![Python: >=3.12](https://img.shields.io/badge/Python-%3E%3D3.12-3776AB?style=flat&logo=python&logoColor=white) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

<img src="src/coyote_api/config/assets/coyote-api-logo.svg" alt="Coyote API" width="360">

The HTTP API and worker host for Coyote. It handles authentication, request validation, application composition and packaged host resources. Clinical operations come from the core; MongoDB persistence comes from its adapter.

Backend configuration lives in `src/coyote_api/config/`; begin with `bootstrap.py`
and `runtime_settings.py`. Complete center-file examples are in
`src/coyote_api/config/examples/center/`. See the [configuration guide](docs/configuration.md)
for environment loading and ownership.

The actual synthetic demo files live in
`src/coyote_api/bootstrap/demo_data/clinical_workflows/`, with `setup/`, `raw/`,
`starter/` and `manifests/` directories. They belong to this package because the
API's installation service consumes them. Wheels include the same bundle, so
installation does not depend on a repository checkout. The core and MongoDB
adapter do not own demo installation resources.

## Documentation

Start with the [package guide](docs/README.md).

- [Getting started](docs/getting-started.md): install the package and make a first use.
- [Usage](docs/usage.md): understand its supported workflow.
- [Configuration](docs/configuration.md): supply the inputs this package owns.
- [Reference](docs/reference.md): find entry points, interfaces and errors.
- [Development](docs/development.md): edit, test and build the package.

## Package identity

The distribution is `coyote-api`; the Python namespace is `coyote_api`.
Its version, dependencies and build configuration belong to
[pyproject.toml](pyproject.toml). See [CHANGELOG.md](CHANGELOG.md) for changes.

Badges describe package metadata and technology, not clinical validation.
GNU GPL version 3 only; see [LICENSE.txt](LICENSE.txt) and
[COPYRIGHT.txt](COPYRIGHT.txt) for copyright and affiliation, with additional
notices in [NOTICE.txt](NOTICE.txt).
