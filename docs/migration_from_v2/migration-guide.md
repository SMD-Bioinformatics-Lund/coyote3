# Coyote v2 clinical migration

This procedure converts the listed clinical collections from a consistent offline
BSON export into current contract-validated bundles. Source databases are never
migration destinations. Destination configuration must already exist in the current
format; these scripts do not migrate ASP, ASPC, ISGL, subpanel, or identity configuration.

## Required before conversion

> [!WARNING]
> Use a consistent offline source export and an isolated migration target.
> Do not apply migration bundles to the legacy production database. Required
> target configuration must exist before conversion; missing metadata must be
> resolved from verified sources, not invented.

Provision an isolated MongoDB replica set for migration and validation. Install its
indexes, current application configuration, and required reference data first.
The target namespace must start with `coyote4_migration_`; the apply tool accepts
one explicit localhost endpoint and rejects the legacy production tunnel port.

| Prerequisite | Required condition |
| --- | --- |
| Assay groups | Every group referenced by an ASP, ASPC, annotation, or blacklist exists. |
| ASP | One active physical assay definition for each selected sample configuration. |
| ASPC | The exact revision selected for each sample exists, with matching ASP and group. The migration never chooses the latest revision automatically. |
| Subpanels | Every non-base scope has a current definition and association with its ASP. |
| ISGL | Every selected `snvlists`, `cnvlists`, or `fusionlists` entry exists and supports that list type. |
| Clinical rules | Applicable rules are installed and governed separately. Historical reports are not regenerated or reinterpreted. |
| Reference data | Required HGNC/VEP/reference resources are provisioned separately. Original annotation versions must be evidenced from the source or historical pipeline records. |
| Historical metadata | Required sample identity, sample number, pipeline, sequencing scope, creation time, and transcript-selection evidence are recorded or supplied from a verified source. |
| Recovery material | Immutable source export, report files, referenced analysis files, verified target backup, and a documented cutover/rollback plan. |

Take a read-only snapshot of installed target configuration:

```bash
export COYOTE_MIGRATION_TARGET_URI='mongodb://127.0.0.1:27018/?directConnection=true'
.venv/bin/python scripts/migration_common/prepare_target.py \
  --target-db coyote4_migration_validation \
  --output /secure/migration/target-catalog.json
```

The command validates the six configuration collections and their relationships
without creating indexes or changing records. Converters use this private snapshot;
application rechecks its fingerprint inside the destination transaction. Any target
configuration change requires a new snapshot and newly reviewed bundles.

## Collection scope

| Source | Current destination |
| --- | --- |
| `samples` | `samples`, extracted `sample_comments` and `reports` |
| `annotation` | `annotation`, with explicitly resolved scope and nomenclature identity |
| `blacklist` | `blacklist`; recorded `assay` becomes `assay_group` |
| `biomarkers` | `biomarkers`; measurements require typed payloads and known units |
| `transloc` | `translocations` |
| `variants_idref` | `variants`, `anno_vep`, and extracted finding comments |
| `cnvs_wgs` | `cnvs` and extracted finding comments |
| `fusions` | `fusions` and extracted finding comments |

Collections outside this table are not copied. Comments and reports embedded in
samples/findings are extracted into their current collections. Versioned VEP evidence
is built from the original stored transcript annotations; no external reannotation
is performed. Existing identities and report-time values are preserved.

## Inventory the complete offline source

Obtain a consistent export with the source operator. A sequential live read and
matching counts are not proof of a point-in-time snapshot. First/last/random examples
help understand historical shapes but cannot establish complete schema coverage.

```bash
.venv/bin/python scripts/migrate_from_v2/audit_source_schema.py \
  --export-dir /secure/migration/export/coyote \
  --output /secure/migration/schema-audit
.venv/bin/python scripts/migrate_from_v2/prepare_source.py \
  --export-dir /secure/migration/export/coyote \
  --index /secure/migration/source.sqlite
```

Each listed collection requires a BSON file, including an empty file for an empty
collection. The [schema inventory](schema-inventory.md) visits every record and every
nested array member, records field/type/object-shape variation, and binds its completion
manifest to exact source counts and hashes. Corruption or an incomplete scan blocks
conversion. Unlisted export files require an explicit exclusion disposition.

The source index rejects duplicate sample names, missing identities, and orphan
finding references. V3 coverage measurements also require a valid sample relationship.
The index is read-only after preparation.

## Review file and missing information

Conversion requires a private Extended JSON review file with `schema_audit`, `samples`,
`annotation`, and `blacklist` sections. V3 also supports `d4_coverage_blacklist` for actual
exclusion records. Record IDs are keys within each section.

`schema_audit` contains the completed audit's `manifest_sha256`, `reviewed_by`,
`reviewed_on`, and dispositions for every `unprofiled_files` entry. Use the digest
printed by the audit command; do not copy a digest from another export.

For each sample, `sample.metadata.current_aspc_id` selects an exact installed target
ASPC ObjectId. Its recorded ASP, environment, omics category, subpanel, key, and version
supply destination configuration fields. Historical pipeline versions, run names,
read counts, authors, and creation dates are never copied from current configuration.
Set `sample.metadata.ingest_status` to `ready` only after readiness review.

Inspect source evidence without printing a clinical record to the terminal:

```bash
.venv/bin/python scripts/migrate_from_v2/inspect_record.py \
  --index /secure/migration/source.sqlite --collection samples \
  --record-id ORIGINAL_SAMPLE_OBJECT_ID \
  --output /secure/migration/sample-evidence.json
```

A missing-field supplement contains `source_sha256`, `reason`, and `fields` (dotted
paths mapped to verified values). Use `sample.supplement` for a sample; finding
supplements use `records.<source_collection>.<record_id>` in that sample's review.
Existing nonnull values and record identities cannot be overwritten by a supplement.

A changed clinical scope requires an explicit mapping rather than a missing-field
supplement. `sample.scope_mapping` contains a source digest, reason, and `fields`
restricted to ASP, subpanel, environment, or omics scope. Those values must agree with
the selected installed ASPC. Annotation and blacklist review entries can contain
`scope.assay_group`; annotations additionally support `scope.subpanel`. These entries
also require the exact original digest and a reason.

Nullable unknown values remain unknown. Missing required fields stop conversion and
appear in the private run report. Do not use placeholder dates, invented pipeline
versions, an assumed administrator, zero counts, or a guessed VEP release.

### Source-specific conversions

- V2 has no D4 migration. `coverage`, `panels`, `groups`, old `variants`, and old
  `cnvs` are not source collections for this procedure.
- Some samples have no case identity, sample number, pipeline, omics layer, or
  sequencing scope. Required historical fields must come from verified records;
  target configuration supplies only the selected configuration context.
- Old file registrations may be arrays. Numeric filters can be strings or numbers,
  and checked-list dictionaries require explicit mapping to current typed filters.
- Scalar biomarkers do not establish units or a complete HRD/MSI result. Supply a
  verified typed payload or leave the run blocked. No scalar is relabeled by guess.
- Fusion calls retain recorded breakpoints, callers, selected flags, and support.
- Missing transcript selection cannot be recreated using today's selection policy.
  Recorded VEP transcript evidence and original version provenance are required.
- Report ObjectIds remain unchanged. A missing destination report ID is derived
  deterministically from that ObjectId, and a display name from its stored file path.
  No report-time finding snapshots are invented.

Stored filters are clinical settings. `sample.canonical_filters` requires
`filters_source_sha256` and `filters_reason`, covering original `filters`, `filter_*`,
and `checked_*` fields. Selected ISGL IDs must exist in the target. Current ASPC
defaults do not silently replace historical filter thresholds or selections.

Single registered file paths move into `files`. Multiple paths require an explicit
`sample.file_registration` with original path digest, reason, and current registrations.
The immutable export retains the original registrations. Missing report files and
external analysis files require separate reconciliation; a BSON conversion does not
validate their contents or availability.

## Conversion and application order

1. Complete target configuration, reference installation, and target preflight.
2. Complete the offline source inventory, index, and operator review.
3. Convert and apply shared annotations and finding blacklist entries.

4. Convert one sample at a time, including its findings, comments, saved reports,
   reported-finding references where present, and original transcript evidence.
5. Reconcile collection counts, identities, report links, exclusions, missing values,
   and all source records before clinical acceptance and cutover.

```bash
.venv/bin/python scripts/migrate_from_v2/migrate_annotations.py \
  --index /secure/migration/source.sqlite --schema-audit /secure/migration/schema-audit \
  --target-catalog /secure/migration/target-catalog.json \
  --review /secure/migration/review.json --output /secure/migration/annotations-bundle
.venv/bin/python scripts/migrate_from_v2/migrate_blacklist.py \
  --index /secure/migration/source.sqlite --schema-audit /secure/migration/schema-audit \
  --target-catalog /secure/migration/target-catalog.json \
  --review /secure/migration/review.json --output /secure/migration/blacklist-bundle
.venv/bin/python scripts/migrate_from_v2/migrate_sample.py \
  --index /secure/migration/source.sqlite --schema-audit /secure/migration/schema-audit \
  --target-catalog /secure/migration/target-catalog.json \
  --review /secure/migration/review.json --sample-id ORIGINAL_SAMPLE_OBJECT_ID \
  --output /secure/migration/sample-bundle
```

For each bundle, run destination preflight and then explicitly apply:

```bash
.venv/bin/python scripts/migration_common/apply_bundle.py \
  --bundle /secure/migration/sample-bundle --target-db coyote4_migration_validation
.venv/bin/python scripts/migration_common/apply_bundle.py \
  --bundle /secure/migration/sample-bundle --target-db coyote4_migration_validation --apply
```

Application verifies bundle hashes and schemas, checks installed scope and configuration
fingerprints, and repeats conflict checks inside a transaction. Identical existing
records are idempotent; differing records block the bundle. There is no nontransactional
fallback. Post-write verification compares complete record digests.

## Reports and metadata backfill

Every conversion produces adjacent `.migration.json` and `.migration.md` reports,
including blocked conversions. `--report` selects a new report path. Application
writes a timestamped JSON/Markdown report inside its bundle, or at `--report`.
Reports contain operation status, source and target fingerprints, converted counts,
reviewed decisions, null/blank field paths, and validation failures. IDs and field
names can be sensitive: files are private and must not be committed.

A successful schema conversion is not clinical acceptance. Review blocked fields and
report limitations, compare all source and destination records, and validate behavior
on the isolated target. Keep the original export and reports for traceability.

Verified run/read metadata can be supplied in UTF-8 TSV with exactly these columns:

```text
sample_id	field	value	evidence
```

Before conversion, use `backfill_sample_metadata.py --index ... --review ... --tsv ...
--output ...` to add missing-field supplements. After import, use `--bundle ... --tsv ...
--output ...` to prepare a conflict-checked patch for case/control run names and read
counts only. Run the patch through the same target application command. Existing
nonnull values cannot be replaced, and no count is recomputed from an unrelated source.
