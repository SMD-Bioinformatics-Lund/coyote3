# Clinical data migration: execution order

Use the fresh converters in `migrations_scripts/v2` for `coyote` and
`migrations_scripts/v3` for `coyote3`. Run from the repository root. Exporting reads
the source; preparation writes local Extended JSON only. Importing is a separate,
explicit operator step. Never point an import at either source database.

The [collection dependency diagrams](../../reference/collection-dependencies/README.md)
explain the keys behind this order. Preparation order differs from import order:
the local sample bundle provides the original sample ObjectIds used to select
findings, even when the shared VEP vault is imported before samples.

## Select the source version

| Existing application | Source database | Converter directory | Export selection |
| --- | --- | --- | --- |
| Coyote v2 | `coyote` | `migrations_scripts/v2/` | `SOURCE_VERSION=2` |
| Coyote v3 | `coyote3` | `migrations_scripts/v3/` | `SOURCE_VERSION=3` |

Both versions use the steps below. The version-specific directories provide
`migrate_samples.py`, `migrate_variants.py` and `migrate_related.py`. Select one
supported lowercase assay ID at a time. Preserve original sample ObjectIds and
prepare related records only for the selected samples. Keep source exports and
review artifacts private; source reads do not authorize destination imports.

## Source inspection and field mappings

Run sample `inspect --all-samples` and collection-specific `inspect` commands in
step 3. Inspection records nested keys and BSON types without inferring missing
values. Check the source-version mappings before accepting prepared output:

- [Observed source structures](https://github.com/SMD-Bioinformatics-Lund/coyote3/blob/api/migrations_scripts/source-structures.md)
- [Sample scope and field mappings](https://github.com/SMD-Bioinformatics-Lund/coyote3/blob/api/migrations_scripts/README.md)
- [Related collections and coverage classification](https://github.com/SMD-Bioinformatics-Lund/coyote3/blob/api/migrations_scripts/related-data.md)
- [Variants and VEP 103 evidence](https://github.com/SMD-Bioinformatics-Lund/coyote3/blob/api/migrations_scripts/variants.md)

## 1. Prepare destination references and configuration

Install `hgnc_genes` and `vep_metadata`, including VEP **103**, through
[center installation](../../deployment/first-installation.md). For separately
reviewed references use the [HGNC procedure](../hgnc-gene-installation.md) and
[VEP procedure](../vep-metadata-updates.md). Do not reannotate historical findings
with a different release.

Create assay groups, diagnosis definitions, assays, assay–diagnosis associations,
gene lists, query rules and configuration revisions using
[assay setup](../../administration/assay-setup.md). Select the exact destination
`current_aspc_id` for every sample review. Identifiers use lowercase; original
sample ObjectIds and specimen identifiers retain their identity.

Clinical reporting rule sets are optional. Publish reviewed narrative rules when
available; missing rules allow reports without generated summary text and produce
a UI warning. Existing historical report snapshots retain their original content.

Configure read-only Bjorn/CDM enrichment using
[the case/control configuration reference](https://github.com/SMD-Bioinformatics-Lund/coyote3/blob/api/migrations_scripts/case-control.md).
The cross-check database is `CMD` (uppercase). Its verified `files` collection
uses `sample-id`, `assay` and `run`. Configure the SSH destination and reviewed
assay aliases before preparation; the configuration section is named `cdm`.

## 2. Export one assay, automatically in batches of 500

```bash
umask 077
export MIGRATION_SSH_HOST='operator@source-host'
export MIGRATION_ROOT='/secure/migration'
export SOURCE_VERSION=3
export ASSAY_ID='hema_gmsv1'

.venv/bin/python migrations_scripts/export_assay.py \
  --source-version "$SOURCE_VERSION" --assay-id "$ASSAY_ID" \
  --ssh-host "$MIGRATION_SSH_HOST" \
  --output "$MIGRATION_ROOT/exports/v$SOURCE_VERSION-$ASSAY_ID"
```

For v2, set `SOURCE_VERSION=2` and the supported assay ID, for example
`solid_gmsv3`, and run the same command. Export resumes only with `--resume` and
the same parameters/output directory. Completed batches are not exported again.
Wait for the completed root manifest before preparation. See
[export selection and checkpoints](https://github.com/SMD-Bioinformatics-Lund/coyote3/blob/api/migrations_scripts/exporting.md).

## 3. Inspect and prepare the sample bundle for each batch

```bash
export BATCH='batch-000001'
export SOURCE_BATCH="$MIGRATION_ROOT/exports/v$SOURCE_VERSION-$ASSAY_ID/$BATCH"
export WORK="$MIGRATION_ROOT/prepared/v$SOURCE_VERSION-$ASSAY_ID/$BATCH"
mkdir -p "$WORK"

.venv/bin/python "migrations_scripts/v$SOURCE_VERSION/migrate_samples.py" inspect \
  --assay-id "$ASSAY_ID" --input "$SOURCE_BATCH/samples.jsonl" \
  --all-samples --output "$WORK/inspection"

cp "$WORK/inspection/review-template.json" "$WORK/review.json"
```

Complete `review.json` with reviewed metadata and the exact installed configuration
revision. Preserve each source digest. The
[sample conversion reference](https://github.com/SMD-Bioinformatics-Lund/coyote3/blob/api/migrations_scripts/README.md#2-complete-the-source-bound-review)
lists required review fields and supported source mappings.

```bash
.venv/bin/python "migrations_scripts/v$SOURCE_VERSION/migrate_samples.py" prepare \
  --assay-id "$ASSAY_ID" --input "$SOURCE_BATCH/samples.jsonl" \
  --review "$WORK/review.json" \
  --case-control-config "$MIGRATION_ROOT/case-control.json" \
  --output "$WORK/samples"
```

This prepares samples and embedded comments, reports and RNA records. It does not
insert samples yet. Every recorded case/control is enriched independently. Failed
runs are excluded; multiple runs require CDM confirmation. Private source/evidence
files are retained but are not destination collections.

## 4. Build variants and the cumulative VEP vault

Run only for nonempty exported variant collections:

```bash
.venv/bin/python "migrations_scripts/v$SOURCE_VERSION/migrate_variants.py" \
  --collection variants --input "$SOURCE_BATCH/variants.jsonl" \
  --sample-bundle "$WORK/samples" --output "$WORK/variants"
```

For v2 `variants_idref` (not a v3 collection), use a separate output directory
and continue the vault. If it is the first variant collection, omit
`--prior-bundle`; otherwise point it at the last completed bundle:

```bash
.venv/bin/python migrations_scripts/v2/migrate_variants.py \
  --collection variants_idref --input "$SOURCE_BATCH/variants_idref.jsonl" \
  --sample-bundle "$WORK/samples" --prior-bundle "$WORK/variants" \
  --output "$WORK/variants-idref"
```

Carry `--prior-bundle` from the most recent completed variant bundle into the next
collection, batch or assay, including across v3/v2. Omit it only for the first
bundle. This merges shared `anno_vep` evidence. For overlap checking, repeat
`--prior-bundle` for every earlier bundle that may contain the same sample/finding;
the last vault is cumulative, but its variant file contains only its own findings.
If v2 lacks `selected_CSQ`, explicitly add `--select-missing-csq --hgnc-genes
/secure/migration/hgnc-genes.jsonl` using a reviewed reference export. Existing
selections remain unchanged. See the
[variant mapping and transcript-selection reference](https://github.com/SMD-Bioinformatics-Lund/coyote3/blob/api/migrations_scripts/variants.md).

## 5. Prepare other sample-owned collections

For each nonempty collection supported by `migrate_related.py --help`, run:

```bash
export COLLECTION='cnvs'
.venv/bin/python "migrations_scripts/v$SOURCE_VERSION/migrate_related.py" inspect \
  --collection "$COLLECTION" --input "$SOURCE_BATCH/$COLLECTION.jsonl" \
  --sample-bundle "$WORK/samples" --output "$WORK/$COLLECTION-inspection"

.venv/bin/python "migrations_scripts/v$SOURCE_VERSION/migrate_related.py" prepare \
  --collection "$COLLECTION" --input "$SOURCE_BATCH/$COLLECTION.jsonl" \
  --sample-bundle "$WORK/samples" --output "$WORK/$COLLECTION"
```

Repeat for applicable CNVs, translocations, biomarkers, fusions, coverage, PGx and
RNA expression/classification/QC. Review any required collection-specific metadata
before preparation. The
[related-data reference](https://github.com/SMD-Bioinformatics-Lund/coyote3/blob/api/migrations_scripts/related-data.md)
documents review and coverage-map options. Match by `SAMPLE_ID`/`sample_oid`, never
by a similar sample name. Coverage is classified per document; do not map all
coverage collections to `d4_coverage`. Prepare `reported_variants` last, after its
report and finding owners have been prepared.

Group-level v3 coverage exclusions use a separately reviewed export:

```bash
.venv/bin/python migrations_scripts/v3/migrate_coverage_blacklist.py \
  --input "$MIGRATION_ROOT/group_coverage.jsonl" --group hematology \
  --output "$MIGRATION_ROOT/coverage-exclusions-hematology"
```

## 6. Review completion and import in dependency order

Repeat steps 3–5 for every batch. Check completion manifests, checksums, counts,
original IDs, author/timestamp retention, report pointers and exact configuration
revisions. Never import a failed/partial preparation. Keep an import ledger by
bundle and file checksum: exporter resume is not an import checkpoint.

| Import order | Collection/files |
| --- | --- |
| 1 | Installed references, assay resources, published configurations and any applicable published rules |
| 2 | Only the **last cumulative** `anno_vep.jsonl`, once |
| 3 | All nonoverlapping `samples.jsonl` bundles, retaining original ObjectIds |
| 4 | Per-bundle `variants`, CNVs, translocations, fusions, biomarkers, coverage and RNA data |
| 5 | Sample/finding comments and shared curation after their referenced owners |
| 6 | Reports, then saved `reported_variants` snapshots |

Example explicit import into a separate destination:

```bash
export TARGET_MONGO_URI='mongodb://127.0.0.1:27018/?directConnection=true'
export TARGET_MONGO_DB='coyote4_migration_validation'
export FINAL_VARIANT_BUNDLE='/secure/migration/REPLACE_WITH_LAST_VARIANT_BUNDLE'

mongoimport --uri "$TARGET_MONGO_URI" --db "$TARGET_MONGO_DB" \
  --collection anno_vep --mode insert --stopOnError \
  --file "$FINAL_VARIANT_BUNDLE/anno_vep.jsonl"
mongoimport --uri "$TARGET_MONGO_URI" --db "$TARGET_MONGO_DB" \
  --collection samples --mode insert --stopOnError --file "$WORK/samples/samples.jsonl"
mongoimport --uri "$TARGET_MONGO_URI" --db "$TARGET_MONGO_DB" \
  --collection variants --mode insert --stopOnError --file "$WORK/variants/variants.jsonl"
```

Repeat the explicit collection/file command for each reviewed output, in the table's
order. Do not import source archives, reference evidence, manifests, earlier
cumulative vaults, or the same finding from overlapping source collections twice.
Do not use upsert to hide identity conflicts. Mongoimport is not atomic across
collections; reconcile an interrupted import before continuing. Preserve referenced
report files and analysis artifacts separately.

## Shared curation still requiring a converter

Use the [variant blacklist converter](variant-blacklist.md) to prepare shared
exclusions after the assay definitions are available. The fresh scripts do not
yet convert shared `annotation`.
Do not substitute embedded finding comments for these resources or claim a complete
clinical migration without them. The removed converters are not part of this
procedure. Annotation preparation must follow the VEP vault: v3 supplies hematology
annotations, v2 supplies the other assays, with matching VEP 103 transcripts and
the agreed lowercase scope mappings. `assay` maps to `asp_group`, `subpanel` to
`diagnosis_id`, and physical assay mappings are `myeloid` → `myeloid_gmsv1`,
`solid` → `solid_gmsv3`, `hematology` → `hema_gmsv1`. Apply the
[documented diagnosis renames](https://github.com/SMD-Bioinformatics-Lund/coyote3/blob/api/migrations_scripts/README.md#scope-and-mapping).
Saved report references must be reconciled
after that stage. Keep the destination unavailable for clinical reporting until
these references and all migrated records have been validated.
