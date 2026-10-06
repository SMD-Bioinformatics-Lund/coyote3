# System architecture

Coyote3 combines a React interface, a FastAPI service, background workers, and MongoDB
persistence. Its architecture separates clinical workflows, application services,
and infrastructure, with explicit contracts for data ingestion, access, and reporting.

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
| [Clinical Data Preparation And Reporting Flow](clinical-data-and-reporting.md) | Trace configuration and findings into report generation. |
| [Architecture decisions](decisions/README.md) | Read accepted architecture decisions and their rationale. |

[Documentation home](../README.md)
