<img src="../src/coyote_api/config/assets/coyote-api-logo.svg" alt="Coyote API" width="320">

<!-- badges:start -->
![coyote-server: 1.0.0](https://img.shields.io/badge/coyote--server-1.0.0-4F46A5?style=flat) ![Python: >=3.12](https://img.shields.io/badge/Python-%3E%3D3.12-3776AB?style=flat&logo=python&logoColor=white) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

The API component hosts Coyote's HTTP API and background workers. It handles
authentication, transport, runtime composition and application resources. It ships
with the MongoDB adapter in `coyote-server`, while retaining its own source,
documentation and test suites.

1. [Install and start the API](getting-started.md).
2. [Configure its runtime](configuration.md).
3. [Understand requests, workers and reports](usage.md).
4. [Look up entry points and assets](reference.md).
5. [Develop and test the host](development.md).

[Architecture](architecture.md) explains the host boundary. Full center
installation, backup and release procedures belong to the application guides.
