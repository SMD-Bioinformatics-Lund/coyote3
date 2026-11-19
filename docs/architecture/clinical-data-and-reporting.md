# From sample input to saved report

Coyote prepares findings before it generates report wording. The core selects and
interprets the data, published rules supply suggested text, and `smd-reports`
renders the document. Saving captures the reviewed result and its provenance.

This page explains those boundaries for developers and administrators. To perform
a review, use the [clinical review procedure](../user-guide/clinical-review-workflow.md).
For endpoint and saved-record details, use the
[reporting reference](../reference/report-snapshots.md).

![Clinical report generation and persistence](../assets/diagrams/report-generation-flow.svg)

## Follow the data

1. **Ingest:** validate the manifest and readable evidence against the assay's
   accepted and required file types. Commit the sample, findings and ready state
   together. Missing optional expected evidence is recorded separately.
2. **Resolve configuration:** use the sample's recorded ASPC revision, its captured
   assay and gene lists, and the sample's saved filters.
3. **Prepare findings:** apply clinical queries, gene scope, selected transcripts,
   annotation matching and report eligibility.
4. **Generate suggestions:** evaluate the currently applicable published clinical
   rules against the prepared facts. Suggestions do not overwrite reviewed comments.
5. **Preview:** render HTML/PDF without saving report history. The conclusion uses
   the latest visible sample comment.
6. **Save:** verify the reviewed inputs, persist report metadata and finding
   snapshots in one transaction, and publish the staged HTML/PDF artifacts.

An accepted ingestion job is not yet a ready sample. A ready sample can still lack
optional evidence. A preview is not an issued report. See
[ingestion recovery](transactions-and-ingest-recovery.md) and
[report save guarantees](../reference/report-snapshots.md#save-guarantees).

## Configuration and filter ownership

| Resource | Owns |
| --- | --- |
| Assay / ASP | Physical coverage, accepted and required input files, family, platform and accreditation |
| Assay configuration / ASPC | Diagnosis/environment settings, enabled analyses and intents, filter defaults, report sections and their ordering |
| Gene list / ISGL | Versioned gene selections for a particular analysis |
| Sample | Current review flags, sample filters and the recorded configuration reference |
| Query rules | Published finding-selection policy resolved for the current scope |
| Clinical reporting rules | Published conditions and suggested wording resolved for the current scope |
| Saved report | Report-time configuration, findings, rules, filters and artifact provenance |

Identifiers such as `asp_id`, `aspc_id`, `diagnosis_id` and `isgl_id` use
lowercase letters, digits, underscores and hyphens. They are join keys, not display
labels. The `base` diagnosis is a configured fallback; it does not erase the
sample's requested diagnosis.

Intake chooses an active configuration for the assay, diagnosis and environment.
Subsequent operational reads use the recorded `current_aspc_id`. Publishing new
query or clinical rules can affect later requests independently of that ASPC
revision; saved reports retain their original resolved content.

At ingestion, ASPC defaults initialize the sample's filter profiles. Applying
filters changes the sample state; resetting restores the resolved configuration's
defaults. Explicit empty lists remain empty. Table search affects displayed rows,
while analytical filters affect the backend selection.

DNA filter paths include `filters.somatic.snv`, `filters.somatic.cnv`,
`filters.somatic.translocation` and `filters.somatic.coverage`. Independent
germline SNV review uses `filters.germline.snv`; RNA fusion review uses
`filters.somatic.fusion`. Use the [filter reference](../reference/assay-filtering.md)
for fields and query semantics.

### Shared and independent SNV review

With `snv_filter_mode = "shared"`, analysis and reporting use one normal SNV filter
flow. With `independent`, each enabled intent has its own filters, findings and
report facts. A filter update for one intent does not replace the other profile.

A clinical-rule section can target `analysis_intent: somatic` or
`analysis_intent: germline`. An independent profile without approved wording
produces no invented narrative; its enabled result tables remain available.
Finding snapshots record their analysis intent.

### Gene scope and references

For targeted assays, selected lists are bounded by physical assay coverage.
Whole-genome/transcriptome scope and ad-hoc genes follow the assay's configured
selection policy. SNV, CNV and fusion list selections are distinct; one domain's
selection is not reused as another domain's gene filter.

Prepared facts retain the selected list identities, versions and effective gene
scope. A list's total gene count is different from its covered gene count.

VEP metadata is selected by `sample.database_versions.vep`. Transcript selection
and HGNC normalization happen before rule evaluation. Report wording does not
choose a different transcript. See [transcript selection](../reference/assay-filtering.md)
and [reference ownership](../core/package-boundaries.md).

## Finding eligibility

An enabled report section does not automatically include every detected finding.
Preparation applies the per-finding filters and sample context described in the
report eligibility reference below.

- SNVs and RNA fusions require a usable classification in the configured
  `reporting.reportable_tiers` selection, subject to their review and gene filters.
- CNVs and DNA translocations can qualify through explicit report selection or a
  usable allowed tier. False-positive and irrelevant flags still exclude them.
- Tier IV is available when explicitly selected by the configuration. An empty
  tier list disables automatic tier inclusion; it does not restore defaults.
- HRD, MSI and TMB are independent measurements. Missing evidence remains absent;
  a measured numeric zero is not an unavailable result.
- A CNV profile is an image under `files.cnvprofile`, separate from CNV calls and
  coverage. The image itself does not establish a typed normal/abnormal result.

The [report eligibility reference](../reference/report-snapshots.md#annotation-scope-and-report-eligibility)
defines the per-finding selection policy. Clinical rules consume these candidates
and cannot reinstate excluded findings.

## Facts supplied to clinical rules

The authoritative model is `PreparedReportContext` in
`core/src/coyote/application/reporting/clinical_rules/facts.py`. It contains typed
sample, assay and configuration facts; applied gene lists; prepared findings;
measurement rows; and aggregates. Use that model and the
[rule-field reference](../reference/clinical-reporting-rules.md) when authoring test
facts. Report payloads, rule facts and saved resolution snapshots are different
contracts.

The evaluator reads prepared facts without accessing databases, choosing
transcripts, assigning tiers, applying analysis filters or calling external
knowledgebases. Exact published assay/diagnosis/analyte/language scope takes
precedence over the same assay's Base release. An invalid or ambiguous exact
release fails instead of silently using Base.

Missing values, explicit false values and measured zeros remain distinct.
A normal or indeterminate result requires the relevant typed measurement or
assessment; it cannot be inferred from missing input. See
[measurement contracts](../reference/measurement-analyses.md).

## Preview, save and provenance

Preview uses the sample's recorded configuration and current review state. It
returns rendered output and optional finding rows without creating `reports` or
`reported_variants`.

Saving checks that the reviewed inputs are still current. Report metadata,
finding snapshots and the sample's latest-report pointer commit together.
Artifacts are staged exclusively and published with checksum verification; an
existing report file is not overwritten. An uncertain commit is reconciled
before retrying. The [saved-report reference](../reference/report-snapshots.md#save-guarantees)
owns the full persistence and recovery protocol.

Saved evidence includes applied configuration and gene-list snapshots, effective
filters, rule identities/versions/hashes, reference and pipeline versions, selected
annotations, author, UTC time and artifact checksums. Later edits or publications
do not rewrite that evidence.

`finding_comments` stores sample-specific review notes for findings. Reusable
classifications and text belong to `annotation`; report-time rows belong to
`reported_variants`.

## Annotation reference

### Annotation identity and matching {#53-annotation-identity-and-matching}

Every annotation stores the common review context (`variant`, `nomenclature`,
`asp_group`, `asp_id`, `diagnosis_id`, `namespace`, `author`, and `time_created`) and only the identity fields
that belong to its nomenclature:

| Nomenclature | Required identity and context fields |
| --- | --- |
| `p`, `c`, `g` | `variant`, `hgvsp`, `hgvsc`, `genomic`, `genomic_hash`, and `gene`; `transcript` is included when available |
| `cn` | `variant` only |
| `f` | `variant`, `gene1`, and `gene2` |
| `t` | `variant`, `gene1`, and `gene2` |

All fields listed for a nomenclature are structurally present. A related field
may be `null` when exact retained evidence cannot supply it. Unrelated identity
fields are absent rather than stored as `null` placeholders. Small-variant
identities come from the selected transcript consequence and the canonical
`chrom_pos_ref_alt` variant identity. They are written together so a protein,
coding, or genomic annotation can be found through any exact representation
without reconstructing HGVS values later. CNV, fusion, and translocation
identities remain in `variant`; they are not duplicated under `cnv`, `fusion`,
or `translocation` fields.

Matching is identity-equivalent rather than fallback-based:

1. For a small variant, the query requires the same gene and matches any
   available exact `hgvsp`, `hgvsc`, or `genomic` identity. These alternatives
   are joined with `OR`; none has precedence over another.
2. `genomic_hash` supports indexed identity and integrity checks but does not
   replace the readable genomic identity in the annotation contract.
3. For fusion and translocation findings, the query uses the canonical
   breakpoint identity together with the applicable `gene1` and `gene2`
   context.

Fusion analysis tables and detail views resolve the same explicitly selected call.
Its breakpoints and gene context supply the lookup identity, while the parent
fusion's `SAMPLE_ID` supplies sample provenance. Caller names are not classification
identities. With no selected call, analysis does not infer an identity from the first
caller. See [fusion tier status](../user-guide/rna-review.md#fusion-tier-matching).

Matching rows are ordered by `time_created`, with `_id` breaking timestamp ties.
Within each identity/scope, a recorded assignment to the sample or a saved report
reference takes precedence over reusable versions. The newest linked version is
used when several exist; otherwise the newest matching version is considered.
Inactive records cannot automatically tier another sample. A missing `is_active`
field means active for existing records. An older active version is not resurrected
when the newer version is inactive.

Detail views request classification history separately from normal table enrichment.
The current classification contains a `history` list of the other identity-matched,
exact-scope class records, newest first, including inactive versions. This list is
display information and does not assign a tier or qualify a finding for reporting.

#### Authoritative runtime flow

The application has one annotation path:

1. The current finding contract supplies the source identity. Small variants
   use selected-CSQ `HGVSp` and `HGVSc` plus `simple_id`; structural findings
   use their canonical breakpoint identity.
2. The classification service carries that source identity in a transient
   `variant_data` object. This object is service input and is never stored in
   `annotation`.
3. The annotation identity mapper converts the source names once:
   `HGVSp` to `hgvsp`, `HGVSc` to `hgvsc`, and `simple_id` to `genomic`. It
   derives `genomic_hash` from the normalized genomic identity.
4. `AnnotationDoc` validates the nomenclature-specific shape, the required
   fields, and the exclusive `class`-or-`text` rule.
5. The repository writes the validated flat document.
6. Search, classification lookup, text lookup, and deletion query only the
   canonical flat annotation fields shown in the table above.

Runtime code does not query retired annotation aliases such as `var_p`,
`var_c`, `var_g`, `cnv`, `fusion`, `translocation`, nested `variant_data`, or
annotation-level `HGVSp`, `HGVSc`, and `simple_id`. Historical shapes are
understood only by the one-time migration utility. A deployment must migrate
old rows before running the current application; runtime fallback is not a
substitute for migration.

MongoDB `_id` values are stored and queried as `ObjectId`, and `class` is
stored and read as an integer. Runtime reads do not coerce historical string
identifiers or string class values. The migration must normalize those values
before the application is started.

An annotation is either a classification or free text. Classification rows
contain `class` and omit `text`; free-text rows contain `text` and omit
`class`. The collection contract rejects rows containing both or neither.

#### Live annotations and report snapshots

`annotation` and `reported_variants` serve different purposes and therefore
use different identity names:

| Collection | Purpose | Genomic identity |
| --- | --- | --- |
| `annotation` | Current reusable classification or annotation text | `genomic` and `genomic_hash` |
| `reported_variants` | Immutable evidence captured when a report is saved | `simple_id` and `simple_id_hash` |

The report snapshot contract retains explicit query fields such as `gene`,
`genes`, `gene1`, `gene2`, `transcript`, `hgvsc`, `hgvsp`, `genomic`,
`nomenclature`, and `variant`. Type-specific report values also use named
fields, for example `cnv_type` and `ratio` for CNVs or `breakpoint_1` and
`spanning_reads` for fusions. There is no generic `finding_data` or retired
annotation-level `variant_data` object in this contract.

The source collection remains authoritative for the complete finding payload.
`reported_variants` is the immutable, compact record of what was included in a
specific saved report, together with the report-time identity, tier, assay,
diagnosis, environment, and analysis context required for traceability and
cohort queries.

Runtime report-history searches use only these current flat snapshot fields.
They do not inspect old `var_p`, `var_c`, `var_g`, or nested `variant_data`
aliases. Existing report snapshots must therefore be normalized by migration
before they are served by the current application.

### Assay and diagnosis context

Production tier changes and reusable interpretation text require `annotation:publish`
in addition to their curation permission. Assigning a tier or submitting reusable text
is the publication action after review. Sandbox curation uses the normal curation grants
and stays in its environment; it never publishes into the clinical namespace implicitly.
Bundled clinical administrator, manager and standard-user roles include publication;
developer and tester roles do not. Centers control the grant through role administration.

Classification applicability is contextual:

- effective classifications require the same `asp_group`, `asp_id` and
  `diagnosis_id` for every biological group;
- production reads `clinical` annotations only; development, testing and validation
  can read `clinical` and `sandboxed` annotations, but write to `sandboxed`;
- group-scoped, parent-group and other diagnosis interpretations are contextual
  references and require explicit re-tiering to become effective in the sample scope.

Free-text annotations use the same assay/diagnosis context. They are available
as global annotation history. Current text is resolved independently by eligible
scope specificity and recency; an inactive text requires a recorded sample link.

#### Deactivation and historical provenance

New classifications and global text annotations retain `source_sample_id` and
`source_finding_id`. Deactivation sets `is_active: false`, `deactivated_at` and
`deactivated_by`, preserving the original annotation identity, author and time.
Repeating deactivation does not replace its original actor or timestamp.

Diagnosis deactivation affects the matching tier in the current assay and diagnosis.
Group deactivation affects matching class and text records across all assays and
diagnoses in the same biological group and namespace, and requires
`tier:remove:global`. Assigning a tier again creates a new record.

`reported_variants.annotation_oid` and `annotation_text_oid` can establish which
versions a sample used, including inactive versions. Such versions remain usable
for that linked sample. Legacy records without origin or report links cannot prove
a sample's historical tier. Tiered search can display their latest matching version
with a disclaimer; analysis does not automatically assign an inactive legacy tier.
Saved report artifacts and snapshots retain their report-time content.

The implementation owners are `domain/annotation_scope.py`,
`application/interpretation/annotation_enrichment.py` and
`application/common/query_service.py` under `core/src/coyote/`, and
`adapters/mongo/src/coyote_mongo/repositories/annotations.py`. See the
[search provenance reference](../reference/report-snapshots.md#tiered-variant-search)
and [user action reference](../user-guide/actions-and-record-changes.md#inactive-annotations-and-sample-history).

## Investigate a discrepancy

| Symptom | First check |
| --- | --- |
| A submitted sample is missing or not ready | [Job state and ingestion recovery](../operations/ingest-job-recovery.md) |
| A finding is visible in analysis but absent from a report | Report section, sample filters, exact classification scope, tier policy and review flags |
| An expected sentence is absent | Resolved published rule scope, intent, required facts and rule-test trace |
| Preview and save disagree | Changed sample/configuration/review inputs; refresh and review the preview |
| A saved artifact is unavailable | [Artifact state and recovery](../reference/report-snapshots.md#save-guarantees) |

When changing this workflow, verify selected findings, gene scope, missing-value
semantics, preview behaviour and persisted provenance with the affected clinical
tests. Tests of rendering alone do not verify clinical eligibility.
