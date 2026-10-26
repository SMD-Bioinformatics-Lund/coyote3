# Data migrations

Select the procedure matching the existing deployment. These operations change stored data or database placement; they are separate from a fresh installation.

## Guides

Before selecting collections, review the
[field-level dependency diagrams and migration ordering](../../reference/collection-dependencies/README.md).
The reference distinguishes string and BSON identifiers, exact configuration revisions,
shared VEP records, report snapshots and historical identities that must be preserved.

| Guide | Use it to |
| --- | --- |
| [Migrate from Coyote v2](../../migration_from_v2/README.md) | Review the v2 source scope, inventory requirements and staged clinical-data conversion procedure. |
| [Migrate from Coyote v3](../../migration_from_v3/README.md) | Review the v3 source scope, inventory requirements and staged clinical-data conversion procedure. |
| [Independent measurement analyses](independent-biomarker-analyses.md) | Convert generic biomarker configuration to explicit HRD, MSI, and TMB selections. |
| [Clinical-Rule Data Maintenance](clinical-rule-migrations.md) | Migrate report policy and clinical-rule configuration. |
| [Reference database placement](knowledgebase-database-migration.md) | Move reference collections to the configured knowledgebase database. |

An application release upgrade is covered by [deployment upgrades](../../deployment/application-upgrades.md).
Use a migration only when its source and target requirements match your data.
For legacy conversion, [assay resources](../../administration/assay-setup.md) must
already be prepared in the destination as described by the selected migration guide.

[Operations tasks](../README.md) · [Documentation home](../../README.md)
