# UI Map and Operation Workflows

This document lists the main UI areas and the main user flows.

## System Interfaces

The UI is split into domain-specific React pages backed by FastAPI routers and permission rules.

- **Dashboard and Global Search (`home`)**: sample overview and report access.
- **DNA Interpretation (`dna`)**: SNV/Indel, CNV, and translocation review.
- **RNA Interpretation (`rna`)**: fusion review and expression analysis.
- **Coverage Analytics (`coverage`)**: sequencing coverage and gene-level coverage views.
- **Administrative Control (`admin`)**: users, roles, permissions, ASP, ASPC, and ISGL.
- **Public Domain (`public`)**: public catalog views and status pages.
- **Identity Context (`userprofile`)**: user settings and security actions.

## Support Architecture

The documentation site is exposed through `HELP_CENTER_URL`. The UI links out to that site instead of rendering the docs inside the main application.

## Standard User Workflows

### DNA Variant Review and Reporting

DNA review usually follows this sequence:

1. **Authentication**: Establish session and resolve authorized assay access.
2. **Access Sample Context**: open the target sample from the catalog.
3. **Primary Interpretation**: Examine prioritized SNV/Indel findings via the interpretation interface.
4. **Action Assignment**: Apply clinical classifications, toggle artifact flags, and append auditable review comments.
5. **Structural Review**: Perform assessment of CNV and translocation findings within integrated structural views.
6. **Report Generation**: Compile the finalized clinical report document or access existing reporting versions.

Finding detail pages keep the sample context visible through a direct sample link in the header. Caller evidence is presented as individual badges, and finding-specific action buttons are constrained to the supported clinical state transitions for that finding type.

### RNA Fusion Review and Reporting

RNA review usually follows this sequence:

1. **Access RNA context**: Resolve the RNA-level sample profile.
2. **Fusion Interpretation**: Review evidence for identified fusion events.
3. **Adjust Filters**: change thresholds and fusion-caller parameters as needed.
4. **Report Generation**: generate the RNA report.

### System Administration Workflow

Administrators manage the configuration layer:

1. **Administrative Initialization**: Access the centralized administrative dashboard.
2. **Access Governance**: Modify user identities, role definitions, and permission matrices.
3. **Assay Lifecycle Management**: Define and version assay resources including ASP, ASPC, and ISGL definitions.
4. **Audit Analysis**: Monitor system-wide operational logs and clinical audit trails.

## Interface Execution Logic

The platform uses a React client with FastAPI JSON endpoints. User actions call backend API services and pass through permission checks. Error pages should show specific setup or validation messages instead of generic failures.

Tables use a shared bordered header style and local CSV export for the loaded result set. Search screens that query cross-sample clinical knowledge require explicit submission so that displayed data always corresponds to a visible set of query controls.

Sample overview distinguishes:

- **Bundle ingest status**: whether the sample bundle loaded and passed ingest validation.
- **Analysis availability**: whether each configured analysis domain has files, raw counts, or filtered result counts ready for review.

This separation prevents a sample-level `ready` state from hiding missing or absent analysis-specific outputs.
