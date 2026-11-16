# MongoDB adapter documentation

<!-- badges:start -->
![coyote-server: 1.0.0](https://img.shields.io/badge/coyote--server-1.0.0-4F46A5?style=flat) ![Python: >=3.12](https://img.shields.io/badge/Python-%3E%3D3.12-3776AB?style=flat&logo=python&logoColor=white) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

The adapter implements Coyote persistence using PyMongo. It owns physical
collections, provider identities, executable queries, indexes and transactions.
It ships with the API in `coyote-server`, while retaining its own source,
documentation and test suites.

1. [Install and construct connections](getting-started.md).
2. [Configure endpoints and concerns](configuration.md).
3. [Use repositories and transactions](usage.md).
4. [Look up adapter interfaces](reference.md).
5. [Develop and test the adapter](development.md).

[Architecture](architecture.md) describes persistence guarantees. Server
provisioning and backup operations belong to application deployment guides.
