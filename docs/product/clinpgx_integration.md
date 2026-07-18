# ClinPGx Integration

!!! info
    ClinPGx is used as a pharmacogenomics knowledgebase signal in Coyote3.
    Dense tables use a local `clinpgx_genes_public` cache for speed. Detail
    pages use the public ClinPGx API on demand for guideline, label, drug,
    pathway, and variant annotation context.

## Purpose

ClinPGx aggregates PharmGKB, CPIC, and PharmCAT resources. Coyote3 uses it to
flag genes with pharmacogenomic relevance without adding another wide table
column to clinical review tables.

The ClinPGx table signal is gene-level:

- `PGx` means the selected variant gene is present in the local ClinPGx public
  gene cache.
- `VIP`, `Variant annotation`, and `CPIC guideline` are rendered in the detail
  knowledgebase card when available.
- The public API action fetches the current ClinPGx knowledge summary for the
  selected variant gene without storing that API response in MongoDB.

!!! warning
    ClinPGx content is a knowledgebase context signal. It does not replace
    clinical interpretation, reporting policy, or local laboratory sign-out
    workflows.

## Data Sources

### Local Gene Cache

`clinpgx_genes_public` is populated from the ClinPGx `genes.tsv` export bundled
as a zip file during controlled seed operations.

Stored fields include:

- `pharmgkb_accession_id`
- `symbol`
- `hgnc_id`
- `ncbi_gene_id`
- `ensembl_id`
- `alternate_symbols`
- `alternate_names`
- `is_vip`
- `has_variant_annotation`
- `has_cpic_dosing_guideline`
- `cross_references`
- GRCh37 and GRCh38 coordinates
- source metadata from the zip export

The table badge lookup matches the selected HGNC-normalized symbol first and
then checks alternate symbols from the ClinPGx file. The displayed variant gene
symbol is not rewritten by the PGx cache.

### Public API

Coyote3 uses:

```text
https://api.clinpgx.org/v1/data/gene/{id}
https://api.clinpgx.org/v1/data/gene?symbol={symbol}&view=max
https://api.clinpgx.org/v1/data/guidelineAnnotation?relatedGenes.accessionId={id}&view=min
https://api.clinpgx.org/v1/data/label?relatedGenes.accessionId={id}&view=min
https://api.clinpgx.org/v1/data/variantAnnotation?location.genes.symbol={symbol}&view=min
https://api.clinpgx.org/v1/report/connectedObjects/{id}/Chemical
https://api.clinpgx.org/v1/report/connectedObjects/{id}/Pathway
```

The identifier route is preferred when the local cache has a
`pharmgkb_accession_id`. Symbol query is used only as a fallback.

!!! caution
    ClinPGx asks API clients to limit requests to 2 requests per second. Coyote3
    therefore does not call the external ClinPGx API for each rendered table row.
    External requests are made only through explicit user actions on detail pages.

## Review Flow

```text
VCF ingest selects the clinical transcript and HGNC-normalized gene
  -> variant list payload collects selected genes for the current page
  -> clinpgx_genes_public is queried in one local batch
  -> UI renders compact PGx badges in the row status column
  -> variant detail card shows cached PGx gene facts
  -> reviewer may click Fetch ClinPGx for current public API context
  -> UI renders guidelines, labels, drugs, pathways, VIP summary, and annotation examples
```

## Seeding

Run the seed command from the repository root:

```bash
python scripts/seed_clinpgx_genes_public.py \
  --zip .design/clinPGx_genes.zip \
  --mongo-uri "$MONGO_URI" \
  --db "$COYOTE3_DB"
```

The seed is an upsert by approved symbol. It does not contain sample identifiers
and it does not mutate variant, sample, report, or annotation collections.

!!! tip
    Re-run the seed after replacing the ClinPGx export zip with a newer official
    file. The importer updates `last_seen_at` and refreshes the public gene
    flags while preserving existing Mongo object identifiers for unchanged
    symbols.

## UI Rules

- Do not show the OncoKB or ClinPGx badge next to the gene name in dense tables.
- Render knowledgebase markers in the compact status column:
  - `OKB`: public OncoKB cancer gene.
  - `Rx`: historical local OncoKB actionable/drug evidence.
  - `PGx`: ClinPGx public gene cache hit.
- Link `OKB` to the OncoKB gene page.
- Link `PGx` to the ClinPGx public API gene record when a ClinPGx identifier is
  known.
- On variant detail pages, show ClinPGx inside the single Knowledge Bases card.
  The local section stays compact and shows only the useful review fields:
  ClinPGx/PharmGKB ID, HGNC ID, VIP status, variant-annotation availability,
  and CPIC dosing-guideline availability. The API-derived section expands after
  the reviewer clicks the ClinPGx fetch action and can show VIP summary,
  guideline annotations, drug labels, top connected drugs, pathways, and variant
  annotation examples.
- Keep ClinPGx separate from OncoKB inside the Knowledge Bases card. They are
  different knowledge sources and should not be visually nested under each other.
- Keep gene-display normalization separate from knowledgebase highlighting. A
  previous HGNC symbol can still be displayed while the knowledgebase lookup is
  resolved through the approved symbol or known aliases.

## Configuration

Environment variables:

- `CLINPGX_BASE_URL`: defaults to `https://api.clinpgx.org/v1`.
- `CLINPGX_PUBLIC_LOOKUPS_ENABLED`: defaults to enabled.
- `CLINPGX_REQUEST_TIMEOUT_SECONDS`: defaults to 3 seconds.

Collection configuration:

```toml
clinpgx_genes_public_collection = "clinpgx_genes_public"
```

The collection name is resolved from `api/config/coyote3_collections.toml`, not
hard-coded in application logic.
