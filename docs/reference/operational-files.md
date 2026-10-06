# Installed catalogs, operational inputs and generated files

These files support installation, reference-data updates, recovery and exports.
They are distinct from editable center configuration and raw sample inputs. Use
the named procedure to create or consume them; do not infer compatibility from a
`.json`, `.gz` or `.txt` extension alone.

## Installed catalogs

| Path or format | Contents | Owner and requirements | Consumer/reference |
| --- | --- | --- | --- |
| `api/config/bootstrap/rbac/permissions.seed.ndjson` | One permission object per line | Application-owned permission IDs and grants; no credentials | [Bootstrap](../deployment/bootstrap-data-flow.md), [permission fields](mongodb-collections.md#permissions). |
| `api/config/bootstrap/rbac/roles.seed.ndjson` | One role object per line | Application-owned role definitions referencing permission IDs | [Roles contract](mongodb-collections.md#roles), [RBAC administration](../administration/permissions-and-access.md). |
| `api/config/bootstrap/reference/assay_groups.seed.ndjson` | Initial group registry | Stable IDs, not center assay definitions | [Assay groups](../administration/assay-groups.md). |
| `hgnc_genes.seed.ndjson.gz`, `vep_metadata.seed.ndjson.gz` in the reference directory | Compressed line-delimited reference documents | Keep the reviewed release intact; a nonempty destination is not overwritten by bootstrap | [Required reference data](../deployment/required-data.md), [HGNC contract](mongodb-collections.md#hgnc_genes), [VEP metadata](knowledgebases/vep-reference.md). |
| `reference/vep_metadata.sources.json`, `reference/NOTICE.txt` | Release provenance and attribution | Release-owned; not runtime center overrides | [VEP updates](../operations/vep-metadata-updates.md). |
| `reference/vep_diagrams/` | Binary assets named by SHA-256 | Keep with the reference pack; hashes are checked during bootstrap | [VEP reference](knowledgebases/vep-reference.md). |
| `api/config/bootstrap/demo_center/*.json` | Synthetic assay, configuration, gene-list and clinical-rule examples | Optional demonstration data; not clinical approval | [Bootstrap options](../deployment/bootstrap-data-flow.md), [clinical resource fields](../administration/clinical-resource-fields.md). |

NDJSON is one complete object on each line. Gzip is a compression wrapper, not a
new document schema. Do not convert these catalogs into a top-level array unless
the selected importer expects an array. Installed actors and initial versions are
assigned by bootstrap; rerunning bootstrap does not reset existing history.

## Operator-supplied imports

| Input | Required format and validation | Missing data and defaults |
| --- | --- | --- |
| BRCA Exchange, CIViC, TP53 and COSMIC snapshots | Source-specific headers, product selection and compression; see [knowledgebase import formats](../operations/knowledgebase-updates.md) | Do not fabricate missing columns or merge releases manually. Dry run validates complete input before database publication. |
| VEP release metadata | Release-specific importer inputs and source provenance; see [VEP update options](../operations/vep-metadata-updates.md) | A new release does not replace every historical release. |
| Legacy migration exports, review files and backfill text | Version-specific collection inventory and exact columns: [v2](../migration_from_v2/migration-guide.md), [v3](../migration_from_v3/migration-guide.md) | Use migration reports for unavailable values. Never infer run names, read counts or clinical approval. |
| MongoDB backup archives | `mongodump` archive/compression options paired with the matching restore command | No default target is safe; select the intended database endpoint explicitly. Follow [backup and recovery](../operations/backup-and-recovery.md). |
| Load-generator configuration | Separate environment/JSON settings and synthetic target checks | Follow [load-test configuration](../testing/load-and-capacity-testing.md); application production credentials are not a test fixture. |

## Generated artifacts

| Artifact | Meaning | Handling and detailed reference |
| --- | --- | --- |
| Saved report HTML/PDF | Rendered clinical evidence | Keep with report metadata and finding snapshots; [report persistence](report-snapshots.md). Editing a file does not create a governed report revision. |
| Finding/table/chart exports | View or selected data exported by a supported UI action | Check filters and selected scope before export; [export behavior](../development/charts-and-exports.md). These are not automatically ingest files. |
| Copied sample YAML | Captured input provenance | Preserve with sample storage and backups; [manifest processing](sample-manifest.md). |
| Ingest staging and job records | Submission workspace and lifecycle information | Diagnose through [ingest recovery](../operations/ingest-job-recovery.md); an uploaded file alone does not prove commit. |
| Logs and audit records | Operational diagnostics and recorded actions | Use [audit/logging](../operations/audit-and-logging.md); they have different retention and access rules from clinical evidence. |
| Migration run reports | Conversion/application counts, rejected records and missing information | Review before acceptance; keep alongside migration inputs without committing private records. |
| Built documentation, frontend assets and generated contracts | Derived software artifacts | Change source/generators and rebuild; see [documentation maintenance](../development/writing-documentation.md). |

A backup must cover the database namespaces and persistent files needed together
for recovery. An exported table or report PDF is not a replacement for that backup.
