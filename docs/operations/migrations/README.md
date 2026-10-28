# Data migrations

Select the procedure matching the existing deployment. These operations change stored data or database placement; they are separate from a fresh installation.

## Guides

Before selecting collections, review the
[field-level dependency diagrams and migration ordering](../../reference/collection-dependencies/README.md).
The reference distinguishes string and BSON identifiers, exact configuration revisions,
shared VEP records, report snapshots and historical identities that must be preserved.

| Guide | Use it to |
| --- | --- |
| [Variant blacklist](variant-blacklist.md) | Consolidate allele records, retain group scopes and assign normal-sample frequencies to their exact assays. |
| [Clinical data: execution order and commands](clinical-data.md) | Run the fresh v2/v3 export and preparation tools, then import reviewed data in dependency order. |
| [Independent measurement analyses](independent-biomarker-analyses.md) | Convert generic biomarker configuration to explicit HRD, MSI, and TMB selections. |
| [Clinical-Rule Data Maintenance](clinical-rule-migrations.md) | Migrate report policy and clinical-rule configuration. |
| [Reference database placement](knowledgebase-database-migration.md) | Move reference collections to the configured knowledgebase database. |

An application release upgrade is covered by [deployment upgrades](../../deployment/application-upgrades.md).
Use a migration only when its source and target requirements match your data.
For legacy conversion, [assay resources](../../administration/assay-setup.md) must
already be prepared in the destination as described by the selected migration guide.

[Operations tasks](../README.md) · [Documentation home](../../README.md)
