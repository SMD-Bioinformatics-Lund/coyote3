# Data migrations

<!-- badges:start -->
![Coyote4: 4.0.0](https://img.shields.io/badge/Coyote4-4.0.0-4F46A5?style=flat) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

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
| [Reference database placement](knowledgebase-database-migration.md) | Understand reference ownership and the supported relocation procedure. |

An application release upgrade is covered by [deployment upgrades](../../deployment/application-upgrades.md).
Use a migration only when its source and target requirements match your data.
For legacy conversion, [assay resources](../../administration/install-assay-resources.md) must
already be prepared in the destination as described by the selected migration guide.

[Operations tasks](../README.md) · [Documentation home](../../README.md)
