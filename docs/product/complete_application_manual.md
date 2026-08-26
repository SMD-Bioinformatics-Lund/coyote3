# System overview

This page explains how the main parts of Coyote3 fit together. Use the audience
manuals for task instructions:

| Reader | Manual |
| --- | --- |
| Clinical user or administrator | [Complete user manual](../user_guide/complete_user_manual.md) |
| Developer or maintainer | [Complete developer manual](../developer/complete_developer_manual.md) |
| Deployment operator | [Production deployment](../start_here/production_deployment.md) |

## Purpose

Coyote3 receives validated analysis output, stores it in typed MongoDB
collections, applies assay-specific review rules, supports clinical
interpretation, and saves reproducible report snapshots.

The application is not a sequencing pipeline, LIMS, patient record, or raw-read
archive. It begins with analysis files and metadata produced by approved
upstream systems.

## End-to-end flow

```text
ASP, ASPC, and ISGL configuration
  -> sample manifest and declared files
  -> validation and atomic ingest
  -> sample and analysis collections
  -> assay-aware filtering and review
  -> comments and classification
  -> report preview
  -> saved report and reported-finding snapshots
  -> audit and cohort search
```

| Stage | Main input | Stored result |
| --- | --- | --- |
| Assay setup | ASP, ASPC, and ISGL documents | Versioned active configuration |
| Ingest | YAML manifest and declared analysis files | Sample plus dependent analysis documents |
| Review | Resolved ASPC, filters, and findings | Updated filter and curation state |
| Reporting | Reportable findings and latest visible sample comment | Report, artifacts, filter snapshot, and typed finding snapshots |
| Governance | Authenticated user action | Audit event where required |

## Runtime services

| Service | Responsibility |
| --- | --- |
| React frontend | Clinical, public, and administrative screens. |
| FastAPI API | Validation, authorization, workflows, reporting, and public contracts. |
| Celery worker | Ingest, maintenance, and explicitly queued background work. |
| Celery beat | Periodic task scheduling. |
| MongoDB | Clinical, configuration, identity, audit, and operational documents. |
| Redis | Task delivery, sessions, and non-clinical cache data. |
| Reverse proxy | One browser origin for UI, API, and documentation. |

The API and worker use the same application services and document contracts.
An HTTP-triggered write and a background write therefore follow the same
validation rules.

## Clinical configuration

| Document | Defines | Stable identity |
| --- | --- | --- |
| ASP | Assay design, omics layer, platform, assay group, covered genes, and design metadata. | `asp_id` |
| ASPC | Environment-specific analyses, filters, report sections, and reporting metadata for an ASP and subpanel. | `aspc_id` |
| ISGL | Named in-silico gene list and the analyses, assays, groups, or diagnoses where it may be selected. | `isgl_id` |

An ASPC resolves by ASP, subpanel, and environment. If no matching subpanel
configuration exists, the application may resolve the base ASPC and shows that
fact to the reviewer. A saved report records the configuration identity and
version used for that report.

## Sample and finding data

The sample document contains identity, assay references, pipeline metadata,
loaded-resource status, selected gene lists, and the effective filter snapshot.
Large result sets are stored separately and linked by sample identity.

| Data | Collection family |
| --- | --- |
| Small variants | `variants` plus versioned `anno_vep` transcript annotations |
| Copy-number findings | `cnvs` |
| DNA structural findings | `translocations` |
| RNA fusion findings | `fusions` |
| Biomarkers | `biomarkers` |
| Coverage | `group_coverage` and `panel_coverage` |
| RNA expression, classification, and QC | Dedicated RNA analysis collections |
| Curation | `annotation`, blacklist, and comment collections |
| Reporting | `reports` and `reported_variants` |

The [generated collection contracts](../api/collection_contracts.md) define the
exact fields and validation rules.

## Query flow

Finding queries combine independent layers:

1. sample identity and analysis intent;
2. ASPC analysis availability;
3. standard analysis filters;
4. selected analysis-specific ISGLs, otherwise ASP gene scope when applicable;
5. approved query-policy exceptions; and
6. search, sort, and pagination requested by the UI.

False-positive and irrelevant findings remain available in analysis views when
requested, but reporting excludes them. Sorting runs before pagination, so the
order applies to the complete filtered result set.

See [query and filter strategy](aspc_driven_query_strategy.md) for every policy
block, operator, and example.

## Reporting flow

Reporting uses prepared facts rather than querying arbitrary data from a Jinja
template. The report service:

1. resolves the sample, ASP, ASPC, applied gene lists, and enabled sections;
2. selects reportable SNVs, CNVs, structural findings, fusions, biomarkers, and
   other enabled analyses;
3. prepares aggregates such as tier summaries;
4. evaluates the static YAML rule set for the ASP and subpanel;
5. renders the preview; and
6. saves immutable report context and typed reported-finding rows when asked.

Report-rule files are part of the application release. Changing approved text
requires a reviewed rule change and application version change.

See [clinical reporting rules](clinical_reporting_rules.md) for rule syntax,
available facts, templates, filters, priorities, and complete examples.

## Security and audit

Authentication establishes identity. Database-backed roles and permissions
decide which actions that identity may perform. Assay, environment, and group
scope further restrict visible resources.

Audit events cover security-sensitive and clinically significant changes,
including configuration changes, sample ingest and deletion, curation,
reporting, user administration, and runtime controls. Traceability records are
retained according to their audit category and must not be replaced by ordinary
application logs.

See the [security model](../architecture/security_model.md) and
[audit and logging](../operations/audit-and-logging.md).

## Configuration ownership

| Source | Use | Example |
| --- | --- | --- |
| Code constants | Product vocabulary that centers cannot redefine | assay groups, supported analysis types |
| Center files | Values a center may change before deployment | contacts, assay catalog, file-key mapping |
| Environment or secret store | Deployment endpoints and secrets | MongoDB URI, database names, credentials |
| MongoDB admin documents | Runtime behavior that authorized users may change | module controls and retention settings |
| User settings | Per-user display preferences | analysis layout and table page size |

Do not duplicate one value across these sources. The
[configuration guide](../start_here/configuration.md) lists every supported
environment and center-file key.

## Authoritative references

| Subject | Reference |
| --- | --- |
| User tasks | [Complete user manual](../user_guide/complete_user_manual.md) |
| Development | [Complete developer manual](../developer/complete_developer_manual.md) |
| Architecture | [Application architecture](../architecture/current_application_context.md) |
| Clinical data lifecycle | [Clinical data and reporting flow](../architecture/clinical_data_and_reporting_flow.md) |
| Sample manifests | [Sample YAML specification](../api/sample_yaml.md) |
| Collection fields | [Collection contracts](../api/collection_contracts.md) |
| Query rules | [Query and filter strategy](aspc_driven_query_strategy.md) |
| Report rules | [Clinical reporting rules](clinical_reporting_rules.md) |
| Deployment | [Production deployment](../start_here/production_deployment.md) |
| Operations | [Maintenance and quality](../operations/maintenance_and_quality.md) |
