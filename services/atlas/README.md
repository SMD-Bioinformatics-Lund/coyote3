![Coyote Atlas](src/coyote_atlas/assets/coyote-atlas-logo.svg)

<!-- badges:start -->
![coyote-atlas: 1.0.0](https://img.shields.io/badge/coyote--atlas-1.0.0-4F46A5?style=flat) ![Python: >=3.12](https://img.shields.io/badge/Python-%3E%3D3.12-3776AB?style=flat&logo=python&logoColor=white) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

Coyote Atlas owns the HGNC gene snapshot, Ensembl VEP metadata and associated
diagrams distributed with Coyote. Its manifest records dataset identities,
source evidence, record counts and SHA-256 hashes. Offline tools inspect and
validate the bundle without a server or database.

The optional API integration plans and installs the reviewed bundle through the
server's existing administrator authorization, audit and preservation rules.
Installation is explicit; package imports and application startup do not write
reference data.

From the repository root:

```bash
uv sync --all-packages
.venv/bin/coyote-atlas inspect
.venv/bin/coyote-atlas validate
```

For an independent installation, use the [reviewed wheel instructions](docs/getting-started.md#install-from-release-wheels).
These commands do not assume that Coyote packages have been published on PyPI.

See [installation](docs/getting-started.md), [usage](docs/usage.md),
[configuration](docs/configuration.md), [architecture](docs/architecture.md),
[reference](docs/reference.md) and [development](docs/development.md).

First-party code is GPL-3.0-only. Bundled third-party resources retain their
source notices and terms; see [copyright](COPYRIGHT.txt), [notice](NOTICE.txt)
and the [Ensembl reference notice](src/coyote_atlas/data/reference/NOTICE.txt).
