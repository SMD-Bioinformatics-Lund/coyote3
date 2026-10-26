# Non-variant sample-related data

Use `v2/migrate_related.py` for `coyote` exports and `v3/migrate_related.py` for
`coyote3` exports. These fresh converters operate on Extended JSON files, require
a completed sample bundle, and never connect to or write a database. Run one source
collection at a time. The sample bundle selects the assay and retains original
sample ObjectIds. Only records with `SAMPLE_ID` matching those migrated ObjectIds
are converted. Saved report findings use their existing BSON `sample_oid` instead.
Records with another, missing or malformed owner are counted and excluded; names
and file paths are never used to infer ownership.

`variants` and `anno_vep` are explicitly excluded. Saved report findings in
`reported_variants` are included because they are report history; their underlying
variant documents are neither read nor migrated by these scripts.

## Collection selection

Read-only random inspection confirmed the following source formats. Required values
are validated against current collection contracts; missing measurements are not
reconstructed from application defaults.

| Source collection | Version | Destination | Mapping |
| --- | --- | --- | --- |
| `cnvs` | v2, v3 | `cnvs` | Preserve interval CNVs; v2 VCF-shaped CNVs use recorded `CHROM`, `POS`, `INFO.END`, `INFO.SVLEN`, `INFO.PROBES`, `INFO.genes` and `INFO.FOLD_CHANGE_LOG`. |
| `cnvs_wgs` | v2 | `cnvs` | Preserve original intervals, ratios, genes, classification, callers and IDs. |
| `transloc` | v2, v3 | `translocations` | Normalize numeric chromosome, FILTER text, missing QUAL marker, PANEL text and `GT._sample_id` → `GT.sample`. |
| `fusions` | v2 | `fusions` | Preserve original gene pairs, caller records, support counts and selection. |
| `biomarkers` | v2, v3 | `biomarkers` | Rename recorded `MSIS.perc` / `MSIP.perc` to `per` without changing the percentage scale; preserve HRD components. |
| `coverage`, `panel_cov`, `group_coverage` | As present in the source | Per-document destination | Classify each record; a source collection may mix formats. |
| `reported_variants` | v3 | `reported_variants` | Preserve saved text, tiers, authors, dates and original report/finding/annotation pointers; validate report and comment ownership. |
| Embedded finding `comments[]` | Both | `finding_comments` | Extract original IDs, authors, timestamps, hiding metadata and text with exact sample/finding ownership. |

The scripts also accept canonical `pgx`, `rna_expression`, `rna_qc`,
`rna_classification` exports. V3 can accept a canonical `fusions` export and v2
can accept a saved `reported_variants` export. Those separate collections were not
present in the inspected source databases; do not manufacture exports for them.
Embedded RNA results, sample comments and reports are already handled by
[the sample converters](README.md). Incomplete embedded RNA QC retains the agreed
unchanged form on its owning sample.

The original `SAMPLE_ID` is normally a string representation of `samples._id`.
Report findings use BSON `sample_oid`. Ownership must be recorded explicitly.
Some old coverage rows have only a `sample` display name: those rows remain
excluded even when the name matches a migrated sample. Conflicting owner fields
on a selected record fail conversion.

Coverage destinations are determined by their contents:

| Document shape | Destination and handling |
| --- | --- |
| `genes` dictionary with gene/transcript/exon/CDS/probe measurements | `d4_coverage`, preserving the structured measurements and original ObjectId. |
| `chr`, `start`, `end`, `avg_cov` intervals | `coverage`, preserving original normal coverage; no D4 hierarchy is manufactured. |
| `group`, `gene`, `region` exclusions | `d4_coverage_blacklist` through the separate group-scoped command below. |

Normal `coverage` is retained as historical data; it is not presented as D4 coverage
by the current application. Unknown or ambiguous shapes fail validation when
selected. Blacklist exclusions are scope-level configuration, not sample-owned
measurements, so the sample step only counts them and never imports them.

## 1. Export and inspect one collection

Use the server's installed MongoDB 3.2 `mongoexport`, as described in the
[sample procedure](README.md#1-inspect-random-documents-read-only). For example:

```bash
umask 077
export MIGRATION_SSH_HOST='operator@source-mongodb-host'

ssh "$MIGRATION_SSH_HOST" \
  'mongoexport --host 127.0.0.1 --port 27017 --db coyote --collection cnvs_wgs --type=json' \
  > /secure/migration/v2-cnvs_wgs.jsonl
ssh "$MIGRATION_SSH_HOST" \
  'mongoexport --host 127.0.0.1 --port 27017 --db coyote3 --collection cnvs --type=json' \
  > /secure/migration/v3-cnvs.jsonl
```

Check successful SSH/export exit status before using either file. A failed export
can leave a partial file. Use a consistent source snapshot for final conversion;
sequential live exports do not establish a point-in-time snapshot.

```bash
.venv/bin/python migrations_scripts/v2/migrate_related.py inspect \
  --collection cnvs_wgs --input /secure/migration/v2-cnvs_wgs.jsonl \
  --sample-bundle /secure/migration/v2-myeloid-prepared \
  --random-documents 20 --output /secure/migration/v2-cnvs_wgs-inspection
```

`--sample-bundle` is the corresponding completed sample-conversion output. No full
source-samples export is needed for selection. Its completion flag,
source version and file checksums are verified before reading related data.

Inspection scans the input once, counts selected/out-of-selection/unlinked records,
and reservoir-samples selected documents. It writes private `structure.json`,
`sampled_source.jsonl` and `review-template.json`. Output directories must be new
and are created with mode `0700`. Terminal output contains counts, not source values.

## 2. Prepare one collection

```bash
.venv/bin/python migrations_scripts/v2/migrate_related.py prepare \
  --collection cnvs_wgs --input /secure/migration/v2-cnvs_wgs.jsonl \
  --sample-bundle /secure/migration/v2-myeloid-prepared \
  --output /secure/migration/v2-myeloid-cnvs_wgs

.venv/bin/python migrations_scripts/v3/migrate_related.py prepare \
  --collection cnvs --input /secure/migration/v3-cnvs.jsonl \
  --sample-bundle /secure/migration/v3-hema-prepared \
  --output /secure/migration/v3-hema-cnvs
```

Run the same command separately with the collection and input file changed:

| Entry point | Collections to select individually |
| --- | --- |
| v2 | `cnvs`, `cnvs_wgs`, `transloc`, `biomarkers`, `fusions`, `coverage` |
| v3 | `cnvs`, `transloc`, `biomarkers`, `coverage`, `panel_cov`, `group_coverage`, `reported_variants` |

Preparation writes current destination files, `source_records.jsonl` with untouched
selected originals, and a final `manifest.json` with counts, input/map hashes and
output checksums. Comments are written to `finding_comments.jsonl`. Original source
ObjectIds are retained. Multiple source intervals require one deterministic parent
coverage ID; their original ObjectIds remain on the individual converted regions.

Only `complete: true` marks finished conversion. Failure writes private
`failure.json`, exits nonzero and leaves no completed manifest. Partial outputs
must not be imported. The completion flag describes conversion of the selection,
not completion of all clinical-data migrations or validation of external pointers.

Pass `--prior-bundle /secure/migration/previous-related-output` when preparing
another collection for the same target; repeat it for multiple earlier outputs.
It verifies their checksums and rejects duplicate destination IDs or a second D4
coverage document for the same sample. This matters for the two v2 CNV sources and
v3 `panel_cov` / `group_coverage`: do not silently choose the first, overwrite one,
average measurements, or import both coverage representations for one sample.
Choose the reviewed source for each sample and prepare it with the corresponding
sample-bundle selection.

## Selection and missing values

The migrated ObjectIds in `--sample-bundle` are the complete selection boundary.
A related record with a valid but unselected owner is counted as `outside_selection`.
Missing or malformed owner values are counted as `unlinked`. Neither category is
converted, archived into the selected bundle, or used to block that bundle. Only
selected source records are written to `source_records.jsonl`. Nothing is deleted
from the source, and no additional sample parents are created.

Group-level coverage exclusions are counted as `non_sample_exclusions` and skipped
by the sample step, including exclusions found in a mixed source collection.

For a missing required field, complete the inspection's review template with exact
source evidence, then pass `--review /secure/migration/related-review.json`:

```json
{
  "records": {
    "000000000000000000000001": {
      "source_sha256": "REPLACE_WITH_GENERATED_SOURCE_SHA256",
      "reason": "Verified original caller selection in the source evidence",
      "fields": {"calls.0.selected": 1}
    }
  }
}
```

Dotted paths support array indices. Reviews may add absent/null fields but cannot
replace recorded values, `_id`, `SAMPLE_ID` or `sample_oid`. They are bound to the
exact original source hash. Missing translocation SOMATIC/support fields or missing
fusion selection are not assigned defaults. A recorded TMB result must explicitly
state `mut/Mb`; scalar values do not establish units. Non-numeric CNV ratios are
not silently translated into new measured values.

## Interval coverage map

Old normal coverage rows contain `amplicon`, `chr`, `start`, `end`, `avg_cov` and sample
ownership. They do not supply the target's gene/transcript hierarchy. Provide
`--coverage-map /secure/migration/coverage-map.json` only when deliberately converting
those normal intervals to D4 using verified assay/reference metadata. Without this
option, normal intervals remain unchanged in `coverage`, even in a collection that
also contains native D4 records. This synthetic example illustrates the accepted keys:

```json
{
  "SYNTHETIC_AMPLICON": {
    "gene": "TP53",
    "covered_by_panel": true,
    "transcript": {
      "chr": "1", "start": 90, "end": 200,
      "transcript_id": "SYNTHETIC_TRANSCRIPT"
    },
    "region_kind": "exons",
    "region_id": "synthetic_exon_1",
    "nbr": 1
  }
}
```

`region_kind` is `exons`, `CDS` or `probes`. `nbr` is optional for exon/CDS records.
Depth and coordinates always come from the original interval. The map supplies
identity/membership, not new measurements. Chromosome disagreement, reversed
intervals, negative/non-finite depths, conflicting transcripts or repeated mapped
regions block conversion. No coordinate liftover or coverage averaging is performed.

For example:

```bash
.venv/bin/python migrations_scripts/v2/migrate_related.py prepare \
  --collection coverage --input /secure/migration/v2-coverage.jsonl \
  --sample-bundle /secure/migration/v2-myeloid-prepared \
  --coverage-map /secure/migration/coverage-map.json \
  --output /secure/migration/v2-myeloid-coverage
```

The converter stages selected intervals in protected per-sample files and builds
one sample's coverage at a time. It does not load the entire interval collection
into memory or use SQLite. Staging files are removed after success or failure;
the selected original records remain in the output archive.

## D4 coverage blacklist

Group-level exclusions have no sample ObjectId relationship. Prepare them separately,
one explicitly selected group at a time; do not derive group membership from sample
names or assign a fabricated `SAMPLE_ID`:

```bash
.venv/bin/python migrations_scripts/v3/migrate_coverage_blacklist.py \
  --input /secure/migration/v3-group_coverage.jsonl \
  --group hematology \
  --output /secure/migration/v3-hematology-coverage-blacklist
```

The input can be any coverage export containing exclusion documents; the shape,
not its filename, decides whether it is an exclusion. The command preserves IDs,
authors, timestamps, genes and region coordinates, lowercases the group ID,
validates the `d4_coverage_blacklist` contract and excludes measurements and other
groups. The referenced assay group must already exist at the destination.

## Saved report findings and import

`reported_variants` verifies that `report_oid` and any `sample_comment_oid` resolve
within the prepared sample bundle and belong to the same sample. It derives a
missing identity hash from the retained `simple_id`, rejects a conflicting hash,
and maps recorded `SNV`/`INDEL` types to explicit SNV analysis. Other declared
finding types retain their own analysis. It does not regenerate text, tier, class,
or transcript selection from current evidence.

Original `var_oid`, `annotation_oid` and `annotation_text_oid` remain unchanged.
These reference collections are outside this converter. Check their existence,
sample ownership and semantic identity after the corresponding migrations and
before clinical use. No new variant or annotation documents are emitted.

After reviewing a completed manifest and checksums, use the
[separate destination import procedure](README.md#4-import-reviewed-files-into-a-separate-destination).
Import only the named current destination files and any `finding_comments.jsonl`.
Never import `source_records.jsonl` or `sampled_source.jsonl` into current clinical
collections. Cross-collection
imports are not atomic; keep an incomplete destination unavailable for clinical use.

See the [dependency-ordered execution guide](../docs/operations/migrations/clinical-data.md)
for preparation and import order across batches and collections.
