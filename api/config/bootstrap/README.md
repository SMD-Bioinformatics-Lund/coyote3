# Application Bootstrap Catalogs

This directory contains application-owned data that can initialize an empty
Coyote3 database. Bootstrap is an explicit deployment operation; importing the
Python package does not write these documents.

## Catalogs

| Directory | Collections | Authority | First-deployment behavior |
| --- | --- | --- | --- |
| `rbac/` | `permissions`, `roles` | Coyote3 application release | Installed before the first local superuser is created. Bundled permissions are marked `system_managed` and cannot be deleted through the UI. |
| `reference/` | `hgnc_genes`, `vep_metadata` | Bundled reference snapshot | Imported only when the corresponding destination collection is empty. Existing reference collections are never merged or replaced by first-run bootstrap. |
| `demo_center/` | `assay_specific_panels`, `asp_configs`, `insilico_genelists` | Synthetic demonstration configuration | Optional smoke-test baseline for a new installation. Replace it with center-approved definitions before clinical use. |

The compressed reference files use newline-delimited JSON. Compression keeps
the source checkout and container image smaller without changing the stored
MongoDB document shape.

## Empty-collection rule

`bootstrap_center_collections.sh` checks each supported destination collection
through the internal collection-status API. A collection with one or more
documents is skipped. This prevents a first-run command from silently mixing
different HGNC/VEP snapshots or replacing center-managed assay definitions.

Application upgrades use dedicated synchronization or release procedures:

- RBAC additions are applied with `scripts/sync_rbac_catalog.py`.
- HGNC and VEP releases are loaded as an intentional reference-data operation.
- ASP, ASPC, and ISGL revisions are created through their managed versioned
  workflows.

## Excluded data

This directory must not contain users, credentials, samples, findings,
annotations, reports, patient identifiers, or center-specific clinical data.
Synthetic ingest and collection examples live under `demo_data/`.
