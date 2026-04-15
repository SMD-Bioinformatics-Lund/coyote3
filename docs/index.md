# Coyote3 Clinical Genomics Platform

This documentation covers how Coyote3 is built, configured, deployed, and used.

Coyote3 supports clinical genomics workflows from data ingestion through review and reporting. The docs are organized by task so teams can find deployment, product, and implementation details quickly.

---

## Platform Principles

Coyote3 is built around three practical goals:

1.  **Clinical Precision**: Use strict contracts and audit trails to keep clinical data reliable.
2.  **Service Separation**: Keep the web layer and the API separate so UI work and analysis work can scale independently.
3.  **Access Control**: Apply RBAC and scope rules consistently across API and UI.

---

## System Architecture At A Glance

The platform is split into separate services so compute-heavy API work does not block the web application.

*   **The Interface (Coyote)**: The web application used for review and workflow management.
*   **The API**: The backend service that handles business logic, analysis workflows, and persistence.
*   **The Infrastructure**: MongoDB stores operational data, and Redis is used for session and cache support.

---

## How to Navigate this Manual

This documentation is grouped by role and task.

### For Clinical & Laboratory Users
*   **Getting Started**: [Quickstart Guide](start_here/quickstart.md) for a local first run.
*   **Understanding Workflows**: [DNA and RNA Workflow Chain](product/workflow_dna_rna.md) and [UI User Flows](product/ui_map_and_user_flows.md).
*   **Terminology**: [Clinical Semantics Reference](product/clinical_semantics_reference.md) for tiers and flags.

### For Software Engineers & Developers
*   **Foundation**: [Local Development Setup](start_here/local_development.md) and [Configuration Model](start_here/configuration.md).
*   **Architecture**: [System Architecture](architecture/system_overview.md) and [Request Lifecycle](architecture/request_lifecycle.md).
*   **Ingestion Contracts**: [Sample YAML Guide](api/sample_yaml.md) and [Sample Input Files](api/sample_input_files.md).
*   **Extending the Platform**: [Adding Features](developer/adding_features.md) and [Schema Contracts](developer/schema_contracts_and_versioning.md).

### For DevOps & System Administrators
*   **Deployment**: [Deployment Guide](operations/deployment_guide.md) and [Initial Checklist](operations/initial_deployment_checklist.md).
*   **Stability**: [Observability and SLOs](operations/observability_slos_and_alerts.md) and [Backup/Restore Procedures](operations/backup_restore_and_snapshots.md).
*   **Base Requirements**: [Minimum Production Baseline](operations/minimum_production_baseline.md).

---

## Platform Topology

![Coyote3 Platform Topology](assets/diagrams/runtime_topology.svg)

---

> [!TIP]
> If you are troubleshooting an existing installation, start with the [Operations Troubleshooting Guide](operations/troubleshooting.md) or the [Developer Troubleshooting Reference](developer/troubleshooting_guide.md).
