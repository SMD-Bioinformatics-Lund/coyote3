# OncoKB Integration

!!! info
    OncoKB is used as a clinical knowledgebase signal in Coyote3. Dense tables
    show compact OncoKB markers in the row status column rather than beside the
    gene symbol or in a permanent wide table column.

## Purpose

OncoKB provides curated precision-oncology knowledge about cancer genes,
somatic alterations, structural variants, copy-number alterations, therapeutic
levels, and biological effects.

Coyote3 uses this information in three places:

1. **Variant tables**: compact `OKB` and `Rx` row markers appear in the status
   column when the gene is present in the public cancer-gene cache or in the
   historical local actionable-evidence cache.
2. **Variant detail pages**: the knowledgebase card summarizes public cache records, local historical
   actionable evidence, and optional live public API responses.
3. **Reference refresh**: an authorized operator explicitly queues a background
   refresh from **Admin > Application Controls**. The job resolves the full
   local HGNC catalogue against the public OncoKB catalogues.

## Data Flow

The normal clinical UI reads MongoDB. It should not make one external request
per table cell or per row.

- `oncokb_cancer_genes_public`
- `oncokb_genes_public`
- `onkokb`
- `oncokb_actionable`
- `oncokb_genes`

This is deliberate. Clinical review pages should be fast and reproducible, and
they should not depend on external API availability during case review.

```text
Administrator queues public OncoKB refresh
  -> Celery maintenance task reads every local hgnc_genes identity record
  -> index approved, previous, and alias symbols in memory
  -> fetch the public cancer-gene catalogue once
  -> fetch the public curated-gene catalogue once
  -> retain entries that resolve to a current local HGNC record
  -> upsert the two shared, de-duplicated public collections
  -> remove stale entries from those managed public collections

sample ingest
  -> parse and persist sample findings
  -> make no external OncoKB request

sample variant table
  -> local variants are filtered from MongoDB
  -> public cancer-gene cache is checked
  -> historical local oncokb_actionable is checked for drug-level evidence
  -> API response includes oncokb_gene_map and oncokb_actionable_gene_map
  -> React renders compact public OncoKB and actionable-evidence markers
```

!!! warning
    Do not call the external OncoKB API once per rendered table row or during
    sample ingest. Use the explicit administrator refresh or explicit
    detail-page action. Per-row live calls create latency, rate-limit exposure,
    and non-reproducible review behavior.

## Public Cache Collections

`oncokb_cancer_genes_public` stores one marker record per gene symbol,
derived from the public cancer-gene list and matched to the complete local
`hgnc_genes` catalogue.
It is the primary source for fast OncoKB markers in variant tables and detail
pages.

The gene cache is seeded from:

```text
GET https://public.api.oncokb.org/api/v1/utils/cancerGeneList
```

This endpoint returns public cancer-gene metadata such as `hugoSymbol`,
`entrezGeneId`, `geneAliases`, `geneType`, `occurrenceCount`,
`oncokbAnnotated`, external panel membership flags, and reference transcript
fields. It does not return therapeutic actionability rows.

The collection stores normalized fields only. It does not keep a duplicated raw
endpoint payload because the indexed fields used by the application are already
represented explicitly.

When HGNC metadata is available locally, Coyote3 stores the approved HGNC symbol
as `gene` and keeps previous/alias symbols as searchable metadata. This matters
for targeted panels: panel definitions and historical VCF annotations may use an
older symbol, while the current public knowledgebase expects the approved HGNC
symbol.

`oncokb_genes_public` stores public gene-summary records from the curated-gene
list for genes that resolve to the complete local `hgnc_genes` catalogue. It
enriches detail-page context with published gene-level summary and background
text.

The gene-summary cache is seeded from:

```text
GET https://public.api.oncokb.org/api/v1/utils/allCuratedGenes?includeEvidence=true
```

This endpoint returns curated gene metadata such as `hugoSymbol`, `entrezGeneId`,
`geneType`, `summary`, `background`, `setting`, highest public level fields, and
reference transcripts. Coyote3 stores normalized fields in
`oncokb_genes_public`; it does not store a duplicate raw response blob there.

!!! info "Historical local collections"
    `oncokb_actionable` is not the same data as `/utils/cancerGeneList`.
    The historical collection contains treatment/actionability-style rows such
    as alteration, drugs, level, cancer type, PMIDs, and protein change. Because
    the public API excludes therapeutic data, those historical rows remain useful
    as the center's local drug-evidence source. Dense tables show a separate
    compact actionable marker for genes represented in this collection. They are
    not used to decide whether a gene receives a current public OncoKB cancer-gene
    marker.

!!! info "Cancer-gene cache refresh"
    `oncokb_cancer_genes_public` and `oncokb_genes_public` are maintained by a
    manually queued Celery maintenance task. The task reads the populated
    `hgnc_genes` collection, matches approved, previous, and alias symbols,
    fetches each public catalogue endpoint once, then reconciles the local
    public-cache records.
    A failed API call or empty HGNC catalogue fails the task and records an audit
    event; it never silently replaces the cache with an empty result.

!!! info "Transcript selection"
    During DNA VCF ingest, Coyote3 selects the displayed `selected_CSQ`
    transcript using HGNC metadata. Transcript records are resolved by HGNC ID
    first, then by approved symbol, previous symbol, or alias symbol. MANE Plus
    Clinical has highest priority, followed by MANE Select, then the center
    VEP canonical protein-coding,
    protein-coding transcript, and finally the first available transcript. The
    selected gene symbol is normalized to the approved HGNC symbol. The raw
    VEP symbol remains part of the immutable VEP evidence in `anno_vep`; it is
    not copied into mutable variant display state.

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
small-variant annotation key for explicit on-demand detail lookups:

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

Coyote3 exposes configuration keys for this integration:

- `ONCOKB_BASE_URL`
- `ONCOKB_PUBLIC_LOOKUPS_ENABLED`
- `ONCOKB_REQUEST_TIMEOUT_SECONDS`

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
- Use `oncokb_genes_public` for public curated-gene summaries.
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
