# Data and clinical reference

The data and clinical reference defines resource identities, accepted input formats,
filtering behavior, reporting rules, and database contracts. Workflow procedures are
covered in the [clinical user guide](../user-guide/README.md),
[administration](../administration/README.md), and [API integration](../api/README.md).

## Guides

| Guide | Use it to |
| --- | --- |
| [System overview](application-overview.md) | Review the system's services, clinical configuration, and end-to-end flow. |
| [Clinical concepts and resource identities](clinical-concepts.md) | Define samples, cases, assays, configurations, gene lists, and findings. |
| [DNA and RNA data model](dna-rna-data-model.md) | Understand the data relationships shared by DNA and RNA workflows. |
| [Application domains and services](domain-services.md) | Map application domains to their resources and service responsibilities. |
| [File formats and defaults](file-format-conventions.md) | Interpret required fields, nulls, examples and format boundaries. |
| [Sample YAML manifest](sample-manifest.md) | Write and validate a sample YAML manifest. |
| [Sample input file formats](sample-file-formats.md) | Check the VCF and JSON formats consumed by ingestion. |
| [Raw ingest file reference](ingest-files/README.md) | Prepare each raw VCF or JSON input using field definitions and complete synthetic examples. |
| [HRD, MSI, and TMB](measurement-analyses.md) | Configure measurement availability, rules, reports, and exports. |
| [Assay configuration and query filtering](assay-filtering.md) | Trace assay configuration into analysis availability and query filters. |
| [Review filter fields and defaults](filter-profile-fields.md) | Look up every supported filter key, unit, bound and default. |
| [Clinical Reporting Rules](clinical-reporting-rules.md) | Look up clinical rule syntax, selection, validation, and governance. |
| [Reporting workflow and finding snapshots](report-snapshots.md) | Understand report identity, finding snapshots, and saved reporting context. |
| [MongoDB collection contracts](mongodb-collections.md) | Look up generated collection fields and validation contracts. |
| [Knowledgebase reference](knowledgebases/README.md) | Understand evidence sources, integrations, and VEP reference data. |
| [Operational files and artifacts](operational-files.md) | Identify installed catalogs, imports, backups and generated outputs. |

[Documentation home](../README.md)
