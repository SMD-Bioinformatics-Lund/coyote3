# UI Map and Operation Workflows

This document serves as the authoritative functional inventory and navigational topology of the platform's user interface. It maps specific UI domains to internal execution endpoints and defines the standardized procedural flows for clinical users.

## System Interfaces

The user interface is logically segmented into domain-specific modules, each governed by dedicated execution blueprints and enforced authorization boundaries.

- **Dashboard and Global Search (`home`)**: Primary operational landing environment for multi-assay sample oversight and clinical report retrieval.
- **DNA Interpretation (`dna`)**: Specialized interpretation environments for small variants (SNV/Indel), Copy Number Variants (CNV), and Structural Variants (Translocations).
- **RNA Interpretation (`rna`)**: Targeted oversight for RNA fusion events and integrated expression analysis.
- **Coverage Analytics (`coverage`)**: High-resolution sequencing coverage metrics and gene-level analysis visualization.
- **Administrative Control (`admin`)**: Centralized management for user accounts, role-based access configurations, and assay-specific resources (ASP/ASPC/ISGL).
- **Public Domain (`public`)**: Exposed catalog views and unprivileged platform status reporting.
- **Identity Context (`userprofile`)**: Managing active user session preferences and security credentials.

## Support Architecture

The platform provides an externalized documentation repository accessible via the `HELP_CENTER_URL` directive. To preserve application performance and security, the UI does not render documentation modules natively; all help interactions are dispatched as secure external references to the standalone documentation environment.

## Standard User Workflows

### DNA Variant Review and Reporting

The procedural chain for DNA-based diagnostic interpretation follows a mandated linear sequence within the platform:

1. **Authentication**: Establish session and resolve authorized assay access.
2. **Access Sample context**: Retrieve specific target sample from the primary catalog.
3. **Primary Interpretation**: Examine prioritized SNV/Indel findings via the interpretation interface.
4. **Action Assignment**: Apply clinical classifications, toggle artifact flags, and append auditable review comments.
5. **Structural Review**: Perform assessment of CNV and translocation findings within integrated structural views.
6. **Report Generation**: Compile the finalized clinical report document or access existing reporting versions.

### RNA Fusion Review and Reporting

The focused RNA workflow enables rapid identification and triage of fusion events:

1. **Access RNA context**: Resolve the RNA-level sample profile.
2. **Fusion Interpretation**: Review evidence for identified fusion events.
3. **Filter Orchestration**: Adjust analytic thresholds and fusion-caller parameters to isolate significant findings.
4. **Report Generation**: Execute the generation of the standardized RNA-specific report variant.

### System Administration Workflow

Platform administrators manage the underlying configuration layer:

1. **Administrative Initialization**: Access the centralized administrative dashboard.
2. **Access Governance**: Modify user identities, role definitions, and permission matrices.
3. **Assay Lifecycle Management**: Define and version assay resources including ASP, ASPC, and ISGL definitions.
4. **Audit Analysis**: Monitor system-wide operational logs and clinical audit trails.

## Interface Execution Logic

The platform utilizes a strictly server-side rendering model leveraging optimized templates. All user-initiated data mutations are dispatched against RESTful backend services and are subject to immediate Permission Gate evaluation. System failures are communicated through commercial-grade error payloads containing actionable diagnostic summaries rather than generic application faults.
