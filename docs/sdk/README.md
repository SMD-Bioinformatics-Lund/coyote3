# Python packages

<!-- badges:start -->
![Coyote4: 4.0.0](https://img.shields.io/badge/Coyote4-4.0.0-4F46A5?style=flat) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

Coyote combines four local Python distributions with the independently maintained
`coyote-relay` Git dependency. The Python client is maintained separately for external integrations;
it is not installed by the application.

| Package | Purpose |
| --- | --- |
| `coyote-core` | Framework-independent clinical rules, contracts and application operations |
| `coyote-server` | Separate API and Mongo components: HTTP, authentication, maintenance, queries and persistence |
| `coyote-pyclient` | Synchronous and asynchronous clients for a running API |
| `coyote-relay` | Pipeline submission commands and ingestion workers using core workflows |
| `coyote-atlas` | Reference bundles, validation and explicit HGNC/VEP publication |
| `coyote-demo` | Synthetic datasets and guarded installation for isolated demonstrations |

## Choose the Python interface

Use the [HTTP client](python-client.md) for external integrations. Use the
[core](core.md) to build a trusted host with explicit repository and authorization
capabilities. Installing the core does not start a server or connect to MongoDB.

Choose a guide for your task:

- [Call a running API from Python](python-client.md).
- [Develop the application locally with editable packages](uv-development.md).
- [Install release wheels](server-installation.md).
- [Implement a host using core operations](application-sdk.md).
- [Understand package dependencies](package-boundaries.md) or
  [check release compatibility](compatibility.md).

## Package-owned documentation

Use the individual guides for installation, usage, configuration, interfaces and
package development: [core](../../core/docs/README.md),
[API](../../api/docs/README.md), [MongoDB](../../adapters/mongo/docs/README.md) and
[HTTP client](https://github.com/SMD-Bioinformatics-Lund/coyote-pyclient/blob/dev/docs/README.md), and
[ingestion service](https://github.com/SMD-Bioinformatics-Lund/coyote-relay/blob/dev/docs/README.md),
[reference service](../../services/atlas/docs/README.md) and
[demo package](../../services/demo/docs/README.md). This section describes how
those interfaces participate in the complete application.
