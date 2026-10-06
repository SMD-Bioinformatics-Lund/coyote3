# Application Bootstrap Catalogs

This directory contains application-owned data that can initialize an empty
Coyote3 database. Bootstrap is an explicit deployment operation; importing the
Python package does not write these documents.

## Catalogs

| Directory | Collections | Authority | First-deployment behavior |
| --- | --- | --- | --- |
| `rbac/` | `permissions`, `roles` | Coyote3 application release | Installed before the first local superuser is created. Bundled records cannot be deleted through the UI. Roles may be deactivated or revised through their normal managed workflow. |
| `reference/` | `hgnc_genes`, `vep_metadata`, `vep_diagrams` | Bundled reference snapshot in `KNOWLEDGEBASE_DB` | Imported only when the corresponding destination collection is empty. Existing reference collections are never merged or replaced by first-run bootstrap. |
| `demo_center/` | `assay_specific_panels`, `asp_configs`, `insilico_genelists` | Synthetic demonstration configuration | Optional smoke-test baseline for a new installation. These records cannot be deleted, but may be deactivated. Add center-approved definitions before clinical use. |

The compressed reference files use newline-delimited JSON. Compression keeps
the source checkout and container image smaller without changing the stored
MongoDB document shape.

## Empty-collection rule

`scripts/bootstrap/bootstrap_database.py` is the explicit first-deployment command. It
connects directly to the configured MongoDB URI before API, worker, or UI
services are started. It creates a named system administrator and an emergency
superuser together with the RBAC catalog, then imports the
bundled RBAC, HGNC, and VEP documents only into empty destination collections.
The optional `--with-demo-center` flag additionally loads the synthetic ASP,
ASPC, and ISGL catalog. A collection with one or more documents is skipped.
This prevents a bootstrap run from silently mixing different HGNC/VEP snapshots
or replacing center-managed clinical configuration.

The operator supplies distinct usernames, email addresses, and temporary passwords
for the two accounts. No default credential is stored in this repository. Both
accounts are marked `system_managed` and must change their passwords at first sign-in.

Bootstrap attributes installed records to the normalized `--sys-admin-username`
account. Supported catalogs are marked `system_managed`, and document versions start
at `1`. Clinical rule content versions and revisions also start at `1`; their
synthetic review, publication, and lifecycle metadata use the administrator and
installation time. This metadata does not establish clinical approval. Generated
subpanel definitions and associations start at version `1` with the same administrator.
Reference release identifiers remain unchanged. Existing database records and
immutable revision history are never reset by rerunning bootstrap.

Application upgrades use dedicated synchronization or release procedures:

- RBAC additions are applied with `scripts/identity/sync_rbac_catalog.py`.
- HGNC and VEP releases are loaded as an intentional reference-data operation.
- `scripts/knowledgebase/update_vep_metadata.py` downloads release-specific Ensembl website
  tables. The bundled VEP seed covers releases 98 through 116, with release 103
  preserved from the existing snapshot. `reference/vep_metadata.sources.json`
  records source commits and hashes; `reference/NOTICE.txt` records attribution.
- `reference/vep_diagrams/` contains original binary images named by SHA-256.
  Keep these assets with the reference pack. Bootstrap checks their hashes and
  installs them as BSON binary in `vep_diagrams`; VEP metadata contains only
  compact descriptors, never embedded base64 image strings.
- ASP, ASPC, and ISGL revisions are created through their managed versioned
  workflows.

## Excluded data

This directory must not contain users, credentials, samples, findings,
annotations, reports, patient identifiers, or center-specific clinical data.
Synthetic ingest and collection examples live under `demo_data/`.
