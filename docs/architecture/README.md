# System architecture

<!-- badges:start -->
![Coyote4: 4.0.0](https://img.shields.io/badge/Coyote4-4.0.0-4F46A5?style=flat) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

Coyote4 combines a React interface, a FastAPI service, background workers, and MongoDB
persistence. Its architecture separates clinical workflows, application services,
and infrastructure, with explicit contracts for data ingestion, access, and reporting.

## Choose the boundary you need

- **Locate code responsibilities:** [application architecture](application-architecture.md).
- **Understand assay and sample relationships:** [resource relationships](resource-relationships.md).
- **Trace a finding into a report:** [sample input to saved report](clinical-data-and-reporting.md).
- **Review access controls:** [security](security-model.md).
- **Understand persistence and failures:** [database topology](mongodb-topology.md) and
  [transactions and recovery](transactions-and-ingest-recovery.md).

[Diagrams](diagram-guide.md) provide visual entry points.
To implement a change, continue to [development](../development/README.md);
to deploy these services, use [deployment](../deployment/README.md).

## Guides

| Guide | Use it to |
| --- | --- |
| [Application Architecture](application-architecture.md) | Understand runtime components and application responsibilities. |
| [Architecture and workflow diagrams](diagram-guide.md) | Find resource maps and workflow diagrams. |
| [Resource relationships](resource-relationships.md) | Trace relationships among configuration, samples, findings, and reports. |
| [Data Contracts And Collection Models](data-contracts.md) | Distinguish HTTP, collection, and runtime data contracts. |
| [MongoDB services and deployment topology](mongodb-topology.md) | Map logical database services to independent MongoDB endpoints. |
| [Configuration Identity And Audit](configuration-identity-and-audit.md) | Understand stable identifiers, revisions, and audit boundaries. |
| [Security Model](security-model.md) | Review authentication, authorization, sessions, and artifact access. |
| [Clinical data lifecycle: ingest, storage, and retrieval](clinical-data-lifecycle.md) | Follow ingestion, storage, and retrieval of clinical data. |
| [Transactions and ingest recovery](transactions-and-ingest-recovery.md) | Understand atomic writes, durable jobs, and recovery behavior. |
| [From sample input to saved report](clinical-data-and-reporting.md) | Trace configuration and findings into report generation. |
| [Architecture decisions](decisions/README.md) | Read accepted architecture decisions and their rationale. |
| [Installable application packages](decisions/0004-installable-application-packages.md) | Understand why libraries and the API have independent package metadata and artifacts. |
| [Future work](../project/future-work.md) | Review the proposed separation of finding observations, origin assessments and clinical interpretations. |

[Documentation home](../README.md)
