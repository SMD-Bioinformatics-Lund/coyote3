# Collection mapping file

This file maps logical repository attributes to physical MongoDB collection
names. `[primary]` applies to `COYOTE3_DB`, `[identity]` applies to
`IDENTITY_DB`, `[knowledgebase]` applies to `KNOWLEDGEBASE_DB`, and `[bam]`
applies to `BAM_DB`. Database names remain
deployment settings and do not need matching TOML table names.

## Ownership, syntax and defaults

This application-owned TOML file maps logical repository names to physical
MongoDB collection names. `[primary]`, `[identity]`, `[knowledgebase]` and `[bam]`
are groups of mappings, not server connection settings. The external center
folder cannot override this file. Centers choose database names and URIs in the
[environment file](environment-file.md), not by renaming these collections.

The shipped file is the source of mapping values. Missing required mappings fail
validation; do not assume a collection name can be inferred from an omitted key.
Use the [generated collection reference](../reference/mongodb-collections.md) for
exact stored field contracts. Changes to mappings belong to a reviewed software
release and any required data migration.

## Mapping Contract

`api/config/collections.toml` is application-owned and maps typed repositories to physical MongoDB collections. It
does not define a document schema and it does not move data.

| TOML element | Required | Allowed value | Meaning |
| --- | --- | --- | --- |
| `[primary]` | Yes | One TOML table | Collection mapping for the database named by `COYOTE3_DB`. |
| `[identity]` | Yes | One TOML table | User, role, permission, session, and audit collection mapping for the database named by `IDENTITY_DB`. |
| `[knowledgebase]` | Yes | One TOML table | External reference collection mapping for the database named by `KNOWLEDGEBASE_DB`. |
| `[bam]` | Yes | One TOML table | Collection mapping for the database named by `BAM_DB`. |
| `*_collection` | Yes for every active logical repository | Non-empty MongoDB collection name, excluding the reserved `system.*` namespace | Physical destination for one logical repository. Application-owned mapping; center deployments retain the shipped values. |
| `bam_samples` | Required when the selected BAM database is used | Non-empty MongoDB collection name | BAM-service sample lookup collection. |

| Collection family | Logical configuration keys | Content stored in the mapped collection |
| --- | --- | --- |
| Identity and security | `users_collection`, `roles_collection`, `permissions_collection`, `api_sessions_collection`, `audit_events_collection` under `[identity]` | User accounts, roles, permission definitions, server-side sessions, and durable audit events. |
| Assay configuration | `asp_collection`, `aspc_collection`, `insilico_genelist_collection`, `public_assay_catalog_collection`, `clinical_rule_sets_collection`, `clinical_rule_revisions_collection` | Assay definitions, active/versioned assay configurations, curated gene lists, public presentation content, and governed clinical reporting rules. |
| Sample and reporting workflow | `samples_collection`, `sample_comments_collection`, `finding_comments_collection`, `reports_collection`, `reported_variants_collection`, `blacklist_collection` | Sample lifecycle records, sample-level comments, finding-level comments, reports, report snapshots, and blacklist state. |
| DNA findings | `variants_collection`, `annotations_collection`, `anno_vep_collection`, `cnvs_collection`, `fusions_collection`, `transloc_collection`, `biomarkers_collection` | Parsed small variants and their annotations, CNVs, fusions, translocations, and biomarkers. |
| Coverage and RNA results | `d4_coverage_collection`, `d4_coverage_blacklist_collection`, `rna_expression_collection`, `rna_qc_collection`, `rna_classification_collection` | D4 sample coverage, assay-group D4 exclusions, RNA expression, RNA quality control, and RNA classification data in the primary database. |
| Reference annotations | `hgnc_collection`, `vep_metadata_collection` | HGNC identity/transcript data and release-specific VEP metadata in the knowledgebase database. |
| Knowledgebases | CIViC, OncoKB, ClinPGx, BRCA Exchange, TP53, COSMIC product, version-manifest, and HPA expression keys under `[knowledgebase]` | External reference datasets in the dedicated knowledgebase database. `oncokb_public` contains query and response data only, never sample identifiers. COSMIC products remain separate collections and `knowledgebase_versions_collection` records their provenance in `versions`. |

> **Caution: Changing names is not a migration**
>
>
> A collection mapping change redirects future reads and writes only. It does
> not copy documents, indexes, report links, or audit history. Create and
> validate the destination collection before changing a production mapping.
>
