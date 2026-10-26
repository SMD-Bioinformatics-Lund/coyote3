# MongoDB migration scripts

Fresh sample converters live in `v2/` and `v3/`. They use the current collection
contracts and shared file/inspection helpers in `common.py`. They do not import
the older migration implementations and do not use SQLite.

Both entry points perform **read-only MongoDB operations** and write local files.
They contain no database inserts, updates, deletes, index creation or target
connection. Run conversion first; review the completed output before importing it
into a separate destination. No migration is performed by creating these scripts.

## Source inspection and verification

Use [export one assay in batches](exporting.md) to export original samples and all
collections with explicit sample ownership in automatic batches of up to 500 samples.
The exporter checkpoints each collection and resumes without fetching completed data again.

Read-only inspection has been completed against `coyote` (v2) and `coyote3` (v3)
through SSH and the server's legacy `mongo` shell. It included random documents in
both databases and additional random examples for every supported v2 source group,
plus aggregate scope and diagnosis distributions. No source data was changed.
See [observed source structures](source-structures.md) for mapping details and known gaps.

The installed MongoDB 3.2 server is incompatible with current PyMongo and mongosh
drivers. Use the server's `mongoexport` 3.2 tool through SSH, then supply the resulting
Extended JSON lines to `--input`. The direct URI path is available for a source
snapshot restored to a compatible MongoDB version. Random sampling is not a full
inventory, and contract validation alone does not establish clinical equivalence.

## Scope and mapping

| Source | Converter output |
| --- | --- |
| `samples` | `samples`, retaining the original BSON ObjectId |
| `samples.comments[]` | `sample_comments`, retaining IDs, text, author, creation/hiding times and hiding state |
| `samples.reports[]` | `reports`, retaining IDs, report numbers, files, authors, timestamps and recorded snapshots |
| `samples.expr` | `rna_expression` when a recorded payload is present |
| `samples.classification` | `rna_classification` when a recorded payload is present |
| `samples.QC` | Complete single RNA results become `rna_qc`; incomplete or multiple results remain unchanged on the sample |

This first stage handles the sample document and records extracted from it.
Separate source collections such as variants, CNVs, translocations, fusions,
biomarkers, coverage and reported findings are not copied by these entry points.
Their own converters must retain the sample identifiers produced here. Clinical
annotations and the shared `anno_vep` vault also have independent conversion stages.

Continue with [non-variant sample-related data](related-data.md) for the fresh
`v2/migrate_related.py` and `v3/migrate_related.py` converters. That stage handles
separate CNV, fusion, translocation, biomarker, coverage, RNA/PGX and saved-report
finding exports, using the sample bundle from this procedure.
Use [variants, VEP evidence and finding comments](variants.md) for the separate fresh
`v2/migrate_variants.py` and `v3/migrate_variants.py` converters and import commands.
That selection uses original sample ObjectIds recorded in `SAMPLE_ID`, with
`sample_oid` used for saved report findings. Coverage source names do not determine
their format: normal coverage, D4 measurements and group-level exclusions are
handled separately according to their stored fields.

Each version has its own `convert` function. V2 translates `groups` into a scalar
lowercase `asp_id`. Very old `group`/`assay` samples use `assay: myeloid` →
`myeloid_gmsv1`, `assay: solid` → `solid_gmsv3`, or `assay: hematology` →
`hema_gmsv1`. A newer physical ASP in `groups` takes precedence over this older
representation. Missing or conflicting scope is rejected.
V3 translates its physical `assay` into `asp_id`; its optional `groups` must agree.
`asp_group` is a field of the assay definition, not a declared required sample field.
The converter does not derive it by renaming `assay` or require it on a sample.
An explicitly recorded or reviewed `asp_group` is retained as optional context.
Both translate `subpanel` into `diagnosis_id`, `profile` into `environment`,
`omics_layer` into `asp_category`, and `sequencing_scope` into `asp_family`.
V3 `panel` / `WGS` plus recorded `DNA` become `panel-dna` / `wgs-dna`.
A missing case/control
ID may come from the recorded nested `case.id` / `control.id`. Original creation
time is required; the current date and ObjectId timestamp are never substitutes.

| Version | Source database | Accepted assay IDs, one per invocation |
| --- | --- | --- |
| v3 | `coyote3` | `gmshem`, `hema_gmsv1` |
| v2 | `coyote` | `hema_gmsv1`, `parp_inhib`, `fusion`, `fusion_validation_nf`, `lymph_gmsv3`, `lymphoid_gmsv1`, `myeloid_gmsv1`, `solidrna_gmsv5`, `solid_gmsv3`, `tumwgs`, `tumwgs-hema`, `tumwgs-solid`, `twistrnafusionv1-0` |

Source matching is case-insensitive. `tumwgs-hema` selects `groups: tumwgs` with
`subpanel: hema`; `tumwgs-solid` selects its solid counterpart. A document whose
groups contain multiple assay identifiers is rejected for explicit review.
The `gmshem` identifier is retained; it is not silently renamed to `hema_gmsv1`.
The inspected v3 source currently contains `hema_GMSv1`, with no `gmshem` match.

Assay, assay-group, diagnosis/subpanel and related configuration identifiers are
lowercase in converted sample and report scope fields. Case differences do not
create conflicts between recorded identifiers and reviewed metadata. Specimen
identifiers, MongoDB ObjectIds, author names and original source archives retain
their recorded values. Embedded report snapshots retain their historical content.

Both converters apply these approved subpanel renames, case-insensitively, before
comparing source aliases or reviewed scope. The same renames apply to extracted
report scope fields; the original source archive and embedded snapshots are retained.

| Source subpanel | Destination diagnosis ID |
| --- | --- |
| `BC` | `breast` |
| `BP` | `breast-pilot` |
| `CRC` | `crc` |
| `LP` | `lung` |
| `None`, empty string, `solid` | `base` |
| `Hem` | `hem` |
| `Hem-Snabb` | `hem-snabb` |
| `KLL` | `kll` |
| `MPN` | `mpn` |
| `Riktad` | `riktad` |
| `AlloSCT` | `allo-sct` |
| `lungthyroid` | `lung-thyroid` |

Unlisted names retain their lowercase spelling. A genuinely absent or null
diagnosis is not automatically assigned `base`. The unsplit tumwgs exception below
continues to use `legacy` for its unspecified subpanel.

Use `--assay-id tumwgs` separately for samples without a named subpanel. Missing,
null, blank and `None` subpanels become `diagnosis_id: "legacy"`, retaining
`asp_id: "tumwgs"`. An existing `legacy` subpanel is included in the same selection.
These records are excluded from the hema/solid selections. Prepare the corresponding
target assay and diagnosis configuration before importing their samples.

Incomplete RNA QC stays unchanged in `samples.QC` and in the original source archive.
No missing measurements, extra flags or labels are added to the QC payload.
Multiple QC results also remain embedded rather than selecting or combining them.

Missing embedded comment/report IDs receive deterministic ObjectIds based on the
original sample ID, destination collection and original array position. Existing
IDs always take precedence. Missing report IDs/names are derived from the retained
report ObjectId and filepath. These derived identifiers do not replace authors,
dates, report content or historical configuration snapshots.

## 1. Inspect random documents read-only

Run from the repository root with the project virtual environment. The source URI
is read from an environment variable so credentials do not appear in command arguments.
Use a MongoDB account restricted to reads when authentication is available.

First export the samples through SSH using the source server's legacy tools.
Use protected storage outside the repository and check SSH's exit status before
using either file; a failed export can leave a partial file.

```bash
umask 077
export MIGRATION_SSH_HOST='operator@legacy-mongodb-host'

ssh "$MIGRATION_SSH_HOST" \
  'mongoexport --host 127.0.0.1 --port 27017 --db coyote --collection samples --type=json' \
  > /secure/migration/v2-samples.jsonl
ssh "$MIGRATION_SSH_HOST" \
  'mongoexport --host 127.0.0.1 --port 27017 --db coyote3 --collection samples --type=json' \
  > /secure/migration/v3-samples.jsonl
```

These export commands read the complete source samples collection. The Python
converter selects only the requested assay. Do not put credentials in SSH arguments;
use existing SSH key/agent configuration. Then inspect the exported structures:

```bash

.venv/bin/python migrations_scripts/v2/migrate_samples.py inspect \
  --input /secure/migration/v2-samples.jsonl \
  --assay-id myeloid_gmsv1 --random-documents 20 \
  --output /secure/migration/v2-myeloid-inspection

.venv/bin/python migrations_scripts/v3/migrate_samples.py inspect \
  --input /secure/migration/v3-samples.jsonl \
  --assay-id hema_gmsv1 --random-documents 20 \
  --output /secure/migration/v3-hema-inspection
```

For a compatible MongoDB source, omit `--input` and set `MIGRATION_SOURCE_URI`
to its explicit read-only URI. Database names remain fixed by the versioned entry
point. File inspection uses reservoir sampling across the selected assay, so it
does not simply take the first records.

Outputs belong outside the repository. Each new output directory is created with
mode `0700`. `sampled-source.jsonl` contains the private original records;
`structure.json` records field/type paths across all sampled array members without
scalar patient values; `review-template.json` contains source hashes indexed by
original sample ObjectId. Terminal output contains counts only. Field names may
themselves contain private identifiers, so the structure report is also private.
Existing directories are never overwritten.

Use `--all-samples` instead of random sampling to prepare review templates for
every sample in the selected assay. This is a full read and can be larger. A live
scan is not a point-in-time snapshot: use an operator-provided consistent MongoDB
snapshot or a source frozen for cutover for final preparation. A source change
after review causes the digest check to fail.

## 2. Complete the source-bound review

Copy the generated review template to a separate private file and complete its
`metadata` values from verified historical data and installed destination
configuration. The following example is synthetic; retain the real generated hash
and sample identity locally.

```json
{
  "samples": {
    "000000000000000000000001": {
      "source_sha256": "REPLACE_WITH_GENERATED_SOURCE_SHA256",
      "metadata": {
        "current_aspc_id": {"$oid": "000000000000000000000002"},
        "current_aspc_name": "Verified installed configuration",
        "asp_group": "hematology",
        "platform": "illumina",
        "read_mode": "PE",
        "ingest_status": "ready"
      }
    }
  }
}
```

Only supply missing canonical values. Conflicting recorded values fail conversion.
Identity, sample name, creation time, embedded history and latest-report pointers
cannot be replaced through metadata. `current_aspc_id` must be the exact installed
BSON ObjectId. Check that its assay, diagnosis and environment agree with the
converted sample; preparation does not connect to or verify the destination.

Recorded legacy filters require `canonical_filters` and `filters_reason` in the
same per-sample review entry. Supply the complete current intent-aware filter
document; never replace recorded thresholds with current application defaults.
The digest covers the complete source, including the old filters.

An intentional diagnosis/group rename uses a separate `scope_mapping` object in
that entry, for example
`{"diagnosis_id": "breast", "reason": "Reviewed source BC to installed breast diagnosis mapping"}`.
Only `diagnosis_id` and `asp_group` can be changed this way. Original scope remains
in the preserved source archive. Historical report snapshots are not rewritten.

Missing historical case identity, pipeline, file registration, authorship required
by a comment, or malformed report history must be resolved from source evidence.
Unknown fields remain on permissive records and in the source archive; validation
does not assign them a new clinical meaning.

## 3. Prepare one assay

```bash
.venv/bin/python migrations_scripts/v2/migrate_samples.py prepare \
  --input /secure/migration/v2-samples.jsonl \
  --assay-id myeloid_gmsv1 \
  --review /secure/migration/v2-myeloid-review.json \
  --case-control-config /secure/migration/case-control.json \
  --output /secure/migration/v2-myeloid-prepared

.venv/bin/python migrations_scripts/v3/migrate_samples.py prepare \
  --input /secure/migration/v3-samples.jsonl \
  --assay-id hema_gmsv1 \
  --review /secure/migration/v3-hema-review.json \
  --case-control-config /secure/migration/case-control.json \
  --output /secure/migration/v3-hema-prepared
```

Add `--sample-id ORIGINAL_OBJECT_ID` to prepare a single reviewed sample. Repeat
the flag for a selected subset. Without it, every sample in the assay must have a
review entry. An absent requested sample fails completion.

Configure [read-only Bjorn/CDM case and control enrichment](case-control.md)
before preparation. Each case and present control is matched by specimen and
assay. Multiple nonfailed runs are retained only when CDM confirms them;
otherwise the latest nonfailed Bjorn run is used. The private
`case_control_sources.jsonl` evidence file is not imported into MongoDB.

Preparation writes one canonical Extended JSON file per derived collection,
`source_samples.jsonl` with the untouched originals, and a final `manifest.json`
with counts and file checksums. **Only a manifest with `complete: true` marks a
finished conversion.** A conversion failure writes private details to `failure.json`
and exits nonzero; partial files must not be imported. Re-run into a new directory
after correcting the review or converter. BSON ObjectIds and dates remain typed.

Review author/time preservation, report counts and latest-report pointers, source
and output counts, and exact installed ASPC scope before loading a destination.
Copy referenced HTML/PDF and analysis artifacts separately; these scripts preserve
their paths but do not copy files or regenerate reports.

## 4. Import reviewed files into a separate destination

These are operator-run commands, not actions performed by the converters. Set the
target to the approved destination database and validate the completed manifest
and file checksums first. Never use `coyote` or the legacy `coyote3` as a destination.
Use insert mode; duplicate IDs must be investigated rather than overwritten.

```bash
export MIGRATION_TARGET_URI='mongodb://127.0.0.1:27018/?directConnection=true'
export MIGRATION_TARGET_DB='coyote4_migration_validation'
export MIGRATION_BUNDLE='/secure/migration/v3-hema-prepared'

mongoimport --uri "$MIGRATION_TARGET_URI" --db "$MIGRATION_TARGET_DB" \
  --collection samples --file "$MIGRATION_BUNDLE/samples.jsonl" --mode insert --stopOnError
mongoimport --uri "$MIGRATION_TARGET_URI" --db "$MIGRATION_TARGET_DB" \
  --collection sample_comments --file "$MIGRATION_BUNDLE/sample_comments.jsonl" --mode insert --stopOnError
mongoimport --uri "$MIGRATION_TARGET_URI" --db "$MIGRATION_TARGET_DB" \
  --collection reports --file "$MIGRATION_BUNDLE/reports.jsonl" --mode insert --stopOnError
```

Run a command only when that collection's file exists. For RNA payloads, repeat
with the matching `rna_expression`, `rna_classification` or `rna_qc` collection/file.
Do not import `source_samples.jsonl`: it is recovery evidence, not current sample
data. `mongoimport` is not atomic across collections; restore or reconcile an
interrupted import before continuing, and keep the target unavailable for clinical
use until all references and related-data stages are validated.

## Execution order

Follow the [dependency-ordered command runbook](../docs/operations/migrations/clinical-data.md).
Use [blacklist preparation](../docs/operations/migrations/variant-blacklist.md)
for shared allele exclusions and per-assay frequencies.
Use `--help` on each version-specific entry point to inspect its supported options.
