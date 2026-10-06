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
| `migrate_configuration.py` | Validate reviewed mappings from `groups` and `panels` |
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

Interval `coverage` requires a reviewed conversion into current gene/transcript
coverage or an explicit archive-only disposition. Original records remain in the
immutable export and source index.

Users, authentication data, external knowledgebases, and system collections are
outside this package. Apply validated bundles only through the shared isolated
target application command described in the runbook.
