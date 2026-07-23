# Reporting Workflow And Variant Snapshots

This document describes the Coyote3 sample-to-report workflow, the rules used
when building a report, what is persisted in MongoDB, and how persisted report
snapshots support later search, mapping, dashboards, and cross-sample review.

For the field-level preparation protocol, annotation matching order, filter
authority, and the report-text boundary, see
[Clinical data preparation and reporting flow](../architecture/clinical_data_and_reporting_flow.md).

The core rule is:

> A report preview is temporary and filter-derived. A saved report is immutable
> clinical evidence: HTML/PDF artifacts plus database metadata and per-variant
> snapshot rows.

## High-Level Flow

1. A sample is ingested into `samples` with assay, subpanel, environment,
   files, current filters, and current ASPC references.
2. The user reviews sample data in the UI: SNVs, CNVs, fusions,
   translocations, coverage, and comments.
3. The user changes filters when needed. The sample filter blob is updated.
4. The Reports tab asks the backend for a report preview.
5. The backend resolves the sample, ASP, and active ASPC; applies the current
   filters and gene scope; enriches and selects reportable findings; and builds
   a temporary prepared report context.
6. The report composer generates text and sections from that prepared context
   and renders clinical report HTML.
7. The UI shows the report preview and snapshot rows. Nothing is persisted yet.
8. The user confirms Save.
9. The backend reruns the same report workflow in save mode, renders HTML,
   renders PDF from the same HTML, saves report metadata, marks the sample as
   reported, and persists per-variant snapshot rows in `reported_variants`.
10. Future searches, variant detail pages, dashboards, and audit workflows read
   the immutable report metadata and reported-variant snapshots.

## Ingested Sample State

The sample document is the operational anchor for the report workflow. The
reporting layer expects the sample to contain enough metadata to resolve:

- the assay: `sample.assay`
- the environment/profile: `sample.profile`
- the subpanel if applicable: `sample.subpanel_id`
- the current ASPC reference: `current_aspc_id`,
  `current_aspc_key`, `current_aspc_version`
- current filter settings: `sample.filters`
- case/control identifiers and Clarity metadata
- file paths under `sample.files`
- report status flags: `reported`, `latest_report_id`, `latest_report_on`

The sample is not the long-term store for report rows. After a report is saved,
clinical report metadata is stored in `reports`, and per-variant report evidence
is stored in `reported_variants`.

## ASPC And Filter Resolution

The ASPC is the digital rulebook for report generation. It controls:

- which analysis sections are valid for the assay/subpanel/environment
- which sections are included in the report
- default filters for SNV, CNV, coverage, and related domains
- report wording such as method, header, description, and output folder

When a sample is loaded, the current filters should come from the matching ASPC:

1. Match by `asp_id`, `subpanel_id`, and environment/profile.
2. If no specific subpanel configuration exists, use the `base` subpanel for
   that assay and environment.
3. Store the effective ASPC reference on the sample so filter reset can restore
   the same default rulebook.
4. Store the filter blob on the sample by domain, for example `filters.snv`,
   `filters.cnv`, and `filters.cov`.

When the user applies filters, the active filter blob changes. Report preview
and save must use that active sample filter state.

## Prepared Report Context

The reporting application completes clinical data selection before report text
is generated. It provides a versioned, read-only context containing:

- sample, ASP, and resolved ASPC identity/version;
- analyses and report sections enabled by ASPC;
- selected ISGL identifiers, versions, ad-hoc genes, and effective gene scope;
- already filtered and annotation-enriched small variants;
- already selected CNVs, fusions, and translocations;
- structured biomarkers and coverage data;
- CNV profile availability;
- filter snapshot, source counts, data versions, and preparation time.

The report composer receives this prepared set. It does not load raw findings
or independently decide which findings are reportable.

!!! info
    The prepared context is a handoff contract. Upstream services own data
    retrieval, transcript selection, HGNC normalization, analytical filters,
    gene-list scope, annotation matching, blacklist/false-positive/irrelevant
    exclusion, and tier reportability.

!!! warning
    A future configurable text rules engine may select and render clinical
    wording from this context. It must not query MongoDB, apply filters, assign
    tiers, choose transcripts, call external knowledgebases, or mutate clinical
    data.

## Report Preview

Endpoint:

```text
GET /api/v1/samples/{sample_id}/reports/{report_type}/preview
```

Rules:

- Permission required: `report:preview`.
- Preview is temporary.
- Preview does not write report metadata.
- Preview does not write `reported_variants`.
- Preview uses the current sample filters.
- Preview resolves the current ASPC at request time.
- Preview renders the same clinical report HTML used for PDF/save.
- Preview can include `snapshot_rows` for UI inspection when requested.

The response contains:

- sample metadata
- preview metadata
- report template name
- report context
- rendered HTML
- optional snapshot rows

Preview PDF endpoint:

```text
GET /api/v1/samples/{sample_id}/reports/{report_type}/preview/pdf
```

Rules:

- Permission required: `report:preview`.
- Generates PDF from the temporary preview HTML.
- Does not save report metadata.
- Does not save reported-variant snapshots.
- Intended for review only.

## Report Save

Endpoint:

```text
POST /api/v1/samples/{sample_id}/reports/{report_type}
```

Rules:

- Permission required: `report:create`.
- Save is an explicit user-confirmed action.
- Save reruns the backend report workflow in save mode.
- The client does not provide trusted HTML.
- The backend renders the report HTML.
- The PDF is generated from the exact same HTML.
- The report number is assigned from the `reports` collection, not from stale
  sample state.
- The save fails if the target HTML or PDF filename already exists.
- `reported_variants` rows are written only after the report artifact and report
  metadata are successfully created.

Saved outputs:

- HTML report file on disk
- PDF report file on disk
- one `reports` document
- many `reported_variants` documents, one per reportable variant snapshot
- sample flags updated to show that the sample has a saved report

## Report Artifact Rules

The report artifact must be self-contained HTML:

- report CSS is embedded in the HTML
- the layout follows the validated clinical report format
- PDF generation uses the same HTML
- preview, saved HTML, and saved PDF should therefore have matching structure

The report renderer is an implementation detail. The product contract is the
generated artifact:

```text
workflow context -> clinical report HTML with embedded CSS -> PDF from same HTML
```

## DNA Report Build Logic

The DNA report workflow builds the report context from the sample, ASPC, and
current filters.

### Section Selection

DNA report sections come from ASPC reporting settings. Supported normalized
sections include:

- `SNV`
- `CNV`
- `CNV_PROFILE`
- `COVERAGE`
- `TRANSLOCATION`
- `FUSION`
- `BIOMARKER`

The report can show only sections enabled for that assay configuration.

### SNV Query Logic

SNV report rows are built from current sample filters:

- `min_depth`
- `min_alt_reads`
- `min_freq`
- `max_freq`
- `max_control_freq`
- `max_popfreq`
- selected VEP consequence groups
- selected SNV gene lists
- display positions for configured verification samples
- false positive exclusion
- irrelevant exclusion

Consequence filtering uses the VEP metadata group map for the sample VEP
version. UI-facing groups such as `missense`, `frameshift`, or `splicing` are
expanded to concrete VEP consequence terms before querying variants.

Current query reproducibility rule:

- consequence matching must preserve the clinical query behavior
- selected transcript consequence and other transcript consequences can both
  affect inclusion where the clinical query did so
- hematology/solid germline rescue behavior is preserved where applicable

After querying:

1. blacklist metadata is attached
2. global annotations are attached
3. hotspot metadata is hydrated
4. report-only filtering keeps variants that:
   - are in selected report genes, unless no report gene filter is active
   - are not blacklisted
   - have a classification
   - are not Tier IV or `999`
5. rows are simplified for the report template
6. rows are sorted by class and allele frequency

### CNV Logic

CNV report rows are included only when `CNV` is in report sections.

Rules:

- load interesting CNVs for the sample
- apply selected CNV effect filters, such as gain/loss
- apply selected CNV gene lists
- organize genes for display
- render the clinical report CNV summary table

### CNV Profile Logic

CNV profile is separate from CNV calls and coverage. It is an image artifact stored on the sample as `files.cnvprofile`. The review UI displays it beside the CNV table so copy-number calls and the profile can be assessed together. It is included in report output only when `CNV_PROFILE` is selected in report sections.

Rules:

- resolve the sample CNV profile image path
- base64 encode the plot if available
- embed it in report HTML
- PDF generation reads it from the same HTML

### Translocation Logic

Translocations are included only when `TRANSLOCATION` is in report sections.

Rules:

- load interesting sample translocations
- render the DNA fusion/translocation summary section

### Biomarker Logic

Biomarker data is loaded when `BIOMARKER` is in report sections.

The clinical DNA report template historically disabled biomarker rendering in the
visible report body. The backend context can carry biomarker data, but visible
report rendering should be controlled deliberately by the report template and
ASPC reporting requirements.

### Conclusion Logic

The report conclusion comes from sample comments.

Rules:

- hidden comments are ignored
- the latest visible sample-level comment is used
- Markdown is rendered and sanitized for report HTML
- if no visible comment exists, the report displays `Slutsats saknas!`

## RNA Report Build Logic

The RNA workflow builds a report context from the sample and fusion data.

Rules:

- load sample fusions
- attach fusion annotations
- filter blacklisted, Tier IV, and `999` classifications from visible report
  sections
- render clinical report RNA fusion summary and detailed fusion tables
- build optional snapshot rows for report persistence

RNA report sections use the RNA report context shape, not the DNA
`report_sections_data` shape.

## Snapshot Rows

Snapshot rows are transient until save. They are built during preview for UI
review and during save for persistence.

For DNA SNVs, each snapshot row contains the reportable identity and
classification state at report creation time:

- `var_oid`: source variant object id
- `annotation_oid`: classification/tiering annotation object id
- `annotation_text_oid`: selected annotation text object id, if applicable
- `sample_comment_oid`: latest sample comment id used for report context
- `var_type`
- `simple_id`
- `simple_id_hash`
- `tier`
- `gene`
- `transcript`
- `hgvsp`
- `hgvsc`
- `variant`
- `created_on`

The snapshot is intentionally smaller than the full variant document. Full
variant payload remains in the source variant collection. The snapshot stores
the immutable evidence needed to answer report-history questions.

## Collections Written On Save

### `reports`

One document is written per saved report.

Purpose:

- report-level metadata
- artifact paths
- filter snapshot
- ASPC snapshot/reference
- immutable clinical-rule release reference: release ID, rule-set ID, version,
  and content hash
- author and creation time
- sample linkage

Important fields:

```json
{
  "_id": "ObjectId",
  "sample_oid": "ObjectId",
  "sample_name": "seed_case",
  "assay": "hema_GMSv1",
  "subpanel_id": "Hem-Snabb",
  "environment": "production",
  "report_num": 1,
  "report_id": "report_id_placeholder",
  "report_type": "html",
  "report_name": "report_id_placeholder.html",
  "filepath": "/reports/.../report_id_placeholder.html",
  "pdf_report_name": "report_id_placeholder.pdf",
  "pdf_filepath": "/reports/.../report_id_placeholder.pdf",
  "author": "username",
  "time_created": "datetime",
  "filters_snapshot": {},
  "aspc": {
    "_id": "ObjectId",
    "aspc_id": "hema_GMSv1_base_production",
    "version": 1
  }
}
```

Indexes:

- `report_id`
- `sample_oid`, `report_num`
- `sample_name`, `time_created`

### `reported_variants`

Many documents can be written per saved report.

Purpose:

- immutable per-report variant evidence
- cross-sample lookup
- report-history lookup
- tier distribution analytics
- variant detail "previously reported" context

Important fields:

```json
{
  "sample_name": "seed_case",
  "sample_oid": "ObjectId",
  "report_oid": "ObjectId",
  "report_id": "report_id_placeholder",
  "report_num": 1,
  "created_by": "username",
  "var_oid": "ObjectId",
  "annotation_oid": "ObjectId",
  "annotation_text_oid": "ObjectId",
  "sample_comment_oid": "ObjectId",
  "var_type": "SNV",
  "simple_id": "13:28608258:G:T",
  "simple_id_hash": "sha-like-hash",
  "tier": 1,
  "gene": "FLT3",
  "transcript": "NM_004119",
  "hgvsp": "p.Asp835Tyr",
  "hgvsc": "c.2503G>T",
  "variant": "p.Asp835Tyr",
  "created_on": "datetime"
}
```

Indexes:

- unique `sample_oid`, `report_oid`, `simple_id`
- `sample_oid`, `report_oid`
- `gene`, `simple_id_hash`, `simple_id`
- `simple_id_hash`, `simple_id`, `tier`
- `gene`, `hgvsp`, `tier`
- `gene`, `hgvsc`, `tier`
- `tier`
- `assay`, `tier`
- creation time indexes

### `samples`

The sample document is updated after report metadata is saved.

Fields updated:

```json
{
  "reported": true,
  "latest_report_id": "ObjectId",
  "latest_report_on": "datetime"
}
```

The sample is not used as the canonical report-history store. It only carries
the latest report pointer and status flags for list views and dashboards.

## Why Store `reported_variants`

The `reported_variants` collection gives the application a clinical report
history index without repeatedly scanning raw variants or parsing report files.

It answers questions such as:

- Has this variant been reported before?
- In which samples was it reported?
- At what tier was it reported?
- Which report included it?
- Which annotation text was used at report time?
- Which sample comment was active when the report was created?
- How often has this gene/protein/cDNA event appeared in reports?
- What is the tier distribution across reported clinical outputs?

This is important because variant interpretations change over time. The source
variant, global annotation, or tier may change later, but the report snapshot
must preserve what was actually signed out at the time.

## Cross-Sample Search And Mapping

### Variant Detail Context

When a user opens a tiered variant, the backend can build a reported-history
context:

1. Load the current variant.
2. Extract selected consequence identity:
   - gene
   - `simple_id`
   - `simple_id_hash`
   - `HGVSc`
   - `HGVSp`
3. Query `reported_variants` by the strongest identity available:
   - preferred: `gene` plus `simple_id_hash` and `simple_id`
   - fallback: `HGVSc`
   - fallback: `HGVSp`
4. Enrich results with sample metadata and annotation text.

This gives the UI "previously reported" context without recomputing historical
queries.

### Tiered Variant Search

The tiered-variant search endpoint combines annotation search with reported
variant snapshots:

1. Search annotation records by gene, variant, or text.
2. For each annotation hit, find reported snapshot rows using
   `annotation_oid`.
3. Group results by sample and report id.
4. Optionally include annotation text.
5. Return sample/report mapping for UI search results.

This supports searches such as:

- all reports where `FLT3` was reported
- all samples linked to a specific annotation
- all reports using a particular annotation text
- tier distribution for a search term

### Dashboard Analytics

Dashboard tier statistics read from `reported_variants`, not raw variant
collections. That means dashboard report counts represent clinically reported
output, not every detected variant.

## Audit And Integrity Rules

Report save should be treated as a clinical state transition.

Rules:

- preview is read-only
- save is explicit and permissioned
- save creates immutable report metadata
- save creates immutable reported-variant rows
- source variants are not copied wholesale into `reported_variants`
- snapshot rows should not be retroactively edited when tiering changes
- changing filters after save does not change historical report rows
- changing comments after save does not change historical report rows
- changing annotations after save does not change historical report rows
- a new report creates a new `reports` document and new snapshot rows

## Error And Conflict Rules

The report save flow fails before persistence when:

- sample cannot be loaded
- ASPC cannot be resolved
- report inputs are invalid for the selected analyte
- report output path is not configured
- target HTML file already exists
- target PDF file already exists

The flow fails during persistence when:

- HTML cannot be written
- PDF cannot be generated
- report metadata cannot be inserted
- reported snapshot bulk write fails

The intended order is:

1. validate sample and ASPC
2. calculate next report number
3. calculate report path and id
4. verify output paths are available
5. build save-mode report context
6. render HTML
7. write HTML
8. write PDF
9. insert `reports`
10. update `samples`
11. insert `reported_variants`

## Design Benefits

This design gives Coyote3:

- fast report-history lookups
- reliable cross-sample variant mapping
- immutable clinical evidence snapshots
- dashboard metrics based on reported clinical output
- stable report artifacts on disk
- clear separation between temporary review state and saved report state
- a path to regenerate previews without mutating historical evidence
- reproducibility for clinical sign-out review

## Current Implementation Notes

- DNA report snapshots currently focus on SNV reported variants.
- CNV, fusion, translocation, and biomarker report sections are rendered in the
  report context when configured, but equivalent dedicated snapshot collections
  or snapshot row schemas should be designed before treating them as immutable
  cross-sample evidence in the same way as SNVs.
- The renderer outputs clinical report HTML with embedded CSS. The internal
  rendering mechanism is not part of the product contract; the artifact format
  is.
- Preview PDF is for review. Saved PDF is created only during report save.
- Conditional clinical text is currently composed by the reporting
  application. A YAML-driven text rules engine is a planned extension and must
  consume only the prepared report context described above.
