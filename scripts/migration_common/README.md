# Shared legacy migration implementation

Version-specific commands live in `../migrate_from_v2/` and `../upgrade_from_v3/`.
MongoDB is the migration destination. SQLite files are temporary local lookup
indexes over BSON exports; they are not an application database or a SQL migration.
The generated BSON bundles contain MongoDB documents. Only the separate
`apply_bundle.py --apply` step writes to the isolated MongoDB destination.

These modules share offline indexing, conversion, reconciliation, and target
application. See the [v2 runbook](../../docs/migration_from_v2/migration-guide.md)
and [v3 runbook](../../docs/migration_from_v3/migration-guide.md) for source contracts and execution order.

| Module | Responsibility |
| --- | --- |
| `schema_inventory.py` | Full-export nested field/type/shape inventory and snapshot-bound review checks |
| `offline.py` | BSON inventory, read-only SQLite access, private artifacts, and bundle manifests |
| `conversion.py` | Source-shape conversion with explicit historical evidence and scope |
| `vep.py`, `build_anno_vep.py` | Shared versioned transcript evidence from complete v2/v3 variant indexes, exact annotation matching, and bounded MongoDB bundles |
| `clinical_plan.py` | Related sample, finding, history, snapshot, and VEP reference checks |
| `commands.py` | Version-specific CLI behavior and reviewed TSV backfills |
| `apply_bundle.py` | Guarded local target preflight and transactional bundle application |
| `prepare_target.py`, `target_catalog.py` | Read-only validation and fingerprinting of preinstalled target configuration |
| `prepare_references.py` | Read-only verification of installed HGNC and historical VEP metadata prerequisites |
| `sample_scope.py` | Supported assay/source selection, tumwgs splitting and lowercase sample scope mapping |
| `run_report.py` | Private JSON and Markdown evidence for completed or blocked migration runs |

Only target preflight and bundle application open MongoDB connections. Neither has
a source connection or reads application environment files. Converters consume local
BSON-derived indexes; tests use synthetic fixtures and in-memory database doubles.

## Clinical field mappings

These mappings apply to both source versions. Version-specific collection names
and required inputs remain in their respective runbooks. Converters preserve
original BSON identities; applying a bundle does not generate replacement IDs.

| Source field | Validated bundle | Target persistence |
| --- | --- | --- |
| `samples.comments[]` | `sample_comments` with the owning sample identity/name | Separate documents retaining comment identity, author, text, dates and hiding metadata |
| `samples.reports[]` | `reports` with owning sample and reviewed assay/diagnosis/environment scope | Original report identities, numbers, authors, dates and file references |
| Finding `comments[]` | `finding_comments` with sample and finding ownership | Separate comments retaining the original history |
| `SAMPLE_ID`; snapshot `sample_oid` | Original sample relationship | Never inferred from a similarly named case |
| Sample `profile` | `environment` | Reviewed target configuration must agree |
| Sample/annotation `subpanel` | `diagnosis_id` | Conflicting or absent required scope needs reviewed reconciliation |
| Sample `case.id` / `control.id` | Missing `case_id` / `control_id` | Existing conflicting values are not silently replaced |
| Sample case/control `sequencing_run`, `reads` | Same nested fields | Preserve recorded values; no guessed runs or zero-filled counts |
| Top-level registered file paths | `files.<key>.path` | Multiple paths require explicit file reconciliation |
| Annotation `assay` | `asp_group` | Requires an installed target group; null scope needs a digest-bound mapping |
| Annotation `nomenclature`, `variant` | Corresponding `hgvsp`, `hgvsc` or `genomic` identity | Classification/text, authorship and creation time are preserved |
| Blacklist `assay` | `assay_group` | The destination adapter writes the existing repository field `assay` |
| Blacklist `_id`, `pos`, `in_normal_perc` | Same fields | Preserve original identity, position and frequency, including zero |

For annotations, a reviewed `scope.diagnosis` writes `diagnosis_id`;
`scope.assay_group` supplies the source assay mapping. Both require the original
record digest and a reason. Unknown scopes do not default to `base` or a configured
group. Blacklist records with the same position and scope are not collapsed: their
distinct identities remain in the bundle, and conflicting values require review.

### One-time annotation scope mappings

Annotation ownership is split between the source versions:

- **v3:** migrate only annotations whose assay group is `hematology`.
- **v2:** migrate annotations from every other assay group; exclude `hematology`.

Selection compares lowercase `assay`/`asp_group` after any digest-bound scope review,
before VEP enrichment and annotation conversion. Excluded annotations are not copied
or merged. Included annotations still require valid scopes and installed configuration.
The selection policy is recorded in CLI-generated bundle provenance. It does not
restrict which variants contribute evidence to the shared VEP reference.

The same policy applies to annotations linked from saved reports. If a sample's
saved report references an annotation excluded by this policy, conversion stops
with a private issue for review. It does not drop the historical link, substitute
an annotation from the other database, or reintroduce an excluded record. Such
references need explicit reconciliation before that sample can be converted.

The v2 and v3 annotation converters apply the following historical data mappings
supplied by the operator. These rules exist only in migration scripts; they do not
change application annotation behavior or sample scope mappings. They also apply
to annotations referenced by saved reports in sample bundles.

- Legacy `assay` becomes `asp_group`; legacy `subpanel` becomes `diagnosis_id`.
- Scope identifiers are lowercase, including `asp_group`, `asp_id`, and `diagnosis_id`.
- Annotation content, gene/transcript identities, classification, author, timestamps,
  and original `_id` are preserved.

| Legacy assay | Destination `asp_group` | Destination `asp_id` |
| --- | --- | --- |
| `myeloid` | `myeloid` | `myeloid_gmsv1` |
| `solid` | `solid` | `solid_gmsv3` |
| `hematology` | `hematology` | `hema_gmsv1` |

Only within the `solid` group, diagnosis aliases are:

| Legacy subpanel | Destination `diagnosis_id` |
| --- | --- |
| `BC` | `breast` |
| `BP` | `breast-pilot` |
| `CRC` | `crc` |
| `LP` | `lung` |
| Literal string `None` | `base` |
| `solid` | `base` |

Other diagnosis values retain their lowercase spelling. In particular, `colon`
remains `colon`; `lungthyroid` remains `lungthyroid`; outside `solid`, the literal
string `None` becomes `none`. Empty strings remain empty, and missing/null scope
values are not inferred from an empty grouped `_id`; unresolved required scopes
still need digest-bound review. No ASP is inferred for `gmsonco`, `lymphoid`,
`tumwgs`, or `unknown`. An explicitly supplied ASP is lowercased and must agree
with any mapping above. Target preflight checks mapped groups, ASPs, and diagnosis
associations against the installed configuration before application.

Saved report HTML/PDF and referenced analysis files require separate operator-managed
file transfer or retained compatible mounts. Database migration preserves their
references; it does not fetch remote files or recreate historical reports.

## Historical VEP evidence

The source clinical databases can contain transcript evidence in `INFO.CSQ` without
an `anno_vep` collection. Sample conversion builds versioned `anno_vep` records from
that evidence only when the original release is known. A source server's current
VEP metadata does not prove the release used for every historical finding.

`build_anno_vep.py` reads `variants_idref` from v2 and `variants` from v3 before
sample conversion. It emits a shared local reference and bounded `anno_vep` BSON
bundles for MongoDB. Compatible repeated evidence is combined; contradictory
consequences for one genomic identity, transcript and release stop the build.
No selected transcript is required merely to preserve all original consequences.

Annotation conversion uses `--vep-index` to match gene, nomenclature, variant and
the exact recorded transcript, including its version. A unique match supplies
`hgvsp`, `hgvsc`, `genomic` and `genomic_hash`. Classification/text, original identity,
author and creation time are retained. The target annotation contract chooses its
primary identity in protein, coding, genomic order. Ambiguous or absent matches
stop conversion; a versionless transcript is not silently upgraded.

Release provenance comes from recorded fields or reviewed per-sample metadata.
The selected reference must also have one recorded/reviewed genome build; combining
different builds into the same genomic-identity cache is rejected. Keep separate
references and isolated targets for different genome builds.
When a whole export is known to use one release, its private review can declare:

```json
{
  "vep_release": {
    "version": "103",
    "source_sha256": "SOURCE_SHA256_FROM_SCHEMA_AUDIT_MANIFEST",
    "evidence": "Reviewed historical pipeline or annotation release record"
  }
}
```

This is an explicit declaration, not a default. Conflicting recorded releases
are rejected. Known other releases are counted and excluded from the requested
reference; missing provenance blocks conversion. Do not label all historical v2
consequences as VEP 103 without evidence.

Legacy MongoDB 3.2 sources require compatible inspection/export tooling isolated
from the current application runtime. These converters consume offline BSON and
do not downgrade the application driver or connect to the live source.

## Migration commands, in order

Run these commands yourself from the repository root after preparing consistent
offline BSON exports with source-compatible tooling. The collection order is:
**HGNC/VEP metadata → anno_vep and findings → samples → annotations → saved finding
snapshots**. These scripts never connect to the legacy source databases. Reference
and target preflight read the isolated destination; conversion is offline. Only
the explicit `apply_bundle.py --apply` commands write clinical records to MongoDB.
Keep the destination application and workers offline until all stages are complete:
findings intentionally precede their owning sample documents during this process.

### 1. Select private working paths and the isolated target

```bash
MIGRATION_ROOT=/secure/coyote3-migration
V2="$MIGRATION_ROOT/v2"
V3="$MIGRATION_ROOT/v3"
VEP="$MIGRATION_ROOT/vep103"
TARGET_CATALOG="$MIGRATION_ROOT/target-catalog.json"
TARGET_DB=coyote4_migration_validation
TARGET_KB_DB=coyote4_migration_knowledgebase
REFERENCE_CATALOG="$MIGRATION_ROOT/reference-catalog.json"
```

Use existing private directories outside the checkout. Place consistent BSON
exports under `$V2/export/coyote` and `$V3/export/coyote3`. Set
`COYOTE_MIGRATION_TARGET_URI` through the approved secret store to an isolated local
MongoDB replica set. Do not use the source tunnel or the application production DB.

First install the normal knowledgebase catalogs using the supported installation
workflow; do not derive HGNC definitions or VEP metadata from clinical variants.
Both `vep_metadata` (including release 103) and `hgnc_genes` must be populated in
the isolated knowledgebase database. See the [knowledgebase operations guide](../../docs/operations/knowledgebase-updates.md)
for maintained reference import tools. Set `COYOTE_MIGRATION_KNOWLEDGEBASE_URI`
through the secret store to that isolated local knowledgebase, then verify it:

```bash
.venv/bin/python scripts/migration_common/prepare_references.py \
  --target-db "$TARGET_KB_DB" --vep-version 103 --output "$REFERENCE_CATALOG"
```

This command validates both reference contracts, requires nonempty collections
and the requested VEP metadata release, and records content fingerprints without
creating collections, indexes, or records.

### 2. Inventory and index each source

```bash
.venv/bin/python scripts/migrate_from_v2/audit_source_schema.py \
  --export-dir "$V2/export/coyote" --output "$V2/schema-audit"
.venv/bin/python scripts/migrate_from_v2/prepare_source.py \
  --export-dir "$V2/export/coyote" --index "$V2/source.sqlite"

.venv/bin/python scripts/upgrade_from_v3/audit_source_schema.py \
  --export-dir "$V3/export/coyote3" --output "$V3/schema-audit"
.venv/bin/python scripts/upgrade_from_v3/prepare_source.py \
  --export-dir "$V3/export/coyote3" --index "$V3/source.sqlite"
```

### 3. Snapshot target configuration and complete the reviews

This step reads the isolated destination; it does not change it:

```bash
.venv/bin/python scripts/migration_common/prepare_target.py \
  --target-db "$TARGET_DB" --output "$TARGET_CATALOG"
```

Install and validate destination configuration first. Create private `$V2/review.json`
and `$V3/review.json` according to the version-specific runbooks, including schema-audit
approval, source-file dispositions, VEP provenance, scope mappings and per-sample ASPC
selection. Missing case identity, historical pipeline evidence, transcript selection,
or mandatory clinical metadata requires reconciliation rather than invented defaults.

Legacy interval `coverage` has no equivalent current interval-coverage collection.
Its disposition must be reviewed explicitly; these scripts do not claim that it has
been converted into D4 measurements. Keep its original export. Current D4 sample
measurements come from v3 `panel_cov`/measurement-shaped `group_coverage` records.

### 4. Build the shared anno_vep collection bundles

```bash
.venv/bin/python scripts/migration_common/build_anno_vep.py \
  --source 2 "$V2/source.sqlite" "$V2/review.json" "$V2/schema-audit" \
  --source 3 "$V3/source.sqlite" "$V3/review.json" "$V3/schema-audit" \
  --vep-version 103 --target-catalog "$TARGET_CATALOG" \
  --reference-catalog "$REFERENCE_CATALOG" \
  --batch-size 1000 --output "$VEP" --issues "$MIGRATION_ROOT/vep-issues.json"
```

The root completion manifest records counts, release, source/review fingerprints,
and a checksum. `anno_vep.sqlite` is the local lookup cache used by annotation
conversion. Numbered directories under `$VEP/bundles` are the MongoDB apply bundles.
A failed build has no root completion manifest and must not be applied.

### 5. Select one assay and build its variants and related findings

Use one supported destination `--assay-id` per invocation. Names are normalized to
lowercase. The source version is checked; an assay cannot be taken from the other
database.

| Source | Supported destination ASP IDs |
| --- | --- |
| v3 | `gmshem`, `hema_gmsv1` |
| v2 | `parp_inhib`, `fusion`, `fusion_validation_nf`, `lymph_gmsv3`, `lymphoid_gmsv1`, `myeloid_gmsv1`, `solidrna_gmsv5`, `solid_gmsv3`, `tumwgs-hema`, `tumwgs-solid`, `twistrnafusionv1-0` |

`GMSHem` becomes `gmshem`; it is not silently renamed to `hema_gmsv1`.
Legacy `tumwgs` with subpanel `hema` selects `tumwgs-hema`; with `solid` it
selects `tumwgs-solid`. Other/missing tumwgs subpanels require reconciliation.
The original subpanel becomes lowercase `diagnosis_id`; the selected installed
ASP supplies `asp_group`. The reviewed ASPC must agree with both the selected
ASP and recorded diagnosis. No new ObjectIds are generated for samples.

Set the source field explicitly using `--assay-field group`, `assay`, or `asp_id`;
the converter does not guess which field contains the listed assay names. For example,
if they are in `group`, prepare one v3 assay:

```bash
ASSAY_ID=hema_gmsv1
ASSAY_FIELD=group
SOURCE="$V3"
MIGRATOR=scripts/upgrade_from_v3/migrate_samples.py
```

For a v2 assay, change only the selected assay, source and wrapper, for example:

```bash
ASSAY_ID=myeloid_gmsv1
ASSAY_FIELD=group
SOURCE="$V2"
MIGRATOR=scripts/migrate_from_v2/migrate_samples.py
```

Run the following command for the selected assay. It includes `variants` and
other supported findings, finding comments, RNA results, D4 measurements and the
matching shared `anno_vep` records. It excludes samples, reports and clinical
annotations. The shared VEP build in step 4 still merges evidence across both
exports so overlapping genomic records remain consistent across assay batches.

```bash
.venv/bin/python "$MIGRATOR" \
  --index "$SOURCE/source.sqlite" --schema-audit "$SOURCE/schema-audit" \
  --target-catalog "$TARGET_CATALOG" --review "$SOURCE/review.json" \
  --vep-index "$VEP" --assay-id "$ASSAY_ID" --assay-field "$ASSAY_FIELD" \
  --stage findings --output "$SOURCE/$ASSAY_ID-findings" \
  --issues "$SOURCE/$ASSAY_ID-findings-issues.json"
```

### 6. Convert the selected assay's samples, retaining original ObjectIds

```bash
.venv/bin/python "$MIGRATOR" \
  --index "$SOURCE/source.sqlite" --schema-audit "$SOURCE/schema-audit" \
  --target-catalog "$TARGET_CATALOG" --review "$SOURCE/review.json" \
  --vep-index "$VEP" --assay-id "$ASSAY_ID" --assay-field "$ASSAY_FIELD" \
  --stage samples --output "$SOURCE/$ASSAY_ID-samples" \
  --issues "$SOURCE/$ASSAY_ID-samples-issues.json"
```

This stage contains `samples`, sample comments and report references, preserving
the original sample `_id` and related identities. It does not convert annotations
or saved finding snapshots. Findings continue to reference the original sample ID.

### 7. Convert annotations after VEP evidence and samples are available

```bash
.venv/bin/python scripts/upgrade_from_v3/migrate_annotations.py \
  --index "$V3/source.sqlite" --schema-audit "$V3/schema-audit" \
  --target-catalog "$TARGET_CATALOG" --review "$V3/review.json" \
  --vep-index "$VEP" --output "$V3/annotations" --issues "$V3/annotation-issues.json"

.venv/bin/python scripts/migrate_from_v2/migrate_annotations.py \
  --index "$V2/source.sqlite" --schema-audit "$V2/schema-audit" \
  --target-catalog "$TARGET_CATALOG" --review "$V2/review.json" \
  --vep-index "$VEP" --output "$V2/annotations" --issues "$V2/annotation-issues.json"
```

These commands retain v3 hematology annotations and v2 non-hematology annotations.
For one annotation ASP at a time, add `--assay-id hema_gmsv1` to the v3 command
or the appropriate supported v2 ASP to the v2 command, and use a unique output
directory. Filtering uses the mapped annotation ASP; it does not infer new annotation
ownership from sample assay names. Group-only annotations without an ASP need
reviewed ASP attribution before they can be selected by this option.

### 8. Convert blacklists

```bash
.venv/bin/python scripts/upgrade_from_v3/migrate_blacklist.py \
  --index "$V3/source.sqlite" --schema-audit "$V3/schema-audit" \
  --target-catalog "$TARGET_CATALOG" --review "$V3/review.json" --output "$V3/blacklist"

.venv/bin/python scripts/migrate_from_v2/migrate_blacklist.py \
  --index "$V2/source.sqlite" --schema-audit "$V2/schema-audit" \
  --target-catalog "$TARGET_CATALOG" --review "$V2/review.json" --output "$V2/blacklist"
```

V3 actual coverage exclusions use `migrate_d4_coverage_blacklist.py` with the same
index, audit, catalog and review arguments and a separate output directory. Sample
coverage measurements are handled in step 5, not by the exclusion converter.

### 9. Complete saved finding snapshots for the selected assay

```bash
.venv/bin/python "$MIGRATOR" \
  --index "$SOURCE/source.sqlite" --schema-audit "$SOURCE/schema-audit" \
  --target-catalog "$TARGET_CATALOG" --review "$SOURCE/review.json" \
  --vep-index "$VEP" --assay-id "$ASSAY_ID" --assay-field "$ASSAY_FIELD" \
  --stage complete --output "$SOURCE/$ASSAY_ID-complete" \
  --issues "$SOURCE/$ASSAY_ID-complete-issues.json"
```

| Related data | Handling |
| --- | --- |
| Small variants | v3 `variants`; v2 `variants_idref`, with original consequences and selected transcript |
| CNVs | v3 `cnvs`; v2 `cnvs_wgs`, preserving recorded interval evidence |
| Fusions | v2 `fusions`; the inspected v3 source has no fusion collection |
| Structural variants | Both versions' `transloc` to `translocations` |
| Biomarkers | Both versions' `biomarkers`; units and conflicting scalar/typed measurements require review |
| D4 sample coverage | v3 `panel_cov` and measurement-shaped `group_coverage`, with explicit duplicate selection |
| RNA measurements | Embedded `expr`, `QC`, `classification` to `rna_expression`, `rna_qc`, `rna_classification` |
| Comments | Sample and finding comments retain identities, ownership, authorship, timestamps and hiding state |
| Reports | Embedded report references retain IDs, dates, authors, numbers and file paths |
| Reported findings | v3 `reported_variants`, retaining report, finding, annotation and sample-comment references |
| Shared annotations and VEP | Linked snapshot annotations are included; shared reference records use the same completed VEP index |

Each numbered directory contains one sample's selected migration stage and a private
conversion report. In `complete` mode it includes all supported related collections.
The root manifest is written only after all selected samples succeed.
Multiple embedded QC results require review; the converter does not average them or
choose one silently. Files referenced by reports or analyses require separate transfer.

If importing both sources into one target, review overlapping sample and annotation
identities before applying either set. Existing differing records are never overwritten.
Use `--sample-ids-file /private/selected-sample-ids.json`, a JSON array of source ID
strings, to convert an explicit subset; default behavior converts every source sample.
For one sample, use `migrate_sample.py --sample-id ID` with the same other arguments.

### 10. Preflight each target bundle without writing

```bash
.venv/bin/python scripts/migration_common/apply_bundle.py \
  --bundle "$VEP/bundles/000001" --target-db "$TARGET_DB"
```

Inspect each completion manifest, issue report, counts and target preflight before
applying. Preflight is read-only; it does not prove a later concurrent target change
will be acceptable. Application rechecks the target catalog and conflicts transactionally.

### 11. Apply approved bundles to MongoDB, one stage at a time

These commands write to the isolated destination. They are not run automatically by
conversion. First apply the VEP bundles:

```bash
(
  set -e
  test -f "$VEP/manifest.json"
  for bundle in "$VEP"/bundles/[0-9]*; do
    test -d "$bundle" || continue
    .venv/bin/python scripts/migration_common/apply_bundle.py \
      --bundle "$bundle" --target-db "$TARGET_DB" --apply
  done
)
```

Apply findings first, then samples, for the selected assay:

```bash
(
  set -e
  for stage in findings samples; do
    test -f "$SOURCE/$ASSAY_ID-$stage/manifest.json"
    for bundle in "$SOURCE/$ASSAY_ID-$stage"/[0-9]*; do
      test -d "$bundle" || continue
      .venv/bin/python scripts/migration_common/apply_bundle.py \
        --bundle "$bundle" --target-db "$TARGET_DB" --apply
    done
  done
)
```

Apply each reviewed source's annotations and blacklists after the sample stage.
If annotations were prepared with `--assay-id`, replace the annotations bundle
path with that assay-specific output directory:

```bash
.venv/bin/python scripts/migration_common/apply_bundle.py \
  --bundle "$V3/annotations" --target-db "$TARGET_DB" --apply
.venv/bin/python scripts/migration_common/apply_bundle.py \
  --bundle "$V2/annotations" --target-db "$TARGET_DB" --apply
.venv/bin/python scripts/migration_common/apply_bundle.py \
  --bundle "$V3/blacklist" --target-db "$TARGET_DB" --apply
.venv/bin/python scripts/migration_common/apply_bundle.py \
  --bundle "$V2/blacklist" --target-db "$TARGET_DB" --apply
```

Then apply the selected assay's complete bundles to finish saved finding snapshots.
Identical findings and samples from earlier stages are verified and skipped;
conflicts stop the transaction:

```bash
(
  set -e
  test -f "$SOURCE/$ASSAY_ID-complete/manifest.json"
  for bundle in "$SOURCE/$ASSAY_ID-complete"/[0-9]*; do
    test -d "$bundle" || continue
    .venv/bin/python scripts/migration_common/apply_bundle.py \
      --bundle "$bundle" --target-db "$TARGET_DB" --apply
  done
)
```

Stop at any failure and inspect the private report before continuing. Each bundle
has its own transaction; there is no transaction spanning the entire migration.
Identical existing records are skipped on retry; conflicting records block writes.
Validate the isolated application's counts, clinical workflows and report artifacts
before arranging a separate reviewed production cutover.
