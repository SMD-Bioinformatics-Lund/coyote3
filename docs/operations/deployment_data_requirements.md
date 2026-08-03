# Deployment Data Requirements

This guide describes the data a center needs before a Coyote3 instance can be
used clinically. It covers required MongoDB collections, optional enhancement
collections, ingest inputs, and the storage flow from manifest to review and
reporting.

!!! info "Configuration ownership"

    Runtime endpoints and secrets are environment configuration. Collection
    names are API configuration in `api/config/center/collections.toml`.
    Public organization, service-hour, and contact-card text is center content
    in `api/config/center/contact.toml`. Repository links and the product description
    are application metadata in `api/config/application_metadata.py`.
    Public assay-catalog narrative text is center content in
    `api/config/center/assay_catalog.yaml`.

## Minimum Collections

A fresh deployment needs the following collections in the configured
`COYOTE3_DB` database to support login, authorization, assay resolution, sample
review, and reporting.

| Logical area | Default collection | Required content |
| --- | --- | --- |
| Users | `users` | User accounts with unique `username` and `email`, role assignments, auth providers, active state, and assay/profile scope. |
| Roles | `roles` | Role records used by the RBAC permission engine. Users may have multiple roles; the UI displays the highest role where a compact label is needed. |
| Permissions | `permissions` | Permission vocabulary using `resource:action[:scope]` naming. Routes check these through the authorization service. |
| Assay panels (ASP) | `assay_specific_panels` | Physical assay definitions: `asp_id`, category, family, group, platform, read mode, expected file keys, covered genes, and germline genes. |
| Assay configurations (ASPC) | `asp_configs` | Operational rulebooks for `asp_id + subpanel_id + environment`: analysis types, filters, report sections, and default review behavior. |
| In-silico gene lists (ISGL) | `insilico_genelists` | Curated clinical gene lists for SNV, CNV, fusion, expression, PGx, and ad-hoc list types. |
| Samples | `samples` | Sample metadata, file references, ASPC id, current filter snapshot, ingest status, report status, and data counts. |
| Findings | `variants`, `cnvs`, `fusions`, `translocations`, `biomarkers`, `panel_coverage` | Analysis-specific records loaded from the sample files. Only collections for enabled analyses need data for a given sample. |
| Reports | `reports`, `reported_variants` | Saved report documents and reportable-finding snapshots. |
| Sample comments | `sample_comments` | Sample-level comment and annotation history. |
| Audit and sessions | `audit_events`, `api_sessions` | Security, mutation, and session records. |

!!! tip "Collection names"

    The names above are defaults. The application does not hardcode them in
    domain services; it resolves them from `api/config/center/collections.toml`
    for the active database.

## Optional Enhancement Collections

These collections improve interpretation quality, search, or external context.
The application can run without all of them, but missing collections reduce the
richness of the UI.

| Collection | Purpose |
| --- | --- |
| `hgnc_genes` | HGNC-stable gene lookup, previous-symbol and alias matching, gene detail pages, and transcript-selection support. |
| `vep_metadata` | VEP version metadata, consequence group mapping, consequence descriptions, and impact coloring. |
| `annotation` | Tiered annotation history used by variant search, known classifications, and report text reuse. |
| `blacklist` | Blacklist and false-positive support for variant review state. |
| `oncokb_genes_public` | Public OncoKB curated gene list from `/utils/allCuratedGenes`. |
| `oncokb_cancer_genes_public` | Public cancer gene list from `/utils/cancerGeneList`; used for actionable/cancer-gene markers where therapeutic detail is not available through public API. |
| `oncokb_public` | Cached public OncoKB HGVSg mutation responses created for relevant ingested variants. |
| `clinpgx_genes_public` | Local ClinPGx gene markers imported from the approved gene source package; used to label PGx-relevant genes in tables. |
| `civic_genes`, `civic_variants` | CIViC knowledgebase context displayed in the variant knowledgebase card. |
| `brcaexchange` | BRCA Exchange context for relevant BRCA findings. |
| `iarc_tp53` | IARC TP53 context for TP53 interpretation support. |
| `cosmic` | COSMIC reference context where licensed/imported data is available. |
| `group_coverage` | Aggregated coverage metrics used by coverage views and dashboard summaries. |
| `hpaexpr`, `rna_expression`, `rna_qc`, `rna_classification` | RNA/expression review and quality-control support. |

!!! warning "External data licensing"

    Public API data and locally imported licensed datasets are different data
    sources. Public OncoKB access excludes therapeutic data. If a center imports
    licensed or historical local datasets, the UI labels the source separately
    from public API results.

## Ingest Manifest

Coyote3 ingest starts from a pipeline YAML manifest. The manifest identifies the
sample, assay, subpanel, environment/profile, case/control metadata, and file
paths. The ingest boundary maps pipeline identity fields to the canonical sample
contract before validation and persistence.

Minimum DNA manifest fields:

| Field | Meaning |
| --- | --- |
| `name` | Stable sample display name. This is used in user-facing sample URLs. |
| `assay` | Pipeline ASP identifier. Ingest maps this to `asp_id`, which must match an active ASP document. |
| `subpanel` | Pipeline subpanel identifier. Ingest maps this to `subpanel_id`; use `base` when no subpanel applies. |
| `profile` | Pipeline environment/profile. Ingest maps this to `environment`, such as `production`, `development`, or a validation environment. |
| `sequencing_technology` | Pipeline platform name. Ingest maps this to the canonical `platform` field, for example `illumina`. |
| `genome_build` | Reference genome build, normally `37` or `38`. |
| `case` | Case sample metadata including id, clarity/pool fields when available, run, FFPE state, reads, and purity. |
| `control` | Control sample metadata for paired samples. Omit only for unpaired samples. |
| `files` | Analysis files keyed by configured file keys such as VCF, CNV JSON, CNV profile image, coverage JSON, translocation VCF, or biomarkers JSON. |

!!! caution "Container-readable paths"

    File paths in manifests must be readable from the API and Celery worker
    containers. Compose mounts `COYOTE3_DATA_HOST_ROOT` both at `/data` and at
    the same absolute host path inside API and Celery containers. Pipeline source
    paths below that root remain valid and are persisted unchanged.

## Ingest Flow

1. The watch-folder task or internal ingest API receives a YAML manifest.
2. The ingest service validates the manifest against the active contracts.
3. The ingest boundary maps pipeline `assay`, `subpanel`, and `profile` to
   `asp_id`, `subpanel_id`, and `environment`; the service then resolves ASP and
   ASPC from those canonical identifiers.
4. Default filter sections are copied from ASPC into the sample document:
   `filters.snv`, `filters.cnv`, `filters.cov`, and other enabled analysis
   sections.
5. Required files from the ASP contract must be present and readable. Optional
   expected files may be absent, but every declared optional file must parse and
   write successfully.
6. The sample document is staged with file references under `files`, the active
   `aspc_id`, ingest status, current data counts, and VCF-derived metadata such
   as VEP and database versions when available.
7. Analysis-specific records are written to their own collections.
8. The sample is marked `ready` only after declared database-backed resources
   are persisted. CNV profile images remain file resources and are displayed in
   the CNV tab without creating database rows.
9. On success, the manifest is renamed with the configured done suffix. On
   failure, it is renamed with the configured failed suffix and an audit event is
   emitted.
10. Optional public knowledgebase enrichment runs as an independent Celery
    task. Its audit outcome is separate from sample readiness and manifest
    completion.

## Review And Reporting Storage

The sample document stores the current review filter state. When a user changes
filters in the UI, the backend persists the updated typed filter section and the
analysis tab reloads from those values.

Reports are separate records. A saved report includes:

- report metadata and report number
- sample identity and ASPC object id used for the report
- a filter snapshot from the time the report was generated
- rendered report content and PDF/export metadata when created
- reportable finding snapshots in `reported_variants`

This separation lets Coyote3 answer clinical questions after a report is saved:

- Which variants were visible under the report filters?
- Which ASPC rulebook generated the report?
- Which samples reported the same HGVSg, HGVS.c, HGVS.p, gene, or tiered
  annotation?
- Did later filter changes affect the historical report? The answer is no; the
  report keeps its own snapshot.

## Public And Center-Owned Content

The public assay catalog and matrix use `api/config/center/assay_catalog.yaml` for
descriptions, sample types, TAT, and navigation labels. The database still
provides the operational truth for ASP, ASPC, and ISGL objects.

The public contact page uses `api/config/center/contact.toml`. A center can
maintain a dedicated deployment revision of the `center/` directory for each
laboratory section.

!!! tip "Multi-section deployment"

    For multiple laboratory sections, build one image and run separate env files,
    databases, data roots, `SCRIPT_NAME` values, and reviewed `center/`
    configuration directories. This keeps the code identical while allowing each
    center or section to own its local routing, contacts, assays, and retention
    policy.
