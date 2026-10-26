# Variants, VEP evidence and finding comments

Use `v2/migrate_variants.py` for `coyote.variants` or `coyote.variants_idref` and
`v3/migrate_variants.py` for `coyote3.variants`. These fresh converters read local
Extended JSON exports and write import files. They do not connect to MongoDB.
Prepare one assay's [sample bundle](README.md) first. Its samples do not need to
have been imported: the bundle supplies the original sample ObjectIds and recorded
database versions used to select and validate findings.

## Inputs and references

All v2 and v3 source variants use VEP 103, as confirmed by the data owner.
Install or prepare the VEP 103 `vep_metadata` and the `hgnc_genes` references before
preparing annotations. This stage does not download references or run VEP.

The read-only source inspection found numeric chromosomes and scalar FILTER values
in v2, and full VEP transcript rows without selected consequences in both v2 source
collections. Sampled v3 findings contained `INFO.CSQ`, `INFO.selected_CSQ` and its
selection criterion, plus precomputed annotation summaries. Random inspection is
not a guarantee that every document has these fields.

Export each source independently using the server's MongoDB 3.2 tools. For example,
after creating a protected local `/secure/migration` directory:

```bash
umask 077
ssh "$MIGRATION_SSH_HOST" \
  'mongoexport --host 127.0.0.1 --port 27017 --db coyote --collection variants' \
  > /secure/migration/v2-variants.jsonl
ssh "$MIGRATION_SSH_HOST" \
  'mongoexport --host 127.0.0.1 --port 27017 --db coyote --collection variants_idref' \
  > /secure/migration/v2-variants-idref.jsonl
ssh "$MIGRATION_SSH_HOST" \
  'mongoexport --host 127.0.0.1 --port 27017 --db coyote3 --collection variants' \
  > /secure/migration/v3-variants.jsonl
```

Export the current target `hgnc_genes` collection separately if selection is needed:

```bash
mongoexport --uri "$TARGET_MONGO_URI" --db "$TARGET_MONGO_DB" \
  --collection hgnc_genes --out /secure/migration/hgnc-genes.jsonl
```

Only records whose explicit `SAMPLE_ID` resolves to an ObjectId in the matching
sample bundle are converted. Malformed/missing owners and owners outside that
selection are counted separately and excluded. Sample names are never used as a
fallback. Selected findings with conflicting owner fields fail validation.

## Prepare each source

For v3, preserve the recorded selection and criterion:

```bash
.venv/bin/python migrations_scripts/v3/migrate_variants.py \
  --collection variants \
  --input /secure/migration/v3-variants.jsonl \
  --sample-bundle /secure/migration/v3-hema-samples \
  --output /secure/migration/v3-hema-variants
```

Both scripts use the confirmed source release 103, including when neither the sample
nor the finding records a release. Recorded `database_versions.vep` on a sample and
`vep_version` on a finding must agree with 103; a conflict fails validation rather
than overwriting the recorded value. No VEP version argument is needed.

For v2 findings without a selected consequence, explicitly enable the application's
configured transcript-selection order using the reviewed HGNC export:

```bash
.venv/bin/python migrations_scripts/v2/migrate_variants.py \
  --collection variants \
  --input /secure/migration/v2-variants.jsonl \
  --sample-bundle /secure/migration/v2-solid-samples \
  --select-missing-csq --hgnc-genes /secure/migration/hgnc-genes.jsonl \
  --prior-bundle /secure/migration/v3-hema-variants \
  --output /secure/migration/v2-solid-variants
```

`--select-missing-csq` applies only to absent selections. Existing selections are
retained even when the current selection rules would choose something else. The
generated selection criterion is recorded. Review newly selected transcripts before
import, especially for historical report comparisons. An empty CSQ array cannot
be used to create a missing selection.

Process `variants_idref` independently; it also uses VEP 103:

```bash
.venv/bin/python migrations_scripts/v2/migrate_variants.py \
  --collection variants_idref \
  --input /secure/migration/v2-variants-idref.jsonl \
  --sample-bundle /secure/migration/v2-solid-samples \
  --select-missing-csq --hgnc-genes /secure/migration/hgnc-genes.jsonl \
  --prior-bundle /secure/migration/v2-solid-variants \
  --output /secure/migration/v2-solid-idref
```

Carry the immediately preceding bundle forward for each further assay/source run.
Its vault already contains the earlier cumulative transcript union. Supply additional
`--prior-bundle` paths for independent branches. Duplicate sample/allele pairs or
finding/comment ObjectIds fail instead of choosing a source and breaking saved
report references. Reconcile overlapping source exports explicitly, retaining a
reviewed account of which original finding IDs report snapshots reference.

Missing metadata can be supplied through `--review` with the same digest-bound
format as [related-data conversion](related-data.md): `records`, keyed by original
ObjectId, containing `source_sha256`, `reason` and dotted `fields`. It can supply
missing `INFO.selected_CSQ`, `INFO.selected_CSQ_criteria` or `vep_version`, but cannot
replace recorded values or change owner/record identity. Protected `failure.json`
identifies validation failures; a failed directory has no completed manifest and
must never be imported.

## Output contracts

| File | Content and relationships |
| --- | --- |
| `variants.jsonl` | Current `VariantsDoc`; original `_id` and sample ownership, canonical `simple_id`/MD5 identity, original selected consequence and criterion. `INFO.CSQ` is removed. |
| `anno_vep.jsonl` | One shared record per canonical allele and VEP release; full source CSQ rows plus the selected row, including when it was absent from the original CSQ array. |
| `finding_comments.jsonl` | Embedded comments with original IDs when present, authors, timestamps, text and hiding metadata; `finding_oid` points to the retained variant `_id`, `sample_oid` to its sample, `finding_type` is `small_variant`. The file is absent if there are no comments. |
| `source_records.jsonl` | Unchanged selected source documents for private reconciliation; never import this archive into live collections. |
| `manifest.json` | Completion, source/version, sample bundle and reference/review/prior-bundle hashes, selection counts and output checksums. |

Vault IDs are deterministic for allele/release. Identical complete transcript rows
are deduplicated. Distinct rows with the same Feature are retained, preserving richer
source columns alongside a slim selected row rather than overwriting either.
Conflicting nonempty variant classes fail. Vault merging stages one allele/release
at a time in local JSON files; no SQLite or other database is used.

The variant retains recorded summary fields. Missing `genes`, versionless
`transcripts`, HGVSc/HGVSp, COSMIC/dbSNP/PubMed IDs and hotspots use the application's
transcript parser. `consequence_terms` includes terms from all retained transcripts,
including the selection, with ampersand strings normalized. Missing population
frequencies use maximum recorded numeric CSQ values, matching ALT in historical
`ALLELE:FREQ` strings. Unavailable values remain null, not zero. Historical values
remain in the raw archive and complete vault rows. No liftover or reannotation occurs.

Reports and reported finding snapshots use the separate
[related-data converter](related-data.md). It preserves `var_oid` links to original
variant ObjectIds. Clinical classification/text annotations belong to a subsequent
annotation migration after the VEP vault is available; they are not inferred from
variant comments. No separate finding-comment collection was observed in the source
collection inventory; this stage extracts the embedded `comments` arrays.

## Review and import into the destination

Check complete manifests, output checksums, selection counts, retained finding IDs,
newly selected transcripts and saved-report references before importing anything.
The scripts have performed no database writes. Local sample preparation may precede
the variant stage while the operator imports reference/VEP data before samples.

For a new destination, import the **last cumulative** `anno_vep.jsonl` once. Import
each run's `variants.jsonl` and optional `finding_comments.jsonl` once. Earlier vault
files overlap the final one and must not all be inserted. Example operator commands:

```bash
mongoimport --uri "$TARGET_MONGO_URI" --db "$TARGET_MONGO_DB" \
  --collection anno_vep --mode insert --stopOnError \
  --file /secure/migration/v2-solid-idref/anno_vep.jsonl
mongoimport --uri "$TARGET_MONGO_URI" --db "$TARGET_MONGO_DB" \
  --collection variants --mode insert --stopOnError \
  --file /secure/migration/v3-hema-variants/variants.jsonl
mongoimport --uri "$TARGET_MONGO_URI" --db "$TARGET_MONGO_DB" \
  --collection finding_comments --mode insert --stopOnError \
  --file /secure/migration/v3-hema-variants/finding_comments.jsonl
```

Repeat the latter two commands for each additional reviewed bundle, skipping absent
comment files. These are manual destination writes, not converter operations.
Do not use drop/upsert to hide conflicts with an existing vault or finding collection.
For a populated destination, reconcile existing allele/release records and IDs before
planning a separate reviewed import. `mongoimport --stopOnError` is not transactional;
after any partial import, reconcile inserted IDs before rerunning it.
