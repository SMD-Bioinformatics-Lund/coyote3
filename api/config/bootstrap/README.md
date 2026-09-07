# Application Bootstrap Catalogs

This directory contains application-owned data that can initialize an empty
Coyote3 database. Bootstrap is an explicit deployment operation; importing the
Python package does not write these documents.

## Catalogs

| Directory | Collections | Authority | First-deployment behavior |
| --- | --- | --- | --- |
| `rbac/` | `permissions`, `roles` | Coyote3 application release | Installed before the first local superuser is created. Bundled records cannot be deleted through the UI. Roles may be deactivated or revised through their normal managed workflow. |
| `reference/` | `hgnc_genes`, `vep_metadata` | Bundled reference snapshot | Imported only when the corresponding destination collection is empty. Existing reference collections are never merged or replaced by first-run bootstrap. |
| `demo_center/` | `assay_specific_panels`, `asp_configs`, `insilico_genelists` | Synthetic demonstration configuration | Optional smoke-test baseline for a new installation. These records cannot be deleted, but may be deactivated. Add center-approved definitions before clinical use. |

The compressed reference files use newline-delimited JSON. Compression keeps
the source checkout and container image smaller without changing the stored
MongoDB document shape.

## Empty-collection rule

`scripts/bootstrap_database.py` is the explicit first-deployment command. It
connects directly to the configured MongoDB URI before API, worker, or UI
services are started. It creates the first local superuser, then imports the
bundled RBAC, HGNC, and VEP documents only into empty destination collections.
The optional `--with-demo-center` flag additionally loads the synthetic ASP,
ASPC, and ISGL catalog. A collection with one or more documents is skipped.
This prevents a bootstrap run from silently mixing different HGNC/VEP snapshots
or replacing center-managed clinical configuration.

The operator supplies the first superuser username, email, and password on the
command line. No default credential is stored in this repository. The account
is marked `system_managed`, cannot be deleted, and must change its password at
first sign-in. It can still be deactivated by an authorized administrator.

Application upgrades use dedicated synchronization or release procedures:

- RBAC additions are applied with `scripts/sync_rbac_catalog.py`.
- HGNC and VEP releases are loaded as an intentional reference-data operation.
- ASP, ASPC, and ISGL revisions are created through their managed versioned
  workflows.

## Excluded data

This directory must not contain users, credentials, samples, findings,
annotations, reports, patient identifiers, or center-specific clinical data.
Synthetic ingest and collection examples live under `demo_data/`.
