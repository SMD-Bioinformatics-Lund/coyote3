# Data and clinical reference

The data and clinical reference defines resource identities, accepted input formats,
filtering behavior, reporting rules, and database contracts. Workflow procedures are
covered in the [clinical user guide](../user-guide/README.md),
[administration](../administration/README.md), and [API integration](../api/README.md).

## Find the reference you need

| Question | Read |
| --- | --- |
| What do ASP, ASPC, ISGL, case and finding mean? | [Clinical concepts and resource identities](clinical-concepts.md). |
| Which inputs does a pipeline need to provide? | [Sample manifest](sample-manifest.md), then [raw file contracts](ingest-files/README.md); submit through the [ingestion API](../api/sample-ingestion.md). |
| Why does a finding pass or fail selection? | [Application base queries](../administration/query-rules.md#application-base-queries-by-analysis), [published rule inheritance](../administration/query-rules.md#scope-and-inheritance) and [filter fields](filter-profile-fields.md). |
| Which fields can a query condition use? | [Query condition catalog](query-condition-fields.md). |
| How are clinical report statements produced? | [Reporting rules](clinical-reporting-rules.md); [saved snapshots](report-snapshots.md) explain retained report context. |
| Where do annotations and reference evidence come from? | [Knowledgebase sources](knowledgebases/README.md). |
| What does a stored document contain? | [MongoDB collection contracts](mongodb-collections.md); use [API workflows](../api/routes-and-workflows.md) for supported access. |

For a step-by-step clinical task, return to the [user guide](../user-guide/README.md).
For creating or changing an assay, use [administration](../administration/README.md).

## Guides

| Guide | Use it to |
| --- | --- |
| [System overview](application-overview.md) | Review the system's services, clinical configuration, and end-to-end flow. |
| [Supported application capabilities](../administration/supported-capabilities.md) | Check supported modalities, sequencing families, analyses and configuration boundaries. |
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
| [Query condition fields and operators](query-condition-fields.md) | Look up the generated catalog of fields and operators accepted in finding query rules. |
| [Clinical Reporting Rules](clinical-reporting-rules.md) | Look up clinical rule syntax, selection, validation, and governance. |
| [Reporting workflow and finding snapshots](report-snapshots.md) | Understand report identity, finding snapshots, and saved reporting context. |
| [MongoDB collection contracts](mongodb-collections.md) | Look up generated collection fields and validation contracts. |
| [Knowledgebase reference](knowledgebases/README.md) | Understand evidence sources, integrations, and VEP reference data. |
| [Operational files and artifacts](operational-files.md) | Identify installed catalogs, imports, backups and generated outputs. |

[Documentation home](../README.md)
