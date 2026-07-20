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
- **Sample List Metadata**: The sample catalog shows sample identity, case/control identifiers, clarity identifiers, profile, assay, subpanel, analysis ingest state, report state, loaded data counts, and load date.
- **Analysis Status Visibility**: Sample overview separates bundle ingest status from analysis availability. Each configured analysis domain is reported as ready, missing, count-bearing, or file-present so users can see whether SNV, CNV, fusion, translocation, coverage, and biomarker data are available for review.

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
- **Domain-Specific Detail Actions**: Detail pages expose only clinically meaningful controls for the finding type. Small variants support blacklist and irrelevant controls; CNVs support report inclusion and noteworthy controls; translocations support report inclusion; fusions support false-positive and selected-call control.
- **Caller Evidence Display**: Caller names are shown as individual badges. The active sample is shown as a direct link back to the sample context.
- **Biological Severity Encoding**: VEP impact, filter flags, and prediction labels use biological severity colors. `HIGH` and damaging predictions are failure/red, `MODERATE` is warning/yellow, `LOW` is pass/green, and `MODIFIER` is neutral rather than benign.

## RNA Interpretation Interface

- **Fusion Visualization**: Dedicated review interface for transcript-level fusion events.
- **Fusion Logic Control**: Thresholding for spanning reads, caller-specific evidence, and projected fusion effects.
- **Evidence Selection**: Granular selection of primary calls when multiple callers yield overlapping fusion data.
- **Caller Evidence Display**: Fusion callers are shown as separate badges where caller-level data is available, while the selected call table manages per-caller evidence selection.

## Administrative and Security Control

- **Identity Lifecycle**: Creation, modification, and revocation of system user accounts.
- **Provider Visibility**: User tables and detail views show one badge per configured authentication provider. LDAP badges represent email-based directory authentication; local badges represent username/password authentication managed by Coyote3.
- **Role Visibility**: Role values are displayed as readable color chips. The role's configured color is used as an accent rather than text color so high-contrast readability is preserved in light and dark mode.
- **Role Palette Governance**: Default roles use a stable palette (`admin` red, `developer` blue, `tester` amber, `manager` indigo, `user` green, `intern` purple, `viewer` slate, `external` slate gray). Centers can change role colors through role configuration without changing authorization behavior.
- **Contact Actions**: User email values are interactive `mailto:` links in admin tables and read-only detail views.
- **Policy Definition**: Management of system-wide roles and permission matrices.
- **Resource Governing**: Versioned lifecycle management for Assay Panels (ASP), Configurations (ASPC), and Gene Lists (ISGL).
- **Configuration Semantics**: Constant-backed values such as assay category, assay group, assay family, platform, environment/profile, analysis type, and ISGL list type render as semantic badges across admin tables and forms.
- **Secure Ingestion Workspace**: Administrative access to bulk YAML-driven data ingestion and index synchronization.
- **System Audit**: High-fidelity operational logging and forensic audit analysis for administrators with `audit_log:view`.

## Public and Clinical Catalog

- **Service Transparency**: Access to the organizational assay catalog and technology matrices.
- **Resource Portability**: Public-facing gene registries and curated diagnostic list exports.
- **Clinical Engagement**: Standardized contact interface for organizational communication.

## Platform Meta-Information

- **Platform Identity**: Centralized access to environment build metadata, project links, and licensing constraints.
- **Documentation Link**: Direct link to the documentation site.
