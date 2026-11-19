# System architecture

<!-- badges:start -->
![Coyote4: 4.0.0](https://img.shields.io/badge/Coyote4-4.0.0-4F46A5?style=flat) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

Coyote4 uses a React frontend, FastAPI host, core workflows, MongoDB repositories
and background workers. Start with [application architecture](application-architecture.md)
for their responsibilities.

| Subject | Guide |
| --- | --- |
| Assays, samples, findings and reports | [Resource relationships](resource-relationships.md) |
| HTTP, stored and runtime models | [Data contracts](data-contracts.md) |
| Database services and endpoints | [MongoDB topology](mongodb-topology.md) |
| Configuration revisions and audit | [Configuration identity](configuration-identity-and-audit.md) |
| Authentication and access | [Security model](security-model.md) |
| Ingestion and retrieval | [Data lifecycle](clinical-data-lifecycle.md) |
| Atomic writes and failure recovery | [Transactions](transactions-and-ingest-recovery.md) |
| Report preparation and saved evidence | [Reporting flow](clinical-data-and-reporting.md) |
| Visual explanations | [Diagrams](diagram-guide.md) |
| Reasons for architecture choices | [Decisions](decisions/README.md) |

Proposals are tracked in [future work](../project/future-work.md).
