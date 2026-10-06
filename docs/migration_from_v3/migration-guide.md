# Coyote v3 clinical migration procedure

The v2 and v3 migration packages convert an operator-provided BSON snapshot into
validated destination bundles. Each sample is migrated with its findings,
comments, saved report references, and report-time finding snapshots. Shared
annotations, blacklist entries, and clinical configuration have separate commands.

The source databases are read-only references. Migration commands do not connect
to them. Conversion, reconciliation, and testing take place offline; target writes
require a separate explicit application step.

## Source contracts

The source inventories distinguish the v2 `coyote` database from the v3 `coyote3`
database. The inspected server reports MongoDB 3.2.14. Use compatible database
tools for an independently approved snapshot; the application's current PyMongo
client is not the legacy export client. A collection name alone does not establish
schema compatibility. Bounded inspection of older and newer records identified
the shapes below; every exported record still requires validation.

| Resource | V2 source | V3 source | Destination and handling |
| --- | --- | --- | --- |
| Samples | `samples` | `samples` | `samples`; original IDs and creation times retained |
| Small variants | **`variants_idref`** | `variants` | `variants`, plus versioned `anno_vep` evidence |
| Copy-number variants | **`cnvs_wgs`** | `cnvs` | `cnvs`; interval, ratio, probes, genes, and review flags retained |
| RNA fusions | `fusions` | Not present in the inspected inventory | `fusions` |
| DNA translocations | `transloc` | `transloc` | `translocations` |
| Measurements | `biomarkers` | `biomarkers` | `biomarkers`; typed HRD, MSI, and TMB payloads |
| Interval coverage | `coverage` | `coverage` | Requires a reviewed conversion or an explicit archive-only disposition |
| Panel coverage | Not present | `panel_cov` | `panel_coverage` |
| Group coverage | Not present | `group_coverage` | `group_coverage` |
| Clinical annotations | `annotation` | `annotation` | `annotation`; scope, authorship, classification, and text preserved |
| Saved finding snapshots | Not present | `reported_variants` | `reported_variants`; report-time content retained |
| Clinical blacklist | `blacklist` | `blacklist` | `blacklist`; `assay` becomes `assay_group` |
| Configuration | `groups`, `panels` | `assay_specific_panels`, `asp_configs`, `insilico_genelists` | Explicitly reviewed current ASP, ASPC, ISGL, group, subpanel, and association documents |

V2 `variants` and `cnvs` are excluded: the authoritative collections are
`variants_idref` and `cnvs_wgs`. They are not merged with the older collections.
Users, roles, permissions, sessions, audit collections, external knowledgebases,
`hpaexpr`, `schemas`, system collections, and `samples_backup` are outside this
clinical migration. Provision identity and external references separately.

## Migration order

1. Obtain a consistent BSON snapshot and retain its original files unchanged.
   Keep saved report files and referenced analysis files with the recovery material.
   Establish snapshot consistency and a cutover plan with the source operator;
   these scripts do not stop production writers or acquire a live snapshot.
2. Complete the [full offline schema inventory](schema-inventory.md), review every
   field/type/object-shape variation, and prepare the version-specific source index. Reconcile orphan references and
   duplicate sample identities before proceeding.
3. Provision an isolated current-version target and its required indexes. Prepare
   reviewed clinical configuration, including ASP/ASPC bindings, subpanels, assay
   groups, gene lists, and separately governed report rules.
4. Build and apply the configuration bundle, then the shared annotation and
   blacklist bundles. Review configuration relationships with the current assay
   consistency validator before importing samples.
5. Complete missing sample metadata and historical transcript evidence. Build one
   sample bundle at a time, review its manifest, and apply it to the isolated target.
6. Reconcile all source sample IDs, destination counts, saved reports, annotation
   references, coverage dispositions, and metadata gaps. Validate clinical behavior
   on the isolated target before approving cutover.

Neither a successful BSON conversion nor schema validation constitutes clinical
acceptance. No migration or test command in this procedure should target either
live source database.

## Prepare an offline source index

A completed, reviewed [schema inventory](schema-inventory.md) is mandatory before
building configuration, annotation, blacklist, or sample bundles. Conversion commands
require `--schema-audit` and review evidence bound to the same source snapshot.

Run from the repository root. Use `scripts/upgrade_from_v3/` for v2 and
`scripts/upgrade_from_v3/` for v3. The commands have the same arguments but enforce
different source inventories. This example prepares an existing v3 export:

```bash
PYTHONPATH=. .venv/bin/python scripts/upgrade_from_v3/prepare_source.py \
  --export-dir /secure/migration/export/coyote3 \
  --index /secure/migration/v3.sqlite
```

The export directory must contain one uncompressed `<collection>.bson` file for
every source collection listed for that version in the table, including empty
files for empty collections. Other files are ignored. The index streams BSON into
SQLite and indexes sample references; it does not load the entire database into
memory. Conversion memory scales with the largest selected sample or shared
resource batch.

Finding `SAMPLE_ID` values must resolve to original sample IDs. Older coverage
records identified only by `sample` are linked through the unique sample name.
Conflicting names, orphan references, and duplicate identities stop preparation.
An interrupted or failed index remains incomplete and cannot be used. Resolve the
source evidence and prepare a new index at a new path.

Source indexes, evidence files, review mappings, and output bundles contain
sensitive clinical data. Keep them outside the repository in controlled storage.
Created index and artifact files have mode `0600`; bundle directories have mode
`0700`. Bundle manifests record counts, content hashes, and source/review digests.

## Reconcile source records

Inspect an original record from the local index without printing its content to
the terminal:

```bash
PYTHONPATH=. .venv/bin/python scripts/upgrade_from_v3/inspect_record.py \
  --index /secure/migration/v3.sqlite \
  --collection samples --record-id 000000000000000000000001 \
  --output /secure/migration/sample-evidence.json
```

The example ID is synthetic. The evidence file contains the original document and
its `source_sha256`. Sample evidence also includes digests for the original filter
fields, top-level file registrations, and linked interval coverage.

A private Extended JSON review file uses these top-level sections:

| Section | Structure |
| --- | --- |
| `schema_audit` | Completed inventory digest, operator review, and unprofiled-file dispositions |
| `samples` | Original sample ID string → per-sample review |
| `annotation` | Original annotation ID string → missing-field supplement |
| `blacklist` | Original blacklist ID string → missing-field supplement |
| `configuration` | Physical source collection → source ID string → reviewed target mapping |

A per-sample review contains `sample.metadata` for explicit target context such as
`asp_id`, `current_aspc_id`, `omics_layer`, `sequencing_scope`, and
`ingest_status: "ready"`. Readiness is an operator decision after reconciliation;
the converter does not infer it from a file path. Historical values already
present in the source cannot be overwritten by metadata.

`sample.supplement` adds missing source fields. Each supplement requires:

```json
{
  "source_sha256": "digest-from-private-evidence-file",
  "reason": "Historical pipeline manifest",
  "fields": {
    "database_versions.vep": "110"
  }
}
```

`fields` accepts dotted document paths. Existing nonnull values and `_id` cannot
be changed. The original snapshot remains the record of every source field.
Per-finding supplements use `records.<physical_collection>.<original_id>` within
the sample review. Supplements for annotations referenced by saved findings must
match those used by the independent annotation migration.

Multiple VCF paths cannot be collapsed into one canonical registration implicitly.
Use `sample.file_registration` with `source_sha256` from `files_source_sha256`,
an evidence `reason`, and the complete current `files` mapping. The replacement
registration must identify the reviewed analysis artifacts for that sample. Source
paths remain in the snapshot; existing canonical registrations cannot be overwritten.

### Filters and configuration

Historical filter thresholds and selected gene lists must be translated into the
current intent-specific filter structure. A sample with stored legacy filters
requires `sample.canonical_filters`, `sample.filters_source_sha256`, and
`sample.filters_reason`. The digest covers the original `filters`, `filter_*`,
and `checked_*` fields. Review the effective settings, including defaults that
the current schema adds; old group names do not automatically identify a physical
ASP or a gene-list type.

For configuration, each source record requires `source_sha256`, `reason`, and
`targets`. `targets` maps current collection names to arrays of complete current
documents with explicit destination IDs. Allowed destinations are
`assay_groups`, `assay_specific_panels`, `asp_configs`, `insilico_genelists`,
`subpanels`, and `subpanel_associations`. Every source configuration record must
be accounted for. There is no automatic conversion of legacy report wording into
published clinical rules.

### Findings, coverage, and historical reports

- V2 idref variants may have `INFO.CSQ` but no selected consequence. The converter
  preserves an existing `INFO.selected_CSQ` and its criterion, or an unambiguous
  stored `selected_csq_feature`. Otherwise, reviewed selection evidence is required.
  The converter does not run the current transcript-selection algorithm. A supplied
  selected consequence must exist in the stored transcript evidence.
- A missing variant identity is derived from recorded chromosome, position,
  reference, and alternate allele. Existing identities are retained. Missing hashes
  are derived from the identity; incompatible hashes fail validation. Original VEP
  versions are required before transcript-vault construction.
  Missing gene, transcript, consequence, HGVS, and cross-reference search fields
  are derived from the stored consequences using the application's aggregation
  helper. Existing fields are retained; no external annotation service is called.
  Missing population-frequency fields are populated from recorded first-consequence
  VEP values, selecting the ALT allele where labels are present. Recorded zero is
  retained; absent frequency remains null. Malformed values block conversion.
- Numeric chromosome labels become strings. MSI `perc` becomes `per` without
  rescaling. Structural genotype `_sample_id` becomes `sample`; pipe-separated
  panel labels become arrays. Unparseable CNV ratios fail instead of becoming null.
  Scalar biomarkers without a typed payload and established units require review.
- Interval coverage lacks the gene/transcript/CDS structure required by current
  panel coverage. A sample review must include `coverage.source_sha256`, `reason`,
  and `action`. `replace` supplies validated `panel_coverage` documents; `archive_only`
  retains the original intervals in the source snapshot but does not expose them
  in the current coverage UI. This limitation is recorded in the bundle manifest.
- Embedded comments and reports move to dedicated collections before parent
  validation. Original IDs, author text, timestamps, hiding state, report numbers,
  paths, and report-time findings are retained. For v2 reports missing string IDs
  or display names, the destination string ID derives from the original report
  ObjectId and the display name from the saved file's basename. Report HTML/PDF
  is not regenerated. Missing v2 reported-finding snapshots are not reconstructed
  from today's annotations.

## Missing metadata and text-file backfills

Availability varies within each legacy database. Newer inspected v3 samples record
case/control run names and read counts; older sample shapes lack them. Missing
values must not be replaced with the migration date, zero, a current pipeline
version, or the administrator's identity.

| Field or resource | When required | Recovery source |
| --- | --- | --- |
| Physical ASP, ASPC, omics, scope, environment | Before sample conversion/application | Reviewed assay and configuration mapping |
| Case/control identity, sample count, pipeline | Before target sample validation | Original ingest manifest or laboratory records |
| VEP version and selected consequence | Before migrating SNVs and transcript evidence | Original pipeline metadata and historical selection evidence |
| Filter thresholds and gene-list selections | Before sample conversion when stored | Source filters, historical group/configuration settings, clinical review |
| `case.sequencing_run`, `control.sequencing_run` | May remain absent and be backfilled | Sequencing manifest or laboratory run register |
| `case.reads`, `control.reads` | May remain absent and be backfilled | Original sequencing/QC output; counts are nonnegative integers |
| Historical entry actor and route | Retain null if unknown | Durable ingest or audit evidence; no default administrator attribution |
| Finding counts | Derived from migrated finding collections | Reconciliation of source and target records; do not invent sample count fields |
| Interval coverage structure | Before current coverage display | Original coverage output and matching transcript/panel definition |
| Saved report artifacts | Before historical reports can be opened | Original report storage, mounted at preserved paths |

Both version folders provide `backfill_sample_metadata.py`. The UTF-8 text file
uses tabs, with exactly this header and one field per row:

```text
sample_id	field	value	evidence
000000000000000000000001	case.sequencing_run	SYNTHETIC_RUN_001	synthetic-manifest.tsv
000000000000000000000001	case.reads	12000000	synthetic-qc.json
```

Before conversion, generate a new review file:

```bash
PYTHONPATH=. .venv/bin/python scripts/upgrade_from_v3/backfill_sample_metadata.py \
  --index /secure/migration/v3.sqlite \
  --review /secure/migration/review.json \
  --tsv /secure/migration/metadata.tsv \
  --output /secure/migration/review-completed.json
```

Supported fields are case/control `sequencing_run` and `reads`, `case_id`,
`control_id`, `sample_no`, `pipeline`, `pipeline_version`, `genome_build`, and
`database_versions.vep`. Duplicate rows, blank values, negative counts, unknown
fields, and overwrites are rejected. Control metadata requires an original
control identity. Evidence references are retained with each supplement.

After a sample bundle has been imported, run names and read counts alone can be
backfilled from the same text format:

```bash
PYTHONPATH=. .venv/bin/python scripts/upgrade_from_v3/backfill_sample_metadata.py \
  --bundle /secure/migration/sample-bundle \
  --tsv /secure/migration/run-and-read-metadata.tsv \
  --output /secure/migration/sample-metadata-patch
```

Apply the resulting patch through the bundle application command below. The target
sample must still match the original bundle, or already match the completed patch.
Concurrent clinical edits, unrelated field changes, and overwriting recorded
values are rejected. Retain the original bundle as the recovery baseline.

## Build the migration bundles

Use the appropriate version directory consistently. These examples use v3:

```bash
PYTHONPATH=. .venv/bin/python scripts/upgrade_from_v3/migrate_configuration.py \
  --schema-audit /secure/migration/v3-schema-audit \
  --index /secure/migration/v3.sqlite --review /secure/migration/review.json \
  --output /secure/migration/configuration-bundle

PYTHONPATH=. .venv/bin/python scripts/upgrade_from_v3/migrate_annotations.py \
  --schema-audit /secure/migration/v3-schema-audit \
  --index /secure/migration/v3.sqlite --review /secure/migration/review.json \
  --output /secure/migration/annotation-bundle

PYTHONPATH=. .venv/bin/python scripts/upgrade_from_v3/migrate_blacklist.py \
  --schema-audit /secure/migration/v3-schema-audit \
  --index /secure/migration/v3.sqlite --review /secure/migration/review.json \
  --output /secure/migration/blacklist-bundle

PYTHONPATH=. .venv/bin/python scripts/upgrade_from_v3/migrate_sample.py \
  --schema-audit /secure/migration/v3-schema-audit \
  --index /secure/migration/v3.sqlite --review /secure/migration/review-completed.json \
  --sample-id 000000000000000000000001 \
  --output /secure/migration/sample-bundle
```

All output paths must be new. A manifest is written only after the bundle's BSON
files are complete. Source indexes are opened read-only. Samples are selected by
their original IDs, not inferred from file names or run names.
For a blocked finding or shared annotation, `--issues /secure/migration/issues.json`
writes the original record ID, source digest, and validation field names to a
private file. Clinical values are not printed in command errors. Reconcile the
identified record and rerun using a new output path.

## Apply to an isolated target

Only `scripts/migration_common/apply_bundle.py` connects to MongoDB. It reads
`COYOTE_MIGRATION_TARGET_URI` explicitly and does not load application environment
files. The URI must use one loopback endpoint; the production tunnel port is
rejected. Direct connection prevents replica-set discovery from selecting a
different endpoint. The database name must start with `coyote4_migration_`.

The target must support transactions. Provision its current indexes and reviewed
configuration first. Application collection names use the canonical names in the
table; custom destination collection aliases require a separately reviewed mapping.

```bash
PYTHONPATH=. .venv/bin/python scripts/migration_common/apply_bundle.py \
  --bundle /secure/migration/sample-bundle \
  --target-db coyote4_migration_validation

PYTHONPATH=. .venv/bin/python scripts/migration_common/apply_bundle.py \
  --bundle /secure/migration/sample-bundle \
  --target-db coyote4_migration_validation --apply
```

Without `--apply`, the command validates the bundle and reads the isolated target
to calculate pending changes. Application verifies hashes and collection contracts,
checks the sample's installed ASP/ASPC scope, rejects conflicting records, and
repeats conflict checks inside the transaction. Matching records are skipped on
rerun. Different source versions should use separate destinations until any shared
sample identities and annotation overlap have been reconciled.

## Acceptance and recovery

Reconcile every source sample, including those blocked by incomplete metadata.
Compare source and target findings by preserved IDs; account separately for
extracted comments/reports and newly derived VEP vault records. Check report links,
hidden comments, annotation scope, transcript evidence, variant flags, coverage
decisions, and case/control metadata. Exercise clinical review and reporting only
against the isolated destination with synthetic or otherwise approved validation data.

Each sample is applied in one transaction. A conversion failure creates no usable
bundle; an apply failure has no nontransactional fallback. A later sample failure
does not remove earlier committed bundles. Keep the destination offline until
all required batches and acceptance checks pass. Recover by restoring the isolated
target baseline and reapplying reviewed bundles; retain the original source
snapshot, source index, review files, manifests, and report artifacts. Production
source data is not a rollback target for these commands.
