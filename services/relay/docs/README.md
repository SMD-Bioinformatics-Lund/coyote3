<img src="../src/coyote_relay/assets/coyote-relay-logo.svg" alt="Coyote Relay" width="320">

<!-- badges:start -->
![coyote-relay: 1.0.0](https://img.shields.io/badge/coyote--relay-1.0.0-4F46A5?style=flat) ![Python: >=3.12](https://img.shields.io/badge/Python-%3E%3D3.12-3776AB?style=flat&logo=python&logoColor=white) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

Use the submission tools from a pipeline host. Install the `api` extra with the
server to expose ingestion routes, and the `worker` extra in the configured
application environment to execute jobs. The server discovers the installed API
extension through `coyote.api.routers`; its authentication and permission checks
protect submissions. Workers execute retained jobs through the core application
workflow. The server can run without Relay installed.

1. [Install the tools or worker](getting-started.md).
2. [Validate and submit a manifest](usage.md).
3. [Configure authentication and worker hosting](configuration.md).
4. [Look up commands and message names](reference.md).
5. [Develop and test this package](development.md).
