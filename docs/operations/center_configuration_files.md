# Center Configuration Reference

Each Coyote3 deployment keeps center-owned configuration under
`api/config/center/`. These files are reviewed and deployed with the
application. They define local terminology, data-source names, public contact
details, and presentation metadata without changing Python or React code.

!!! warning "Deploy the directory as one configuration unit"

    API, Celery worker, beat scheduler, and frontend-facing public endpoints
    must use the same revision of `api/config/center/`. Change the files in
    source control, review the change, then restart API and worker services
    together.

## Ownership Boundary

| Location | Owner | Purpose | Edit for a center deployment? |
| --- | --- | --- | --- |
| `api/config/center/` | Deploying center | Clinical vocabulary, input field names, collection names, public contact content, catalog copy, and flag wording. | Yes, through reviewed configuration changes. |
| `api/config/application_metadata.py` | Coyote3 software | Product description, repository, licence, issue, and support-request URLs. | No. This identifies the Coyote3 codebase. |
| `api/config/constants.py` | Coyote3 software | Supported workflow semantics, data-model values, validators, permission categories, and sequencing-platform capabilities. | No. Extend the software when a new semantic capability is needed. |
| `api/config/runtime_settings.py` | Coyote3 software | Environment-derived runtime, security, cache, mail, and service settings. | No. Supply the documented environment values instead. |

## Directory Layout

```text
api/config/
  application_metadata.py       # repository-owned product metadata
  app_config.py                 # public runtime configuration facade
  runtime_settings.py           # environment-derived runtime setting classes
  constants.py                  # software-owned semantic constants
  loaders/                      # Python loaders for center-owned assets
  center/
    contact.toml                # public center identity and support contacts
    clinical_vocabulary.toml    # center vocabulary and sample-file bindings
    collections.toml            # Mongo database/collection mapping
    assay_catalog.yaml          # public assay-catalog narrative overlay
    filter_flag_metadata.yaml   # human-facing VCF filter badge metadata
```

The application resolves these paths internally. Do not add configuration-path
environment variables for normal deployments.

## Configuration Model

Coyote3 separates deployment wiring, center-owned configuration, and software
contracts. This prevents a local deployment choice from silently changing a
clinical workflow or a security rule.

| Layer | Location | Owner | Typical contents | Change method |
| --- | --- | --- | --- | --- |
| Runtime settings | A copied `deploy/env/example.env` file | Platform administrator | Database connection, secrets, public mount, paths, resource limits, local timezone | Update the environment and restart the affected services. |
| Center configuration | `api/config/center/` | Center clinical and technical owners | Local terminology, manifest field names, collection mapping, contacts, catalog text, filter explanations | Review the versioned file change and restart API, worker, and beat together. |
| Software contract | Python modules under `api/config/` and typed contracts | Coyote3 maintainers | Implemented analysis types, authentication mechanisms, permission semantics, persistence schemas | Change code, tests, and release documentation. |

The complete environment-variable table is maintained in
[Configuration and Environments](../start_here/configuration.md). This page
documents the center-owned TOML and YAML files.

!!! note "Keep referenced identifiers stable"

    An identifier referenced by an ASP, ASPC, ISGL, sample manifest, report,
    or historical sample is part of the clinical record. Do not rename it for
    presentation purposes. Create a reviewed replacement and plan a migration
    when a meaning must change.

## `contact.toml`

This file controls center-specific content shown on Contact and About pages.
Repository links and the product description are intentionally not present;
they are codebase metadata and remain consistent across deployments.

| TOML path | Required | Allowed value | Runtime behavior |
| --- | --- | --- | --- |
| `[organization]` | Yes | TOML table | Local center identity shown on Contact and About pages. |
| `organization.name` | Yes | Non-empty text | Retained as center metadata. The deployment `ORGANIZATION_NAME` is authoritative for the displayed runtime name; keep both aligned. |
| `organization.department` | No | Text | Department, laboratory, or service shown with center information. |
| `[support]` | Yes | TOML table | General center support information. |
| `support.primary_email` | No | A single support email address | General email contact. Leave blank only when the center intentionally has no general mailbox. |
| `support.urgent_phone` | No | Text | Telephone number or approved urgent escalation route. |
| `[[hours]]` | No, repeatable | TOML array of tables | Each row becomes one service-hours item. |
| `hours[].label` | Yes when present | Text | Short heading, such as `Service desk` or `Out of hours`. |
| `hours[].value` | Yes when present | Text | Schedule or escalation instruction. |
| `[[contacts]]` | Recommended, repeatable | TOML array of tables | Each row becomes one contact card. There is no maximum number of cards. |
| `contacts[].label` | Yes | Text | Visible card title. |
| `contacts[].role` | No | Text | Responsibility or scope beneath the title. |
| `contacts[].email` | No | One email address or comma-separated addresses | Clickable contact destination. |
| `contacts[].phone` | No | Text | Optional direct telephone number. |
| `contacts[].description` | Yes | Text | Explain which questions belong to this contact channel. |

Repository URLs, issue templates, product description, documentation links,
and catalog links are intentionally not configurable per center. They are
loaded from `api/config/application_metadata.py`, because they identify the
Coyote3 software project rather than the deploying organization.

## `clinical_vocabulary.toml`

This file configures center-controlled vocabulary and manifest field names.
It is validated during API and worker startup. The full schema, supported
workflow options, validation rules, and change procedure are documented in
[Clinical Vocabulary Configuration](clinical_vocabulary.md).

Use it when a center needs to change local authentication-provider
availability, a sample YAML file key, baseline file requirement, or the file
bound to an implemented analysis type. Sequencing platforms and their read
capabilities are software-owned and cannot be changed in this file.

> [!IMPORTANT]
> Assay groups are not center configuration. They are a software-owned clinical
> taxonomy because they define persisted access, annotation, query, ASP, ASPC,
> and ISGL scope. The supported identifiers are `hematology`, `solid`,
> `pgx`, `tumwgs`, `wts`, `myeloid`, `lymphoid`, `fusion`, and `fusionrna`.
> Assay family (`panel-dna`, `wgs`, `panel-rna`, `wts`) and subpanel (for
> example `endometrie` or `breast`) are separate concepts.

### Field-Level Contract

| TOML path | Required | Allowed values | Used for |
| --- | --- | --- | --- |
| `assay.categories` | Yes | Non-empty, unique lowercase identifiers | Omics categories that own `files.<category>` and `analysis.<category>` configuration. |
| `assay.families` | Yes | Non-empty, unique lowercase identifiers | ASP family choices. Every family must appear in `assay.family_categories`, `assay.family_scopes`, and `files.required_by_family`. |
| `assay.base_subpanel_id` | Yes | One lowercase identifier | Base ASPC subpanel identifier used when an assay has no selected named subpanel. |
| `assay.family_categories.<family>` | Yes, once per family | One configured category | Associates each assay family with its file and analysis vocabulary. |
| `assay.family_scopes.<family>` | Yes, once per family | One non-empty identifier | Sets the sequencing scope written for samples of that family. |
| `environment.options` | Yes | Unique lowercase identifiers | Environment/profile options selectable in ASPC and sample workflows. |
| `environment.default` | Yes | One item in `environment.options` | Default environment used when none is specified. |
| Software platform registry | Not a TOML value | `illumina`, `iontorrent`, `pacbio`, `nanopore` | Validates ASP/sample platform. It derives read technology and constrains the read-mode field: Illumina permits `SE` or `PE`; the other current platforms have no selectable read mode. Add a platform only through a software release with its capability definition. |
| `authentication.providers` | Yes | One or both of `local`, `ldap` | Default values allowed in a user's `auth_type` list. `local` uses username and a local password; `ldap` uses email and the configured directory service. A deployment can override this default with `AUTHENTICATION_PROVIDERS`. No other provider is implemented. |
| `genelist.standard_types` | Yes | Non-empty, unique identifiers | ISGL types offered when the ad-hoc switch is off. |
| `genelist.adhoc_types` | Yes | Non-empty, unique identifiers with no overlap with standard types | ISGL types offered when the ad-hoc switch is on. |
| `reporting.required_aspc_fields` | Yes | Non-empty, unique ASPC reporting field identifiers | Lists the report metadata expected for active report-capable ASPCs. |
| `files.dna.keys` | Yes | Non-empty, unique identifiers using letters, numbers, `_`, or `-`; normalized to lowercase | All permitted file keys under `files` in a DNA sample manifest. |
| `files.rna.keys` | Yes | Same identifier rule as DNA | All permitted file keys under `files` in an RNA sample manifest. |
| `files.required_by_family.panel-dna` | Yes | One or more keys from `files.dna.keys` | Baseline mandatory declared files for every panel DNA sample. |
| `files.required_by_family.wgs` | Yes | One or more keys from `files.dna.keys` | Baseline mandatory declared files for every WGS sample. |
| `files.required_by_family.panel-rna` | Yes | One or more keys from `files.rna.keys` | Baseline mandatory declared files for every panel RNA sample. |
| `files.required_by_family.wts` | Yes | One or more keys from `files.rna.keys` | Baseline mandatory declared files for every WTS sample. |
| `analysis.dna.types` | Yes | Unique uppercase identifiers | DNA analysis labels enabled in ASPC forms. New labels also require a matching application workflow before ingest/reporting can process them. |
| `analysis.dna.file_keys.<TYPE>` | Yes, once for every enabled DNA type | One or more keys declared in `files.dna.keys` | Associates a DNA analysis type with its source file key(s). The mapping keys must exactly match `analysis.dna.types`. |
| `analysis.rna.types` | Yes | Unique uppercase identifiers | RNA analysis labels enabled in ASPC forms. New labels also require a matching application workflow before ingest/reporting can process them. |
| `analysis.rna.file_keys.<TYPE>` | Yes, once for every enabled RNA type | One or more keys declared in `files.rna.keys` | Associates an RNA analysis type with its source file key(s). The mapping keys must exactly match `analysis.rna.types`. |

| Analysis type | Input expectation | Notes |
| --- | --- | --- |
| `SNV` | Small-variant VCF | DNA only. The first configured file key is the primary source. |
| `CNV` | CNV calls | DNA only. Typically a CNV JSON result. |
| `CNV_PROFILE` | CNV profile image | DNA only. Rendered beside the CNV table. |
| `TRANSLOCATION` | Structural-variant calls | DNA only. May share the same source as `FUSION`. |
| `FUSION` | DNA structural-variant or RNA fusion calls | The supported source depends on the omics section. |
| `BIOMARKER` | Biomarker payload | DNA only. |
| `COVERAGE` | Coverage payload | DNA only. Provides quality and gene/exon coverage views. |
| `TMB` | Tumour mutational burden result | DNA only. |
| `PGX` | Pharmacogenomic result | DNA or RNA. |
| `EXPRESSION` | Expression result | RNA only. |
| `CLASSIFICATION` | Classifier result | RNA only. |
| `QC` | Quality-control payload | RNA only. |

!!! warning "Manifest, ASPC, and source-file agreement"

    A file may be omitted only when it is neither required by assay family nor
    declared for an enabled analysis. If the manifest declares a file for an
    analysis, ingest must load it successfully. A missing or unreadable
    declared file fails the ingest instead of producing a partly ready sample.

## `collections.toml`

This file maps logical repository attributes to physical MongoDB collection
names. Each top-level TOML table is one database name, for example
`[coyote3_dev]` or `[BAM_Service]`.

### Mapping Contract

`collections.toml` maps typed repositories to physical MongoDB collections. It
does not define a document schema and it does not move data.

| TOML element | Required | Allowed value | Meaning |
| --- | --- | --- | --- |
| Application database table, for example `[coyote3_dev]` | Yes for every database used as `COYOTE3_DB` | Exact MongoDB database name | The mapping selected for the primary Coyote3 database. |
| BAM database table, for example `[BAM_Service]` | Required when `BAM_DB` integration is enabled | Exact MongoDB database name | The mapping selected for BAM-service lookup data. |
| `*_collection` | Yes for every active logical repository | Non-empty MongoDB collection name, excluding the reserved `system.*` namespace | Physical destination for one logical repository. Keep the key fixed; change only its value when the center uses another collection name. |
| `bam_samples` | Required when the selected BAM database is used | Non-empty MongoDB collection name | BAM-service sample lookup collection. |

| Collection family | Logical configuration keys | Content stored in the mapped collection |
| --- | --- | --- |
| Users and governance | `users_collection`, `roles_collection`, `permissions_collection`, `groups_collection`, `schemas_collection` | User accounts, roles, permission definitions, optional groups, and administration schemas. |
| Assay configuration | `asp_collection`, `aspc_collection`, `insilico_genelist_collection` | Assay definitions, active/versioned assay configurations, and curated gene lists. Clinical report wording remains in repository-owned YAML sources. |
| Sample and reporting workflow | `samples_collection`, `sample_comments_collection`, `reports_collection`, `reported_variants_collection`, `blacklist_collection` | Sample lifecycle records, sample-level comments, reports, report snapshots, and blacklist state. |
| DNA findings | `variants_collection`, `annotations_collection`, `anno_vep_collection`, `cnvs_collection`, `fusions_collection`, `transloc_collection`, `biomarkers_collection` | Parsed small variants and their annotations, CNVs, fusions, translocations, and biomarkers. |
| Coverage and RNA results | `coverage_collection`, `groupcov_collection`, `expression_collection`, `rna_expression_collection`, `rna_qc_collection`, `rna_classification_collection` | Coverage, grouped coverage, expression, RNA quality control, and RNA classification data. |
| Reference annotations | `hgnc_collection`, `vep_metadata_collection`, `canonical_collection`, `cosmic_collection` | HGNC identity/transcript data, VEP metadata, canonical-transcript reference, and COSMIC data. |
| Knowledgebases | `civic_variants_collection`, `civic_gene_collection`, `oncokb_collection`, `oncokb_actionable_collection`, `oncokb_genes_collection`, `oncokb_public_collection`, `oncokb_genes_public_collection`, `oncokb_cancer_genes_public_collection`, `clinpgx_genes_public_collection`, `brcaexchange_collection`, `iarc_tp53_collection` | Local knowledgebase imports and public reference material used for clinical markers and detail views. |

!!! caution "Changing names is not a migration"

    A collection mapping change redirects future reads and writes only. It does
    not copy documents, indexes, report links, or audit history. Create and
    validate the destination collection before changing a production mapping.

## `assay_catalog.yaml`

This YAML file provides catalog narrative and presentation metadata. Clinical
assay records, ASPCs, and ISGLs remain the authoritative source for active
analysis configuration and gene content.

### Catalog Key Reference

The catalog is a presentation overlay. ASPs define assays, ASPCs define active
analysis configuration, and ISGLs define curated genes. Editing this YAML file
changes public catalog content; it does not change clinical filtering, ingest
requirements, or report behavior.

| YAML path | Required | Allowed value | Use and fallback behavior |
| --- | --- | --- | --- |
| `version` | Yes | Text or number | Catalog-content revision. |
| `last_updated` | Recommended | ISO-style date or text | Public maintenance date. |
| `maintainer` | Recommended | Text | Center team responsible for catalog content. |
| `header` | Recommended | Text | Catalog landing-page heading. |
| `description` | Recommended | Text, including multiline YAML text | Catalog landing-page introduction. |
| `layout.order` | Recommended | Ordered list of modality keys | Display order. Modalities omitted from the list are appended after configured values. |
| `modalities.<modality>` | Yes for each modality | Mapping | A public modality, for example `WGS`, `WTS`, or `GenePanels`. Its key is a stable presentation identifier. |
| `modalities.<modality>.label` | Yes | Text | Visible modality label. |
| `modalities.<modality>.title` | No | Text | Expanded title; falls back to `label`. |
| `modalities.<modality>.description` | No | Text | Modality explanatory text. |
| `modalities.<modality>.categories.<category>` | Yes for every catalog section | Mapping | One public assay/category section. |
| `category.catalog_id` | Recommended | Stable text identifier | Catalog route and presentation identity. |
| `category.label` | Yes | Text | Visible category heading. |
| `category.title` | No | Text | Expanded heading; falls back to `label`. |
| `category.description` | Recommended | Text | Public assay description; falls back to the ASP description where available. |
| `category.subheading` | No | Text | Supplemental heading. |
| `category.asp_id` | Recommended | Existing ASP `asp_id` | Links the catalog section to the physical assay definition. |
| `category.subpanel_id` | No | Existing ASPC subpanel identifier | Narrows the category to a subpanel. Use the configured base subpanel when no specific subpanel applies. |
| `category.aspc_id` | No | Existing ASPC identifier | Direct configuration reference. |
| `category.aspc_ids` | No | Mapping of environment label to existing ASPC identifier | Environment-specific catalog context. |
| `category.family` / `category.asp_family` | No | Supported ASP family identifier | Optional public family override; normally inherited from the ASP. |
| `category.assay_group` | No | Existing center assay-group value | Optional public group override; normally inherited from the ASP. |
| `category.input_material` | No | List of display strings | Public sample/input badges. |
| `category.tat` | No | Text | Turnaround-time statement, for example `7-14 days`. |
| `category.sample_modes` | No | List of display strings | Sample-mode badges, for example `Tumor-only` or `Tumor-normal`. |
| `category.analysis` | No | List of display strings | Public analysis summary. If omitted, available analysis is derived from the ASPC. |
| `category.report_sections` | No | List of display strings | Public report-content summary. |
| `category.clinical_indications` | No | List of text values | Public clinical indication list. |
| `category.limitations`, `category.public_notes` | No | Text | Public limitations and supplementary notes. |
| `category.gene_lists` | No | Ordered list of mappings | Gene-list sections within the category. |
| `gene_lists[].key` or `gene_lists[].isgl_id` | Required for an ISGL-backed list | Existing ISGL `isgl_id` | Resolves active ISGL metadata and gene coverage. Remove blank placeholder entries in new catalog content. |
| `gene_lists[].label`, `description` | No | Text | List-specific visible text; label falls back to the ISGL display name. |
| `gene_lists[].diagnosis` | No | List of display strings | List-specific clinical context. |
| `gene_lists[].subpanel_id`, `list_type` | No | Existing subpanel ID or ISGL list type | List-specific context overrides. |
| `gene_lists[].tat`, `input_material`, `sample_modes`, `analysis` | No | Same forms as the category keys | List-level values override the corresponding category value. |

!!! info "Use ASP, ASPC, and ISGL for clinical truth"

    Catalog YAML is appropriate for descriptions, turnaround-time wording,
    public input labels, and display order. Use ASP, ASPC, and ISGL records for
    active assay behavior, required files, analytical settings, and genes.

## `filter_flag_metadata.yaml`

This YAML file turns VCF `FILTER` values into readable badge labels and
tooltips. It does not change filtering or tiering logic.

### Flag Metadata Key Reference

| YAML path | Required | Allowed value | Interface behavior |
| --- | --- | --- | --- |
| `exact` | Recommended | Mapping keyed by an exact upper-case VCF `FILTER` string | Used for known exact values, including `PASS`. |
| `prefixes` | Recommended | Mapping keyed by an upper-case prefix | Used when neither a detailed term nor an exact value matches. The first matching configured prefix supplies the fallback metadata. |
| `terms` | Recommended | Mapping keyed by a complete known VCF `FILTER` string | Used for caller-specific terms. A term takes precedence over an `exact` value and a prefix. |
| `*.label` | Yes for displayed metadata | Short text | Visible badge text. Keep it compact for dense clinical tables. |
| `*.severity` | Yes for displayed metadata | `pass`, `fail`, `warn`, `info`, or `neutral` | Badge and tooltip color family: green, red, amber, blue/indigo, or muted respectively. |
| `*.description` | Yes for displayed metadata | A clear sentence | Tooltip explanation. Describe the biological or technical implication, not merely the color. |
| `*.hidden` | No | Boolean, default `false` | When `true`, the term remains known but is suppressed from visible badges. |

Matching order is: full `terms` match, full `exact` match, first matching
`prefixes` entry, then the application's general fallback for common `PASS`,
`FAIL`, and `WARN` patterns. Add a `terms` entry whenever a generic prefix
cannot give reviewers a sufficiently specific explanation.

## Software-Owned Values

The following values are intentionally not configurable by a center. They are
application behavior and changing them requires a software change.

| Item | Defined in | Why it is software-owned |
| --- | --- | --- |
| Permission identifiers and permission categories | `api/config/constants.py` and authorization contracts | Centers assign existing permissions to roles; they do not define new authorization semantics. |
| Authentication implementation | `api/config/security.py` and authentication services | The vocabulary file can enable `local` and/or `ldap`, but it cannot add an authentication protocol. |
| Supported analysis types | Typed contracts, parsers, repositories, UI, and reporting services | A new type requires end-to-end ingestion, storage, display, report, and test support. |
| Reporting-rule operators and rendering behavior | Reporting contracts and rule engine | Clinical content follows its own controlled reporting-rule release process. |
| Normalized database-version keys | `api/config/database_versions.py` | Keys such as `database_versions.vep` are stable software contracts; source parsing is not a center vocabulary setting. |
| Product, licence, repository, and issue URLs | `api/config/application_metadata.py` | These identify Coyote3 itself rather than the deploying center. |

## Safe Change Protocol

1. Identify whether the change is center vocabulary, presentation content, or
   a software capability. Only the first two belong in `api/config/center/`.
2. Edit the smallest relevant file and retain stable identifiers already used
   by historical samples, ASPCs, ISGLs, or report releases.
3. Review the diff with clinical and technical owners.
4. Run configuration and contract validation in a non-production environment.
5. Restart API, worker, and beat services together.
6. Verify one representative public page and one representative ingest or
   report workflow affected by the change.

!!! tip "When not to edit a configuration file"

    Do not use center configuration to introduce a new analysis type, parser,
    authentication protocol, permission semantic, or report rule evaluator.
    Those are software capabilities and require a typed implementation,
    contracts, tests, and documentation update.
