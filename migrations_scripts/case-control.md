# Case and control sequencing metadata

Both version-specific sample `prepare` commands require `--case-control-config`.
For every sample, preparation reads Bjorn and CDM separately for the case and,
when present, the control. It matches the original specimen ID exactly and assay
identifiers case-insensitively using explicit mappings. It never writes to either
reference database. Original sample ObjectIds, authors, history and BAM paths are
preserved.

## Configure the reference sources

The inspected Bjorn source is `bjorn.samples`: specimen identity is `id`, assay
is `assay`, and sequencing records are in `replicates[]`. Run names are in
`replicates[].paths.sequencing_run` and dates in `sequencing_date`.

The cross-check database is **`CMD`**, with that exact capitalization. Read-only
inspection verified `CMD.files`: specimen identity is `sample-id`, assay is
`assay`, and the sequencing run is `run`. The configuration section remains
`cdm`; its `database` setting selects the actual MongoDB database `CMD`.
Use the source server's SSH destination below and supply reviewed reference
assay mappings. Do not infer reference assay names from the destination assay ID.

Store this JSON in a private location, for example
`/secure/migration/case-control.json`:

```json
{
  "bjorn": {
    "ssh_host": "operator@source-host",
    "database": "bjorn",
    "collection": "samples",
    "sample_id_field": "id",
    "assay_field": "assay"
  },
  "cdm": {
    "ssh_host": "operator@source-host",
    "database": "CMD",
    "collection": "files",
    "sample_id_field": "sample-id",
    "assay_field": "assay",
    "run_field": "run"
  },
  "assays": {
    "hema_gmsv1": {
      "bjorn": ["REPLACE_WITH_VERIFIED_BJORN_ASSAY"],
      "cdm": ["REPLACE_WITH_VERIFIED_CDM_ASSAY"]
    }
  }
}
```

Add one entry under `assays` for each destination assay being prepared. Multiple
reference assay identifiers can be listed when their equivalence is confirmed.
Field paths support nested objects and arrays. Reference specimen IDs and run
names retain their original case.

Each SSH reader invokes `mongoexport` on the specified host, defaulting to MongoDB
at `127.0.0.1:27017`. Optional `host`, `port` and `mongoexport` settings select
the database endpoint and installed export binary. Use a read-only database
account/environment on that host. For offline preparation, replace `ssh_host`
with `input`, the absolute path to a newline-delimited Extended JSON export;
retain the database, collection and field mappings. Exactly one of `input` and
`ssh_host` is required per reference. Offline exports are scanned per specimen.

## Run selection and metadata

- Bjorn statuses `normal`, `topup`, or absent are eligible. `failed` excludes
  that run, even if another record for the same run is eligible. Unknown status
  values require review.
- If CDM confirms at least two distinct eligible Bjorn run names, store those
  confirmed names in `case.sequencing_run` or `control.sequencing_run` as a list,
  ordered by sequencing date.
- Otherwise, store the latest eligible Bjorn run as a single string. A successful
  CDM lookup with no matching records follows this rule. A failed connection or
  export stops preparation; it is not interpreted as an empty result.
- Use the latest selected replicate's Clarity sample/pool IDs, FFPE status and
  purity when recorded. Sum `n_reads` across selected distinct runs only when
  every selected run has a count; otherwise set `reads` to null.
- Missing eligible runs, missing run names/dates, conflicting duplicate runs or
  tied latest dates stop preparation for review. No run is chosen arbitrarily.

The sample contract accepts a string, a list of strings, or null for
`sequencing_run`. Preparation retains the original source sample and writes
`case_control_sources.jsonl` with matching reference records and the selection
decision for each role, keyed by the original sample ObjectId. This private
evidence file is **not a destination collection and must not be imported**.
The completion manifest includes output checksums and the configuration checksum.
Protect these exports as clinical data. A failed preparation has no completion
manifest and must not be imported.

Return to the [sample migration commands](README.md#3-prepare-one-assay).
