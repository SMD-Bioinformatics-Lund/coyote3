# Migrate from Coyote v2

This package converts offline BSON exports of the v2 `coyote` database.
The authoritative small-variant collection is **`variants_idref`** and the
authoritative CNV collection is **`cnvs_wgs`**. The older `variants` and `cnvs`
collections are excluded.

Follow the [v2 migration runbook](../../docs/migration_from_v2/migration-guide.md)
for collection mappings, source relationships, reconciliation, commands, and recovery.

## Commands in order

| Command | Purpose |
| --- | --- |
| `audit_source_schema.py` | Inventory every field and shape in all migrated source records before conversion |
| `prepare_source.py` | Index the documented v2 BSON snapshot without connecting to MongoDB |
| `inspect_record.py` | Write original record evidence and source hashes to a private file |
| `migrate_annotations.py` | Preserve shared annotation scope, identity, and clinical content |
| `migrate_blacklist.py` | Convert blacklist assay-group scope |
| `backfill_sample_metadata.py` | Add missing TSV metadata or prepare later run/read patches |
| `migrate_sample.py` | Convert one sample and its related findings, histories, and VEP evidence |

## Required reconciliation

V2 idref variants can lack a recorded selected consequence and simple identity.
Genomic identity can be derived from recorded coordinates and alleles. Transcript
selection requires a unique stored selection or reviewed historical evidence.

Older samples can lack case/control identity, pipeline metadata, physical assay
bindings, intent-specific filters, and VEP version provenance. Missing required
fields block conversion. Optional run names and read counts can remain absent
until verified values are supplied through the backfill command.

V2 report references can lack a string report ID or display name. Destination IDs
derive from the preserved report ObjectId and display names from the saved file
basename. No report-time finding snapshots are invented.

V2 has no D4 coverage. Only the eight clinical collections in the runbook are
indexed; legacy configuration and interval coverage are outside migration scope.

Users, authentication data, external knowledgebases, and system collections are
outside this package. Apply validated bundles only through the shared isolated
target application command described in the runbook.

Destination ASP, ASPC, ISGL, assay groups, and subpanels must already be installed.
Use `scripts/migration_common/prepare_target.py` before conversion. Every conversion
requires `--target-catalog` and writes a private JSON/Markdown migration report.
