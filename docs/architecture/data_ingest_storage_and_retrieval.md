# Clinical data lifecycle: ingest, storage, and retrieval

This reference explains how Coyote3 accepts pipeline output, validates it, stores it, and returns it to clinical review and reporting workflows. It complements the [runtime data contracts](data_contracts.md), [sample input files](../api/sample_input_files.md), and [clinical data and reporting flow](clinical_data_and_reporting_flow.md).

## Core model

Each loaded sample has one canonical samples document. It stores identity, assay scope, source-file metadata, the resolved ASPC, the current filter snapshot, status, and lightweight result counts. Analysis results are stored in separate collections and linked to the sample by SAMPLE_ID, the string form of the sample document ObjectId.

This separation keeps sample lists efficient, permits independent server-side filtering and pagination for each analysis type, keeps large transcript payloads out of mutable small-variant rows, and lets saved reports preserve their historical context. Collection names are resolved from api/config/center/collections.toml; names in this guide are defaults.

## From manifest to ready sample

A completed YAML manifest is the ingest declaration. Pipeline keys such as assay, subpanel, and profile are normalized to asp_id, subpanel_id, and environment before configuration is resolved. Canonical identifiers are lower-case join keys; display labels remain human-facing values.

1. A watch-folder task or authorized internal request receives a manifest.
2. The service validates identity, case/control structure, omics layer, platform, sequencing scope, and the declared file-key family against SamplesDoc.
3. It resolves the active ASP from assay_specific_panels and the active ASPC from asp_configs using asp_id, subpanel_id, and environment. If the requested subpanel configuration is absent, the configured base ASPC is resolved and the sample records that base configuration is in use.
4. The ASP defines accepted and required file keys. The ASPC defines enabled analysis types. Every enabled analysis makes its configured source file required. An optional file may be absent only when it is not declared; a declared file must exist, parse, validate, and persist successfully.
5. The DNA or RNA parser reads declared files into an internal preload payload. Parsers never write directly to MongoDB.
6. Every database-backed payload is normalized through the Pydantic collection registry, then dependent records are written before the sample is persisted with current counts and ready state.
7. If a dependent write fails, the service restores the earlier dependent state for an update or removes staged records for a new sample. A failed ingest cannot leave a ready sample.
8. The manifest receives its configured done or failed suffix and an ingest audit event. Optional public knowledgebase enrichment is separate from readiness.

> **Info: Pipeline paths**
>
>
> Manifests retain pipeline host paths. API and Celery containers must be able to read those paths through their mounts. The paths are preserved in the sample document so the originating artifact remains identifiable.
>

## Configured file ownership

The center-configurable mapping is in api/config/center/clinical_vocabulary.toml. It defines accepted external manifest keys and their analysis ownership. An ASP may further restrict those keys with expected_files and required_files. ASPC analysis_types determine which expected artifacts are required for that configuration.

| Omics layer | Analysis type | Default manifest key | Internal preload | Persistent destination |
| --- | --- | --- | --- | --- |
| DNA | SNV | vcf_files | snvs | variants and anno_vep |
| DNA | CNV | cnv | cnvs | cnvs |
| DNA | translocation / DNA fusion | transloc | transloc | translocations |
| DNA | biomarker / TMB | biomarkers | biomarkers | biomarkers |
| DNA | coverage | cov | cov | panel_coverage |
| DNA | CNV profile | cnvprofile | none | File metadata only |
| DNA | PGx | pgx | pgx | pgx |
| RNA | fusion | fusion_files | fusions | fusions |
| RNA | expression | expression_path | rna_expr | rna_expression |
| RNA | classification | classification_path | rna_class | rna_classification |
| RNA | QC | qc | rna_qc | rna_qc |
| RNA | PGx | pgx | pgx | pgx |

Manifest names are center-configurable. Internal preload names are application contracts because they map to Pydantic models and repositories. The runtime checks this binding so a configured file cannot silently lose a persistence destination.

## Storage contract by artifact

Before dependent records are written, ingest attaches canonical sample linkage and sample name. Each record is validated through api/contracts/schemas/registry.py.

| Collection | One document per | Stored content | How it is fetched |
| --- | --- | --- | --- |
| samples | sample | identity, assay scope, ASPC, files, filter state, counts, ingest and report state | list and overview queries |
| variants | small variant | selected display consequence, complete `consequence_terms` index, genotype values, genomic identity, flags, current tier, compact annotations | SAMPLE_ID with server-side filter, search, sort, and pagination |
| anno_vep | genomic small variant and VEP release | immutable complete VEP CSQ transcript evidence, genomic identity, and VEP version | genomic identity plus sample database_versions.vep |
| cnvs | CNV call | genes, region, callers, ratio/copy number, purity/SR when supplied, flags, tier | SAMPLE_ID plus CNV filters |
| translocations | structural call | breakpoints, genes, normalized annotations, call data, flags, tier | SAMPLE_ID plus translocation filters |
| biomarkers | sample | normalized biomarker result data | SAMPLE_ID |
| panel_coverage | sample | coverage metrics and gene/group coverage trees | SAMPLE_ID |
| fusions | fusion event | genes, caller calls, selected call, reads, effect, descriptions, flags, tier | SAMPLE_ID plus fusion filters |
| rna_expression | sample | selected-gene TPM, reference values, and z-scores | SAMPLE_ID |
| rna_classification | sample | classifier classes, scores, source metadata | SAMPLE_ID |
| rna_qc | sample | RNA quality-control measurements | SAMPLE_ID |
| pgx | sample or PGx result set | declared pharmacogenomic result payload; source arrays are retained under `records` | SAMPLE_ID |
| reports | saved report | rendered content, configuration references, filters, report metadata | sample and report id |
| reported_variants | report finding | frozen typed snapshot for an SNV, CNV, fusion, translocation, biomarker, or PGx result | report, sample, and `analysis_type` linkage |

### DNA small variants

The DNA parser opens the VEP-annotated VCF with pysam, converts each record to the internal VCF representation, normalizes call and annotation values, enriches stable genomic identity, and chooses one display transcript using the configured transcript-selection order.

The compact variants document contains the selected consequence, table values, and
`consequence_terms`: the ordered, de-duplicated union of every parsed VEP
`Consequence` term across all transcripts for that variant. The complete
normalized CSQ transcript array is stored in `anno_vep` for the sample VEP
release and then removed from the mutable variant row. The alternate-transcript
table reads `anno_vep`; it does not reconstruct transcripts from the display
row. The unstructured VCF `INFO.Annotation` value is discarded during DNA
ingest because it has no defined consumer or clinical contract; it is not the
structural-variant `ANN.Annotation` field.

VEP `CLIN_SIG` is stored as an ordered list in both the selected variant CSQ
and every `anno_vep.CSQ[]` transcript. A scalar such as
`uncertain_significance&likely_pathogenic` becomes
`["uncertain_significance", "likely_pathogenic"]`. Ingest accepts scalar or
list input, splits ampersand-delimited terms, removes duplicates, and preserves
first-seen order.

The selected consequence is a display anchor only. It contains the values needed
for the selected row, such as `Feature`, `SYMBOL`, `HGNC_ID`, HGVS, impact,
prediction values, exon/intron, and consequence. It intentionally excludes
transcript-selection evidence including MANE values, HGNC match provenance,
canonical markers, and transcript tags. Raw VEP MANE and canonical values stay
with the versioned `anno_vep.CSQ[]` evidence. HGNC match state and display
badges are derived when a transcript payload is read from the current
`hgnc_genes` collection, so an HGNC refresh does not require rewriting VEP
evidence.

#### VEP evidence versioning and transcript display

`anno_vep` has one immutable document for each `(simple_id_hash, vep_version)`
pair. Ingesting a genomic variant already known for VEP 103 does not overwrite
that evidence. Ingesting the same genomic variant with VEP 110 creates a
second document. A sample always reads the document matching its own
`database_versions.vep`, which makes alternate-transcript review reproducible
for that sample's annotation release.

The vault intentionally does not store mutable HGNC-derived values such as
`HGNC_MATCHED`, `HGNC_MATCH_SOURCE`, `VEP_SYMBOL`, `transcript_tags`,
`canonical_source`, or `is_canonical`. On a detail request the API resolves the
transcript's HGNC ID first, then its approved symbol, previous symbols, and
aliases. It uses that current record to decorate the response with MANE and
VEP-canonical badges. A later HGNC update therefore changes presentation and
normalization where appropriate without mutating historical VEP transcript
evidence.

#### Small-variant table request cost

The small-variant endpoint filters and sorts the complete matching result set
before pagination so sorting remains correct across every page. It then returns
only the requested page. Page-only work includes knowledgebase markers and
display enrichment. Report-wide section construction and Swedish report text
generation are reserved for report/export contexts. The comment suggestion is
also generated only after the reviewer selects **Suggest text**, rather than
when a table tab opens.

Sorting by tier is the deliberate exception: tier classification is part of
the requested global order, so the API resolves that context before sorting.
Other ordinary table sorts retain page-only display enrichment.

SNV consequence filtering queries `variants.consequence_terms`, never
`INFO.selected_CSQ.Consequence` and never `INFO.CSQ`. This means a clinically
relevant term on an alternate transcript remains queryable while the selected
transcript remains stable for display. The compound index on
`SAMPLE_ID, consequence_terms` supports that query shape.

> **Warning: Existing DNA records**
>
>
> Records without `consequence_terms` must be backfilled or re-ingested before
> consequence filtering can include them. Coyote3 ingestion derives
> `consequence_terms` from the parsed VEP records
> only from the matching `anno_vep` record for the sample's VEP version. It
> leaves a row untouched when that evidence is absent and reports it for
> review; it does not infer terms from the selected transcript.
>

The sample stores VCF-derived database versions under database_versions. Database_versions.vep is the only sample-level VEP version field.

#### Population frequency fields

The small-variant document contains gnomad_frequency, gnomad_max, exac_frequency, and thousandG_frequency when VEP supplies them.

| Stored field | Source field | Current normalization |
| --- | --- | --- |
| gnomad_frequency | gnomAD_AF, then gnomADg_AF | Maximum numeric allele frequency in the first CSQ entry |
| gnomad_max | MAX_AF | Stored when the same CSQ entry contains gnomAD annotation |
| exac_frequency | ExAC_MAF | Frequency paired with the ALT allele in the first CSQ entry |
| thousandG_frequency | GMAF | Frequency paired with the ALT allele in the first CSQ entry |

> **Warning: Current population-frequency behavior**
>
>
> In the current parser, these values are taken from the first transient parsed
> CSQ entry before display-transcript selection. The temporary `INFO.CSQ`
> payload is moved to `anno_vep` before the compact variant record is saved.
> These values are not calculated from the selected transcript or aggregated
> across all applicable transcripts. The source VCF must therefore use a
> stable CSQ order. A future parser revision should resolve allele-level
> values across applicable CSQs deterministically before this becomes an
> assay-independent clinical protocol.
>

### CNVs

The CNV parser accepts a JSON list of calls or an object whose values are calls. It converts caller labels to a lower-case list, normalizes numeric probe counts and ratios, and derives an event type from a ratio only when the pipeline did not provide one. A CNV profile image is not a CNV call: cnvprofile remains a validated file resource and the CNV JSON creates cnvs records.

The CNV table reads only the sample-linked records, then applies the sample CNV filters and a CNV gene list if one has been applied. Callers, copy number/ratio, purity, supporting reads, status, artifact state, and tier remain separate data concepts. Missing source values remain missing rather than becoming a clinical conclusion.

### DNA translocations

The structural-variant parser reads the translocation VCF, normalizes split annotation values, retains selected annotation where present, and writes one translocations document per accepted call. The table applies translocation-specific filters and an attached translocation/fusion gene list. An SNV list never implicitly filters translocations.

### Biomarkers and coverage

Biomarker and coverage JSON are stored as sample-scoped typed documents. The ingest boundary normalizes supported biomarker spelling variants before validation. Panel coverage is used by coverage views, the sample overview, and dashboard summaries. It is structured quality data, whereas a CNV profile is a viewable source image.

### RNA fusions

RNA fusion input is a JSON list of fusion events. Every event must have caller calls and exactly one selected call. Ingest makes the selection explicit for every call, using 1 for the selected call and 0 for alternatives. It provides safe empty defaults for missing effect, description, and common-read values, and rejects malformed selections.

The fusions table filters only by an applied fusion gene list. A fusion matches when either participating gene belongs to the list. Caller, effect, description terms, spanning reads, spanning pairs, flags, and tier are independent filter dimensions. Description-term color groups are configurable UI vocabulary; they do not alter source descriptions.

### RNA expression, classification, and QC

Expression, classification, and QC files are JSON documents held in separate sample-linked collections. They are normally enabled only for WTS-style ASPCs. Their tabs appear only when the sample ASPC enables the analysis and the declared file has been ingested.

> **Info: Missing RNA tabs**
>
>
> A missing expression, classification, or QC tab normally means that analysis is not enabled for the sample. It does not mean an enabled analysis returned an empty result.
>

### File-only resources

CNV profile and PGx source files are validated when declared and retained under samples.files. They currently do not create a dependent collection document. CNV profile images are served from their declared source resource for the split CNV view. PGx remains an input artifact until the application introduces a typed PGx results collection.

## Retrieval paths

The API resolves the user-facing sample name to the canonical sample document. Its ObjectId string becomes the SAMPLE_ID query value for dependent collections, allowing stable user-facing URLs without exposing ObjectIds in normal sample routes.

| Workflow | Reads | Retrieval logic |
| --- | --- | --- |
| Sample list and overview | samples | Reads sample-level fields and counts only; full findings are not loaded |
| Small variants | variants, anno_vep, reference metadata, applied ISGLs | Server-side filters, search, multi-column sort, and pagination; alternate transcripts come from anno_vep for the sample VEP version |
| CNVs and profile | cnvs, samples.files.cnvprofile | CNV filters and CNV ISGL scope; profile is read from the declared resource |
| DNA translocations | translocations | Structural-event filters and only a translocation/fusion list attached to the sample |
| RNA fusions | fusions | Fusion gene, caller, effect, description-term, and read filters |
| Expression, classification, QC | rna_expression, rna_classification, rna_qc | Available only to compatible RNA samples and enabled ASPC analyses |
| Coverage and biomarkers | panel_coverage, biomarkers | Sample-scoped structured documents |
| Reports | samples, ASP, ASPC, ISGLs, filtered findings, reports, reported_variants | A prepared report context is built from active data; saved reports retain their own snapshots |

Permissions and module availability checks precede reads. Query caching is keyed by sample, intent, filter state, page, and multi-column sort state. Curation or filter actions invalidate affected cached queries so the next table read reflects persisted data.

The sample catalog CSV has a stable set of columns for supported analysis data
counts and availability. It also loads biomarker documents for the exported
sample rows in one bulk query and flattens their values into separate columns.
Missing data remains an empty CSV cell, so every exported row has the same
column structure.

## Gene scope

The sample filter state stores applied ISGL identities. Each analysis consumes only its corresponding list type.

| Analysis | Applied list type | Fallback with no attached list |
| --- | --- | --- |
| Small variants | SNV | ASP covered_genes; no gene restriction when empty |
| CNVs | CNV | ASP covered_genes; no gene restriction when empty |
| DNA translocations | translocation or fusion | ASP covered_genes; no gene restriction when empty |
| RNA fusions | fusion | ASP covered_genes; no gene restriction when empty |
| Expression | expression | ASP or analysis-specific configured scope |

An ISGL can declare multiple list types and be selectable for several analyses. It filters an analysis only when that analysis-specific filter has applied it. Selecting an SNV list therefore does not filter CNVs or fusions.

## Reporting, rollback, and deletion

Review actions update the active analysis record and create their audit events. Reusable tiered annotations live in annotation; reported_variants records freeze the subset attached to a saved report. The report service receives filtered findings, biomarkers, coverage, applied gene lists, ASP, ASPC, and static report rules. It does not re-parse source files.

Annotation persistence uses one flat, validated contract. Current finding
fields are translated at the classification boundary, then only canonical
`hgvsp`, `hgvsc`, `genomic`, `genomic_hash`, gene, transcript, breakpoint, and
review-context fields are stored and queried. The temporary `variant_data`
service payload is not persisted. Retired annotation fields are accepted only
by the migration utility and have no runtime read fallback. See
[clinical data and reporting flow](clinical_data_and_reporting_flow.md#53-annotation-identity-and-matching)
for the complete nomenclature shapes and matching protocol.

A re-ingest snapshots dependent records that will be replaced. If a new write fails, the earlier records are restored. Administrative sample deletion removes sample-bound variants, CNVs, coverage, translocations, fusions, biomarkers, RNA expression, classification, QC, sample comments, finding comments, reports, and reported-variant snapshots before deleting the sample. The deletion audit event keeps sample name and internal identifier as traceability metadata.

## Operational diagnosis

When a sample is not ready or an expected tab is missing:

1. Check the manifest suffix and ingest audit event.
2. Confirm the manifest resolves to an active ASP and ASPC.
3. Confirm every ASPC-enabled analysis has a declared readable file.
4. Compare sample data counts with dependent collection counts by SAMPLE_ID.
5. Confirm the sample omics layer and ASPC analysis_types; DNA endpoints are not called for RNA samples, and RNA-only endpoints are not called for DNA samples.
6. For transcript issues, check the sample VEP version and matching anno_vep record before examining the selected display transcript.

For field-level collection shapes, see [collection contracts](../api/collection_contracts.md). For the manifest format and key definitions, see [sample input files](../api/sample_input_files.md).
