# Export one assay in batches

`export_assay.py` exports original source documents for one assay and its selected
samples. It uses **read-only** `mongo` and `mongoexport` commands on the MongoDB 3.2
source server, through SSH. It never imports documents, changes schemas or writes
to MongoDB. The resulting Extended JSON files are inputs to the separate migration
converters.

## Start an export

Run from the repository root using the local Python environment. SSH access must
already work without an interactive prompt. The server supplies `mongo` and
`mongoexport`; the local Linux host supplies `ssh` and GNU `sort`. Modern PyMongo
and `mongosh` are not used to connect to this source.

Choose a protected local directory outside the repository. It must not exist when
starting a new export. For v3 hematology:

```bash
umask 077
.venv/bin/python migrations_scripts/export_assay.py \
  --source-version 3 --assay-id hema_gmsv1 \
  --ssh-host "$MIGRATION_SSH_HOST" \
  --output /secure/migration/exports/v3-hema_gmsv1
```

For v2 solid-tumour samples:

```bash
.venv/bin/python migrations_scripts/export_assay.py \
  --source-version 2 --assay-id solid_gmsv3 \
  --ssh-host "$MIGRATION_SSH_HOST" \
  --output /secure/migration/exports/v2-solid_gmsv3
```

The database is `coyote` for version 2 and `coyote3` for version 3. Assay matching
uses the same rules as the [sample converters](README.md#scope-and-mapping):

| Source | Sample selection |
| --- | --- |
| v2 | Case-insensitive `groups`, including string or array values. Older biological `assay` values map to the approved physical assay IDs when `groups` is absent, empty or agrees with the old representation. |
| v3 | Case-insensitive physical `assay`; `groups` is used when `assay` is absent. |
| v2 `tumwgs-hema` | `groups: tumwgs` and recorded `subpanel: hema`. |
| v2 `tumwgs-solid` | `groups: tumwgs` and recorded `subpanel: solid`. |
| v2 `tumwgs` | `groups: tumwgs` with missing, null, blank, `None` or `legacy` subpanel. |

Use lowercase assay IDs on the command line; source document casing is preserved.
No diagnosis, assay or other source values are renamed during export.

## Batch contents

The default is **500 samples per batch**. A 1,200-sample assay produces batches of
500, 500 and 200 automatically. The limit counts samples, not variant documents;
every linked record for the selected samples is exported, however many there are.
`--batch-size` can lower this value, from 1 through 500.

At startup the script discovers physical collections containing `SAMPLE_ID` or
`sample_oid`, then saves a sorted list of matching sample ObjectIds. Every related
collection is queried for those ObjectIds as BSON values and as textual values.
The collection inventory includes newly encountered collections with these owner
fields, rather than relying only on a fixed list of known names.

This includes sample-owned variants, `variants_idref`, CNVs, translocations,
biomarkers, coverage, fusions and any separate comments, reports, RNA, QC or reported
finding collections using these fields. Embedded comments, reports, expression and
QC remain intact inside each exported sample. Empty collection files are kept, so
the checkpoint records that the collection was checked for the batch.

Records must have one unambiguous scalar sample ObjectId. Missing owner fields do
not create a relationship through a sample name or a file path. A selected record
with conflicting or malformed owners stops the batch. Shared annotations, assay
configuration, reference collections and group-level coverage exclusions without
sample ownership are outside this sample export; use their separate migration
procedures. A collection using a different relationship field needs an explicit
reviewed mapping before it can be included.

Example output:

```text
v3-hema_gmsv1/
  request.json
  inventory.json
  sample_ids.jsonl
  selection.json
  manifest.json
  batch-000001/
    samples.jsonl
    variants.jsonl
    cnvs.jsonl
    ...other discovered sample-owned collections...
    progress.json
  batch-000002/
    samples.jsonl
    variants.jsonl
    ...
    progress.json
```

Files retain original BSON IDs, dates, authors, selected consequences, full CSQ
arrays and all other source content. Conversion and extraction happen afterward.
The exporter writes canonical Extended JSON; output ordering is for deduplication
and does not imply clinical ordering. Private `.stderr` files contain source-tool
diagnostics. Do not publish any of these files or commit them to the repository.

## Resume without exporting completed data again

Repeat the same command with `--resume`:

```bash
.venv/bin/python migrations_scripts/export_assay.py \
  --source-version 3 --assay-id hema_gmsv1 \
  --ssh-host "$MIGRATION_SSH_HOST" \
  --output /secure/migration/exports/v3-hema_gmsv1 \
  --resume
```

The source, assay, batch size and output directory must match the original run.
Resuming verifies the saved selection, collection inventory and file checksums.
It skips all checkpointed collection exports, even within an interrupted batch.
If the whole export has already completed, no source commands run again.

Each source collection has its own document-identity ledger. Identical duplicate
records are omitted; conflicting content for an already exported identity fails
instead of silently replacing history. The ledger is reconstructed from verified
local files and uses temporary files plus a 32 MiB external sort buffer, not SQLite
or another local database. Clinical documents are streamed individually. Completed
files have record counts and SHA-256 checksums in `progress.json`; the root manifest
is marked complete only after every batch is complete. One process can use an
output directory at a time.

An interrupted source command may leave a `.raw.jsonl` or `.pending.jsonl` file.
That unfinished collection is retried; checkpointed collections are not fetched
again. Do not edit output files or checkpoints to bypass a failure. A checksum
failure requires restoring the original file or starting a new reviewed export.

The saved ID selection is fixed. Samples added later do not get appended on resume,
and already exported documents are not refreshed. Use a stable source backup or
keep the selected source records unchanged throughout export. MongoDB 3.2 exports
across collections do not provide a single transactional snapshot: a related record
added after its collection was exported would not be included. Creating a new output
directory intentionally starts a new independent export and can repeat earlier data.

Collection discovery checks owner-field presence and can scan collections without
supporting indexes. It fails on a timeout rather than silently leaving a collection
out. Increase `--discovery-timeout-ms` from its default 30000 only when appropriate
for the source. No index is created or changed by the exporter.

## Use the files for migration

For each numbered batch, use `samples.jsonl` as the sample converter's `--input`.
Prepare and review that batch's sample bundle first. Then supply the corresponding
collection files to the [related-data converter](related-data.md) and
[variant converter](variants.md), using that exact batch's prepared sample bundle.
Carry prior variant bundles forward as documented to merge the shared VEP 103 vault
and detect overlap across preparation runs. A root export manifest is not a prepared
sample bundle and must not be passed as `--sample-bundle`.

No export or migration is run merely by adding this script. The commands above
perform source reads and local file writes only.
