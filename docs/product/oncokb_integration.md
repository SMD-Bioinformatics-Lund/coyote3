# OncoKB Integration

!!! info
    OncoKB is used as a clinical knowledgebase signal in Coyote3. Dense tables
    show compact OncoKB markers in the row status column rather than beside the
    gene symbol or in a permanent wide table column.

## Purpose

OncoKB provides curated precision-oncology knowledge about cancer genes,
somatic alterations, structural variants, copy-number alterations, therapeutic
levels, and biological effects.

Coyote3 uses this information in four places:

1. **Variant tables**: compact `OKB` and `Rx` row markers appear in the status
   column when the gene is present in the public cancer-gene cache or in the
   historical local actionable-evidence cache.
2. **Variant detail pages**: the knowledgebase card summarizes public cache records, local historical
   actionable evidence, and optional live public API responses.
3. **Annotation text**: auto-generated clinical text can include an OncoKB gene
   link when the gene is represented in the knowledgebase.
4. **Ingest-time cache building**: DNA VCF ingest batches new HGVSg-first
   queries against the public OncoKB API for genes already present in the local
   public cancer-gene cache and persists responses for later local review.

## Data Flow

The normal clinical UI reads MongoDB. It should not make one external request
per table cell or per row.

- `oncokb_cancer_genes_public`
- `oncokb_genes_public`
- `oncokb_public`
- `onkokb`
- `oncokb_actionable`
- `oncokb_genes`

This is deliberate. Clinical review pages should be fast and reproducible, and
they should not depend on external API availability during case review.

```text
VCF ingest
  -> parse and persist variants
  -> normalize selected CSQ symbols through HGNC IDs, previous symbols, and aliases
  -> build unique public OncoKB HGVSg queries for cached OncoKB genes only
  -> fall back to protein-change queries only when HGVSg is unavailable
  -> skip query hashes already present in oncokb_public
  -> POST missing queries in batches to public.api.oncokb.org
  -> store variant-level responses in oncokb_public
  -> store annotation-derived gene summaries in oncokb_genes_public

sample variant table
  -> local variants are filtered from MongoDB
  -> public cancer-gene cache is checked
  -> historical local oncokb_actionable is checked for drug-level evidence
  -> API response includes oncokb_gene_map and oncokb_actionable_gene_map
  -> React renders compact public OncoKB and actionable-evidence markers
```

!!! warning
    Do not call the external OncoKB API once per rendered table row. Batch at
    ingest time or use the explicit detail-page action. Per-row live calls create
    latency, rate-limit exposure, and non-reproducible review behavior.

## Public Cache Collections

`oncokb_public` stores variant-level public API responses. The unique identity
is `query_hash`, derived from the query mode and public OncoKB request fields.
For HGVSg queries, the identity is derived from:

- `hgvsg`
- `referenceGenome`
- requested public evidence types

For fallback protein-change queries, the identity is derived from:

- `gene.hugoSymbol`
- `alteration`
- `referenceGenome`
- requested public evidence types

The hash intentionally does not include `sample_id`. If the same
`17:g.76736896T>C` or the same fallback protein-change query appears in many
samples on the same reference genome, all samples reuse one public annotation
record.

Important fields:

- `query_hash`: stable cache key.
- `query_method`: `hgvsg` or `protein_change`.
- `gene`, `hgvsg`, `alteration`, `reference_genome`: searchable query identity.
- `query`: exact public OncoKB request payload.
- `response`: exact public OncoKB response payload.
- `data_version`: OncoKB public data version when returned.
- `gene_exist`, `variant_exist`: public response booleans when returned.
- `variant_ids`, `sample_ids`, `sample_names`: provenance for the first cache
  build pass that observed this query.
- `public_api`: always `true`.
- `therapeutic_data_included`: always `false`.

`oncokb_cancer_genes_public` stores one marker record per gene symbol,
derived from the public cancer-gene list. It is the primary source for fast
OncoKB markers in variant tables and detail pages.

The gene cache is seeded from:

```text
GET https://public.api.oncokb.org/api/v1/utils/cancerGeneList
```

This endpoint returns public cancer-gene metadata such as `hugoSymbol`,
`entrezGeneId`, `geneAliases`, `geneType`, `occurrenceCount`,
`oncokbAnnotated`, external panel membership flags, and reference transcript
fields. It does not return therapeutic actionability rows.

The collection stores normalized fields only. It does not keep a duplicated raw
`oncokb` blob because the cancer-gene endpoint payload is already represented by
the indexed fields used by the application. Exact raw responses are retained in
`oncokb_public` for variant-level annotation calls, where response reproducibility
is clinically useful.

When HGNC metadata is available locally, Coyote3 stores the approved HGNC symbol
as `gene` and keeps previous/alias symbols as searchable metadata. This matters
for targeted panels: panel definitions and historical VCF annotations may use an
older symbol, while the current public knowledgebase expects the approved HGNC
symbol.

`oncokb_genes_public` stores public gene summary records observed from
the public curated-gene list and variant-level annotation responses. It enriches
detail-page context when the public API returns or publishes gene-level summary
and background text.

The gene-summary cache is seeded from:

```text
GET https://public.api.oncokb.org/api/v1/utils/allCuratedGenes?includeEvidence=true
```

This endpoint returns curated gene metadata such as `hugoSymbol`, `entrezGeneId`,
`geneType`, `summary`, `background`, `setting`, highest public level fields, and
reference transcripts. Coyote3 stores normalized fields in
`oncokb_genes_public`; it does not store a duplicate raw response blob there.
Variant-level public API calls may later refresh the same collection with
annotation-derived summary fields for genes seen during ingest.

!!! info "Historical local collections"
    `oncokb_actionable` is not the same data as `/utils/cancerGeneList`.
    The historical collection contains treatment/actionability-style rows such
    as alteration, drugs, level, cancer type, PMIDs, and protein change. Because
    the public API excludes therapeutic data, those historical rows remain useful
    as the center's local drug-evidence source. Dense tables show a separate
    compact actionable marker for genes represented in this collection. They are
    not used to decide whether a gene receives a current public OncoKB cancer-gene
    marker.

!!! warning "Cancer-gene cache seeding"
    `oncokb_cancer_genes_public` and `oncokb_genes_public` are populated by
    explicit operational seed actions, not automatically inside every VCF
    ingest. Ingest reads the local cancer-gene collection to decide which
    variants should be sent for public OncoKB variant-level annotation.

!!! tip
    Keep public cache writes insert-first. Existing `query_hash` records are
    skipped by default. Add a dedicated refresh command if a center wants to
    rebuild public cache records after an OncoKB data-version change.

!!! info "Transcript selection"
    During DNA VCF ingest, Coyote3 selects the displayed `selected_CSQ`
    transcript using HGNC metadata. Transcript records are resolved by HGNC ID
    first, then by approved symbol, previous symbol, or alias symbol. MANE Plus
    Clinical has highest priority, followed by MANE Select, then the center
    canonical map after HGNC-symbol normalization, VEP canonical,
    protein-coding transcript, and finally the first available transcript. The
    selected gene symbol is normalized to the approved HGNC symbol, and the raw
    VEP symbol is retained as `VEP_SYMBOL` only when it differs.

## Public API Notes

Coyote3 uses the public OncoKB API host:

```text
https://public.api.oncokb.org/api/v1
```

This public endpoint does not require a commercial or production OncoKB license
and does not require an API token. It provides public API access across genes,
excluding therapeutic data.

The public API includes endpoints for mutation, copy-number, structural-variant,
HGVSg, cancer-gene, level, and info lookups. Coyote3 uses HGVSg as the primary
small-variant annotation key for on-demand detail lookups and ingest-time cache
enrichment:

```text
POST /annotate/mutations/byHGVSg
```

Each query sends `hgvsg`, `referenceGenome`, `evidenceTypes`, and the Coyote3
variant identifier. HGVSg is preferred because it is genomic and
transcript-independent. This avoids false misses when the displayed transcript
protein change differs from the canonical isoform expected by OncoKB.

When VEP has already supplied `HGVSg`, Coyote3 uses that value. If it is absent,
Coyote3 constructs HGVSg only for simple SNVs from `CHROM`, `POS`, `REF`, and
`ALT`. Complex insertions, deletions, and delins events are not hand-normalized
from raw VCF fields; they use VEP-provided `HGVSg` when present, otherwise the
system falls back to:

```text
POST /annotate/mutations/byProteinChange
```

The protein-change fallback sends the selected gene symbol, one-letter protein
alteration, reference genome, and evidence types. It is intentionally secondary
because protein-change annotation can be isoform-sensitive.

Coyote3 exposes configuration keys for controlled future use:

- `ONCOKB_BASE_URL`
- `ONCOKB_DEMO_BASE_URL`
- `ONCOKB_PUBLIC_LOOKUPS_ENABLED`
- `ONCOKB_REQUEST_TIMEOUT_SECONDS`
- `ONCOKB_PUBLIC_BATCH_SIZE`

!!! caution
    Public OncoKB responses exclude therapeutic data. They are useful for gene,
    variant, mutation-effect, diagnostic, and prognostic context where available,
    but they should not be presented as a therapy recommendation source.

## UI Rules

- Do not show OncoKB as an inline badge beside a gene symbol in dense tables.
- Show OncoKB markers in the compact row status column:
  - `OKB`: public OncoKB cancer gene.
  - `Rx`: historical local OncoKB actionable/drug-evidence fields.
- Prefer `oncokb_cancer_genes_public` for current public marker badges.
- Use `oncokb_genes_public` for public curated-gene and annotation-derived summaries.
- Show historical local `oncokb_actionable` as a distinct actionable/drug-evidence
  marker in dense tables and as supplemental center-specific evidence in
  knowledgebase cards.
- In variant detail pages, keep OncoKB inside the single Knowledge Bases card.
  Use collapsible sections to combine prefilled public cache data
  (`oncokb_cancer_genes_public` and `oncokb_genes_public`) with the explicit
  public API lookup button. The cached fields provide stable review context; the
  button lets the reviewer refresh public evidence on demand without making table
  rendering depend on external API calls.
- Do not add a dedicated OncoKB column to dense variant tables.
- In detail pages, keep OncoKB evidence in the Knowledge Bases card and fetch
  public API evidence only when the reviewer clicks the OncoKB API action.
