# Reporting and History

This chapter explains how reports are generated, stored, and traced historically.

## Report lifecycle

For DNA reports:

1. Analyst reviews sample and tiers variants.
2. Analyst previews report.
3. Analyst saves report.
4. Coyote3 writes HTML file.
5. Coyote3 appends report metadata to sample.
6. Coyote3 stores immutable `reported_variants` snapshot rows.
7. Sample appears in reported/done list.

## Routes involved

- Preview DNA report: `/dna/sample/<sample_id>/preview_report`
- Save DNA report: `/dna/sample/<sample_id>/report/save`
- View saved report: `/samples/<sample_id>/reports/<report_id>`
- Download saved report: `/samples/<sample_id>/reports/<report_id>/download`

RNA routes:

- Preview RNA report: `/rna/sample/preview_report/<sample_id>`
- Generate RNA PDF: `/rna/sample/report/pdf/<sample_id>`

## What gets stored in sample document

On report save, Coyote3 updates sample fields:

- increments `report_num`
- appends entry in `reports[]` including:
  - report `_id`
  - `report_id`
  - `report_name`
  - `filepath`
  - `author`
  - `time_created`

This metadata controls visibility on `/samples/done` and report links.

## What gets stored in `reported_variants`

Coyote3 stores one snapshot row per reported variant with report linkage.

Typical fields include:

- `sample_oid`, `report_oid`, `report_id`, `sample_name`
- `var_oid`, `simple_id`, `simple_id_hash`
- `tier`
- `gene`, `transcript`, `hgvsp`, `hgvsc`
- `annotation_oid`, `annotation_text_oid`, `sample_comment_oid`
- `created_on`, `created_by`

These rows preserve report-time truth even if global annotations change later.

## Why preview and save can differ operationally

Preview uses the same payload logic as save, but does not persist state.

Save can fail if:

- report path is not writable
- file already exists with same report name
- DB write for report metadata fails

So preview success does not guarantee save success.

## Historical lookup paths

Two key history views:

- `/search/tiered_variants`
- `/reported_variants/variant/<variant_id>/<tier>`

Use these to trace:

- where a variant has been reported
- with which tier
- in which samples/reports

## Audit-safe usage guidance

1. Treat report save as the interpretation checkpoint.
2. Use report-linked views for historical truth, not mutable live sample state.
3. Avoid relying only on current `annotation` class if historical report-level evidence is required.
