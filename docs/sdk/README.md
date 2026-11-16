# Python packages

<!-- badges:start -->
![Coyote4: 4.0.0](https://img.shields.io/badge/Coyote4-4.0.0-4F46A5?style=flat) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

Coyote has four independently installable Python distributions in one repository.

| Package | Purpose |
| --- | --- |
| `coyote-core` | Framework-independent clinical rules, contracts and application operations |
| `coyote-server` | Separate API and Mongo components: HTTP, authentication, maintenance, queries and persistence |
| `coyote-pyclient` | Synchronous and asynchronous clients for a running API |
| `coyote-relay` | Pipeline submission commands and ingestion workers using core workflows |

## Choose the Python interface

Use the [HTTP client](python-client.md) for external integrations. Use the
[core](core.md) to build a trusted host with explicit repository and authorization
capabilities. Installing the core does not start a server or connect to MongoDB.

Start with [editable uv development](uv-development.md), then consult
[installation](server-installation.md), [package boundaries](package-boundaries.md),
[application operations](application-sdk.md) and [release compatibility](compatibility.md).

## Package-owned documentation

Use the individual guides for installation, usage, configuration, interfaces and
package development: [core](../../core/docs/README.md),
[API](../../api/docs/README.md), [MongoDB](../../adapters/mongo/docs/README.md) and
[HTTP client](../../clients/python/docs/README.md), and
[ingestion service](../../services/relay/docs/README.md). This section describes how
those interfaces participate in the complete application.
