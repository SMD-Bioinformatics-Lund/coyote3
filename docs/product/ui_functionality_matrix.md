# Functional Component Matrix

This document lists the main capabilities exposed through the Coyote3 user interfaces. It groups them by domain and user role.

## Global Platform Capabilities

The following features apply across the platform:

- **Unified Permission Model**: Every system interaction is subject to rigorous "Resource:Action:Scope" authorization checks, enforcing strict read, write, and administrative boundaries.
- **Operational Feedback**: The platform delivers secure transactional confirmation for all data mutations and state changes via standardized status notifications.
- **Dynamic Annotation Systems**: Clinical comments and annotations support visibility controls (hide/unhide) and cross-case global context propagation.
- **State Persistence**: Analytic filter states are maintained at the sample level, ensuring consistent diagnostic context during multi-session review.
- **Data Pagination**: Server-side pagination handles large datasets, while client-side views support local list interaction where appropriate.

## Clinical Dashboard Environment

- **Executive Analytics**: Real-time KPI visualization covering throughput metrics, analysis states, and tier distribution.
- **Workload Analysis**: Distribution analysis by assay profile, omics layer, and sequencing scope.
- **Assay Insights**: Contextual drill-down from analytic charts to targeted sample cohorts.
- **Gene Coverage Oversight**: Comparative gene-list metrics across ASP and ISGL resource domains.

## Sample Management and Ingestion

- **Multimodal Search**: Advanced string-based retrieval for sample identities.
- **Operational Scoping**: Filtering by production status, assay technology, and organizational assay groups.
- **View Isolation**: Independent tracking and navigation for "Live" versus "Reported" sample states.

## Diagnostics and Configuration Workflow

- **Gene Scope Refinement**: Application of standardized ISGL cohorts or ad-hoc gene inclusions.
- **Analytic Verification**: Inspection of the effective diagnostic scope derived from combined assay configurations.
- **Threshold Analysis**: Real-time review of sample-level filters versus raw sequencing findings.
- **Reporting History**: Longitudinal tracking and immediate retrieval of generated clinical report versions.

## DNA Interpretation Interface

- **Integrated Findings**: Unified review interface for SNV, CNV, and Translocation data.
- **Bulk Actions**: Bulk classification and clinical flag updates across finding sets.
- **Analytic Refinement**: Application of targeted depth, frequency, and consequence filters.
- **Data Portability**: Standardized CSV export for all genomic finding categories.

## RNA Interpretation Interface

- **Fusion Visualization**: Dedicated review interface for transcript-level fusion events.
- **Fusion Logic Control**: Thresholding for spanning reads, caller-specific evidence, and projected fusion effects.
- **Evidence Selection**: Granular selection of primary calls when multiple callers yield overlapping fusion data.

## Administrative and Security Control

- **Identity Lifecycle**: Creation, modification, and revocation of system user accounts.
- **Policy Definition**: Management of system-wide roles and permission matrices.
- **Resource Governing**: Versioned lifecycle management for Assay Panels (ASP), Configurations (ASPC), and Gene Lists (ISGL).
- **Secure Ingestion Workspace**: Administrative access to bulk YAML-driven data ingestion and index synchronization.
- **System Audit**: High-fidelity operational logging and forensic audit analysis (Superuser-only).

## Public and Clinical Catalog

- **Service Transparency**: Access to the organizational assay catalog and technology matrices.
- **Resource Portability**: Public-facing gene registries and curated diagnostic list exports.
- **Clinical Engagement**: Standardized contact interface for organizational communication.

## Platform Meta-Information

- **Platform Identity**: Centralized access to environment build metadata, changelogs, and licensing constraints.
- **Documentation Link**: Direct link to the documentation site.
