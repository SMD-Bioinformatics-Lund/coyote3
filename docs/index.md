# Coyote3 Clinical Genomics Platform

This documentation covers how Coyote3 is built, configured, deployed, and used.

Coyote3 supports clinical genomics workflows from data ingestion through review and reporting. The docs are organized so teams can find operational guidance, product behavior, and implementation details without guessing where the source of truth lives.

---

## Platform Principles

Coyote3 is built around three practical goals:

1.  **Clinical Precision**: Every component is designed to ensure the integrity of clinical data. Strict typing, contract-based schemas, and comprehensive audit trails provide the reliability required for diagnostic-grade environments.
2.  **Architectural Scalability**: Utilizing a decoupled **Flask-to-FastAPI** topology, Coyote3 scales horizontally to handle massive omics datasets without compromising UI responsiveness.
3.  **Policy-Driven Governance**: Granular, resource-oriented permissions (RBAC) ensure that access to sensitive clinical data is tightly controlled and audited at every layer.

---

## System Architecture At A Glance

The platform is split into separate services so compute-heavy API work does not block the web application.

*   **The Interface (Coyote)**: The web application used for review and workflow management.
*   **The API**: The backend service that handles business logic, analysis workflows, and persistence.
*   **The Infrastructure**: MongoDB stores operational data, and Redis is used for session and cache support.

---

## How to Navigate this Manual

This documentation is structured by operational domain to help you find the information you need quickly.

### For Clinical & Laboratory Users
*   **Getting Started**: [Quickstart Guide](start_here/quickstart.md) for a local first run.
*   **Understanding Workflows**: [DNA and RNA Workflow Chain](product/workflow_dna_rna.md) and [UI User Flows](product/ui_map_and_user_flows.md).
*   **Terminology**: [Clinical Semantics Reference](product/clinical_semantics_reference.md) for tiers and flags.

### For Software Engineers & Developers
*   **Foundation**: [Local Development Setup](start_here/local_development.md) and [Configuration Model](start_here/configuration.md).
*   **Deep Dive**: [System Architecture](architecture/system_overview.md) and [Request Lifecycle](architecture/request_lifecycle.md).
*   **Extending the Platform**: [Adding Features](developer/adding_features.md) and [Schema Contracts](developer/schema_contracts_and_versioning.md).

### For DevOps & System Administrators
*   **Deployment**: [Enterprise Deployment Guide](operations/deployment_guide.md) and [Initial Checklist](operations/initial_deployment_checklist.md).
*   **Stability**: [Observability and SLOs](operations/observability_slos_and_alerts.md) and [Backup/Restore Procedures](operations/backup_restore_and_snapshots.md).
*   **Base Requirements**: [Minimum Production Baseline](operations/minimum_production_baseline.md).

---

## Platform Topology

![Coyote3 Platform Topology](assets/diagrams/runtime_topology.svg)

---

> [!TIP]
> If you are troubleshooting an existing installation, start with the [Operations Troubleshooting Guide](operations/troubleshooting.md) or the [Developer Troubleshooting Reference](developer/troubleshooting_guide.md).
