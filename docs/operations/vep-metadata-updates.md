# VEP metadata updates

`vep_metadata` lives in `KNOWLEDGEBASE_DB`, reached through
`KNOWLEDGEBASE_MONGO_URI`. Each document describes one major Ensembl release.
It supplies variant-class labels, consequence descriptions, impact ratings and
the logical consequence groups used by the application. It also records published
human cache versions. These reference versions do not replace the pipeline's
`samples.database_versions` provenance.

Users can inspect the installed definitions and diagrams in the
[VEP reference library](../reference/knowledgebases/vep-reference.md).

## Sources and release scope

`scripts/knowledgebase/update_vep_metadata.py` reads the official Ensembl GitHub sources for:

| Data | Official source |
| --- | --- |
| Consequence terms, descriptions, SO accessions and impacts | `ConsequenceTable.pm`, which renders the [calculated consequences page](https://jun2026.archive.ensembl.org/info/genome/variation/prediction/predicted_data.html) |
| Variant classes, definitions and SO accessions | Release-specific [classification HTML](https://jun2026.archive.ensembl.org/info/genome/variation/prediction/classification.html) |
| GRCh37 and GRCh38 cache versions | Release-specific [VEP cache documentation](https://jun2026.archive.ensembl.org/info/docs/tools/vep/script/vep_cache.html) |

Every release branch is resolved to a Git commit before downloading. The script
retains the original source files and a SHA-256 manifest. Source code is parsed
as literal data, never executed. The consequence renderer is in `public-plugins`
for releases 98 and 99 and `ensembl-webcode` from release 100 onward.
The metadata's three reference URL fields point to human-readable Ensembl archive
pages, not raw source files. `scripts/knowledgebase/ensembl_archives.json` records the reviewed
release-to-archive dates from the [Ensembl archive listing](https://jun2026.archive.ensembl.org/info/website/archives/index.html)
and historical release announcements. Review this mapping when adding a release;
unknown dates stop the import. Retired external archives may no longer serve their
original pages. The local reference and pinned source manifest remain available.

The bundled seed covers major releases 98 through 116. Release 103 is protected:
the importer neither downloads nor replaces it. The software version 116.2 belongs
to major release 116; this importer does not create a separate metadata document
for every VEP software patch.

The website tables contain 36 consequences through release 109 and 41 from
release 110. They are documentation snapshots, not an exhaustive extraction of
the executable VEP engine. In particular, internal variation constants may contain
terms absent from a historical website table and may assign different impacts.
The importer deliberately uses the website table requested for this reference,
not the internal constants. It does not reannotate variants or change their raw
VEP consequences.

## Storage and grouping

The existing document fields are retained: `vep_id`, creation provenance, source
URLs, `db_info`, `variant_class_translations`, `conseq_translations` and
`consequence_groups`. MongoDB `_id` values survive replacement of existing releases.
The optional `consequence_diagram` field stores only MIME type, dimensions,
owning release, source URL and SHA-256 digest. The digest references `_id` in
`vep_diagrams`, configured through `vep_diagrams_collection` in the knowledgebase
collection mapping. Each asset contains `data` as BSON binary subtype 0 and
`mime_type`. Identical images are stored once across releases. No base64 image
string is stored in `vep_metadata` or the image collection. JPEG, PNG and validated
SVG images are supported. SVG scripts, event handlers, entity declarations and
external content references are rejected. The browser renders SVG as an image,
not inline executable markup.

| Field | Meaning |
| --- | --- |
| `conseq_translations.<term>.so_term` | Sequence Ontology accession, not the consequence name |
| `conseq_translations.<term>.impact` | Ensembl website impact rating for this release |
| `conseq_translations.<term>.group` | Coyote3 logical filter group |
| `consequence_groups` | The same membership expressed as group-to-term lists |
| `db_info.<build>.published_sources` | Complete cache-table source labels and values, including MANE and separate gnomAD sources |
| `db_info.<build>.gnomad` | Published gnomAD sources combined with explicit exome/genome labels |
| `db_info.<build>.assembly_accession` | RefSeq accession explicitly present for the matching assembly in the cache table; empty when unavailable |

Empty cache fields mean the source did not publish that value. They do not mean
the pipeline omitted that database. The importer does not infer missing versions
from another release. The Ensembl database version template marker is resolved
from the pinned release in both `published_sources` and `ensembl_version`.

`scripts/knowledgebase/vep_metadata_policy.json` owns application labels and logical groups.
Every imported consequence must occur in exactly one reviewed group. Unknown
terms and duplicate assignments stop the import before database writes.
Groups absent from a release are omitted, not filled with newer terms.

| Group | Included findings |
| --- | --- |
| `splicing` | Acceptor, donor, splice-region and supported extended splice-site terms |
| `stop_gained`, `frameshift`, `stop_lost`, `start_lost` | Their corresponding consequence terms |
| `inframe_indel` | Inframe insertions and deletions |
| `missense` | Missense and protein-altering variants |
| `other_coding` | Coding-sequence and supported coding-transcript variants |
| `synonymous` | Synonymous, retained start/stop and incomplete terminal codon variants |
| `transcript_structure` | Transcript ablation and amplification |
| `UTR`, `miRNA`, `NMD` | UTR, mature miRNA and NMD-transcript terms |
| `non_coding`, `intronic`, `intergenic` | Noncoding transcripts, introns, upstream/downstream and intergenic terms |
| `regulatory` | Regulatory-region and transcription-factor binding-site terms |
| `feature_elon_trunc` | Feature elongation and truncation |
| `other` | Generic `sequence_variant`, when present in the release table |

These groups are application filtering categories, not new clinical severity
classifications. Existing sample-specific queries continue to request that sample's
VEP release. Unversioned configuration options select the numerically latest release.

## Download and inspect

Run from the repository root with the project's Python environment:

```bash
.venv/bin/python scripts/knowledgebase/update_vep_metadata.py \
  --from-release 98 --to-release 116 --cpus 4 \
  --actor "$USER" --output-dir /tmp/vep-reference-review
```

The default command makes no database or seed writes. It downloads and validates
all requested releases except 103, then writes `documents.json`, `manifest.json`
and per-release original sources beneath the output directory. `--cpus` controls
concurrent release downloads. A failed download or validation aborts the whole
batch; no incomplete release is installed.

Review changes to terms, ontology accessions, impacts, groups and cache versions
before applying. Historical website corrections can change displayed reference
information for existing samples. Reports already stored are not rewritten.

## Install and update the seed

Pause competing reference importers. Use a maintenance connection with write
permission on the knowledgebase database; normal application access can remain
read-only. A replica set, including a single-member replica set, is required.

```bash
.venv/bin/python scripts/knowledgebase/update_vep_metadata.py \
  --from-release 98 --to-release 116 --cpus 4 \
  --actor "$USER" --output-dir /tmp/vep-reference-install \
  --env-file .knowledgebase-maintenance.env \
  --apply --backup /secure/backups/vep-before-update.bson
```

The private environment file must define `KNOWLEDGEBASE_MONGO_URI` and
`KNOWLEDGEBASE_DB`. Shell environment variables override file values. Never commit
the file. Create the backup parent directory beforehand; the backup file must not
already exist. Its permissions are set to owner read/write only.

The importer backs up all existing documents in the requested range except 103,
then replaces or inserts that range in one MongoDB transaction. It refuses to
continue if those records changed after backup. Other releases, collections,
samples, findings, annotations and reports are untouched. Keep the backup and
source manifest with the maintenance record. Existing release IDs must be unique.

After review, add `--update-seed` to write the compressed application seed and
its source manifest. This flag can be used without `--apply` for a seed-only
update. Release 103 and other unrequested seed records remain unchanged.
First-run bootstrap still imports references only into an empty collection;
deploying a new image does not silently replace an existing collection.

For a future release, set `--from-release` and `--to-release` to that major version.
New terms require an explicit policy review before import. Restart API and worker
processes after deployment so they run the numeric-release selection code.

## Diagram-only updates, including release 103

New metadata imports also download the diagram linked by each release's
`predicted_data.html`. To add or refresh diagrams without replacing definitions:

```bash
.venv/bin/python scripts/knowledgebase/update_vep_diagrams.py \
  --output /tmp/vep-diagrams.json --cpus 4
```

The diagram command downloads images for releases present in the bundled seed,
including 103. Add `--update-seed` to enrich the seed, and use the following flags
for a database update:

```bash
.venv/bin/python scripts/knowledgebase/update_vep_diagrams.py \
  --output /tmp/vep-diagrams.json --cpus 4 \
  --env-file .knowledgebase-maintenance.env \
  --apply --backup /secure/backups/vep-before-diagrams.bson
```

All requested releases must already exist in the database. The command backs up
their complete documents, inserts content-addressed binary assets and sets only
`consequence_diagram` in one transaction on the same knowledgebase connection.
It does not alter consequence definitions, groups, creation provenance or IDs.
Release 103 remains protected from the metadata importer; its diagram can be
updated independently. Image provenance is retained inside each diagram document.

The seed stores original binary files under
`api/config/bootstrap/reference/vep_diagrams/<sha256>`. Bootstrap validates hashes
and installs these into the configured image collection before metadata. Keep
this directory with the reference seed when copying a seed pack to another center.
The downloader's review output may contain base64 as JSON transport data; import
separates this into BSON binary before writing either collection.

### Existing inline images

Pause other reference importers, then migrate an existing installation:

```bash
.venv/bin/python scripts/knowledgebase/migrate_vep_diagram_storage.py \
  --env-file .knowledgebase-maintenance.env \
  --apply --backup /secure/backups/vep-before-binary-images.bson
```

The migration validates each original image, preserves its bytes and hash, and
atomically removes embedded base64 while inserting its binary asset. Release 103
is included. A second run finds nothing to migrate. Use `--update-seed` to convert
an older seed pack. Deploy the binary image API and refreshed frontend together
with this migration; older clients expect inline images. Normal application
credentials need read access to both knowledgebase collections, not write access.

## Correcting reference links and version labels

For references installed with raw download URLs or an unresolved Ensembl version
label, use the targeted repair with a maintenance connection:

```bash
.venv/bin/python scripts/knowledgebase/repair_vep_reference_links.py \
  --env-file .knowledgebase-maintenance.env \
  --apply --backup /secure/backups/vep-before-reference-repair.bson
```

This backs up all installed records and corrects only the three documentation
URL fields and unresolved cache version labels in a transaction. Definitions,
groups, IDs, creation provenance and diagrams are unchanged, including release
103. `--update-seed` applies the same corrections to the bundled seed without
requiring a database connection. Repeating the repair makes no further changes.
