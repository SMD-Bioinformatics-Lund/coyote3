# Knowledgebase Evidence

Coyote3 presents local and explicitly requested external knowledgebase context
alongside clinical findings. Knowledgebase evidence supports interpretation; it
does not assign a tier, alter a finding, change cohort counts, or determine
report inclusion.

## Supported sources

| Source | Context used by Coyote3 |
| --- | --- |
| COSMIC | Exact or bounded finding matches, tumour classifications, Cancer Gene Census, hallmarks, resistance, structural context, and actionability when the corresponding products are installed. |
| CIViC | Local gene and variant evidence. |
| BRCA Exchange | Coordinate evidence for applicable BRCA findings. |
| IARC/NCI TP53 | Local TP53 variant evidence. |
| Human Protein Atlas | Transcript-level tissue expression context. |
| OncoKB | Local cancer-gene and historical actionable records, a maintained public cache, and an explicit public detail lookup. |
| ClinPGx | Local gene markers and an explicit public detail lookup. |

The installed datasets determine which sections are available. The COSMIC card
reports missing type-specific managed products as not configured when their
release is absent or their active collection is empty. Other source sections
either report that no local evidence is available or are omitted. None of these
states is negative evidence for the finding.

## Collection ownership

All collections in this reference are stored in `KNOWLEDGEBASE_DB`. The
application accesses them through repositories and never joins them by a sample
identifier. `oncokb_public` must not contain sample names, sample identifiers,
or patient data.

`hgnc_genes` remains in `COYOTE3_DB`. It is the authoritative gene identity and
transcript reference used to normalize approved, previous, and alias symbols
before knowledgebase lookup; it is not an external knowledgebase collection.

### Shared and non-COSMIC collections

| Collection | Current use | Where it is shown | Deployment priority |
| --- | --- | --- | --- |
| `versions` | Active release, publication time, collection, and record-count provenance for managed snapshots. COSMIC availability checks require an active manifest as well as a non-empty product collection. | About-page release inventory and not-configured states. | Core for managed knowledgebase releases. |
| `civic_variants` | Matches small variants by genomic allele, gene plus HGVSc, or gene plus variant description. | Small-variant knowledgebase evidence. | Recommended for oncology review when a current CIViC snapshot is maintained. |
| `civic_genes` | Matches an approved gene symbol to CIViC gene metadata. | Small-variant details, Gene Information, and Gene Cohort Explorer. | Recommended with `civic_variants`. |
| `brcaexchange` | Matches exact GRCh37 or GRCh38 alleles for BRCA1/BRCA2 findings. | Applicable small-variant details. | Analysis-specific; recommended for BRCA testing. |
| `iarc_tp53` | Matches TP53 by selected HGVSc. | Applicable small-variant details. | Analysis-specific; recommended where TP53 interpretation is in scope. |
| `hpaexpr` | Matches selected transcript identifiers to tissue expression values. | Small-variant transcript expression section. | Optional supporting context. |
| `oncokb_cancer_genes_public` | HGNC-normalized public cancer-gene markers and aliases. | `OKB` table markers, finding details, Gene Information, and Gene Cohort Explorer. | Recommended general OncoKB baseline. |
| `oncokb_genes_public` | HGNC-normalized public curated-gene summaries and highest public level fields. | Small-variant details and gene-level knowledgebase context. | Recommended with the public cancer-gene cache. |
| `clinpgx_genes_public` | Gene identity, VIP, annotation, and CPIC-guideline flags by symbol or alias. | `PGx` table markers, small-variant details, and gene-level knowledgebase context. | Analysis-specific; recommended for pharmacogenomics workflows. |
| `oncokb` | Historical local alteration annotations matched by gene and protein alteration. | Small-variant details. | Retain only when the center has a valid, understood source and license. |
| `oncokb_actionable` | Historical local drug/actionability rows matched by gene and alteration. | `Rx` markers, small-variant details, and gene-level context. | Optional historical evidence; not a replacement for current licensed therapeutic data. |
| `oncokb_genes` | Historical local gene records and fallback gene metadata. | Gene-level context and a fallback when the maintained public cache has no record. | Optional legacy reference. Prefer maintained public caches for new deployments. |
| `oncokb_public` | Stores de-duplicated public variant-query responses by query hash. No current clinical page reads this collection as evidence. On-demand detail lookup calls the public API directly. | No current clinical UI consumer. | Optional infrastructure; do not load sample-linked records. |

The public OncoKB gene refresh populates `oncokb_cancer_genes_public` and
`oncokb_genes_public` from the public gene catalogues after HGNC resolution. It
does not populate therapeutic evidence. The ClinPGx gene cache provides fast
local markers; the explicit detail action can request richer public ClinPGx
context without writing sample data into a knowledgebase collection.

### COSMIC collections used by current views

| Collection | Lookup and contribution | Where it is shown | Deployment priority |
| --- | --- | --- | --- |
| `cosmic_cancer_gene_census` | Gene symbol to tier, role, mutation types, tumour scope, and somatic/germline status. | Knowledgebase Details aggregate chart; `CGC` markers on every finding table; all applicable finding details; Gene Information; Gene Cohort Explorer. | Highest-value general COSMIC collection. |
| `cosmic_cgc_hallmarks` | Gene symbol to curated hallmark descriptions and publications. | Optional Knowledgebase Details hallmark summary; finding details and gene-level context. | Recommended companion to Cancer Gene Census. |
| `cosmic_mutation_census` | Exact GRCh38 allele or COSV identifier to driver tier, disease, ClinVar, and tested/mutated counts. | Small-variant COSMIC evidence. | Recommended small-variant baseline. |
| `cosmic_targeted_variants` | Exact chromosome, position, reference, alternate, or COSV identifier. | Small-variant COSMIC evidence. | Recommended for targeted-panel review. |
| `cosmic_census_gene_mutations` | Exact Census-gene allele or COSV identifier with mutation and phenotype references. | Small-variant COSMIC evidence. | Recommended small-variant companion. |
| `cosmic_classifications` | Resolves phenotype identifiers from matched records to primary site, histology, and subtype. | Tumour-classification table in applicable finding details. | Recommended enrichment with mutation, CNA, fusion, or breakpoint products. |
| `cosmic_copy_number` | Overlapping reported interval plus affected genes; matching records are grouped into observation counts. | CNV details. | Recommended when CNV analysis is enabled. |
| `cosmic_fusions` | Exact partner pair in either orientation. | Fusion details. | Recommended when fusion analysis is enabled. |
| `cosmic_breakpoints` | Overlaps either reported translocation breakend. | Translocation matched-record evidence. | Recommended when translocation analysis is enabled. |
| `cosmic_structural_variants` | Joins matched breakpoint records by `cosmic_structural_id` to descriptions, mutation type, coordinates, phenotype, and publication. | Translocation structural context. | Recommended companion to breakpoints. |
| `cosmic_actionability` | Matches normalized gene or gene-pair membership to disease, drug, trial, rank, and outcome context. | Small-variant, CNV, fusion, and translocation details when matching rows exist. | Optional, high-value context when licensed; gene-level matching is broader than exact variant evidence. |
| `cosmic_resistance_mutations` | Matches COSV identifiers to curated drug-response records. | Small-variant details. | Optional specialized therapeutic context. |
| `cosmic` | Exact genome-screen coding allele or COSV identifier. | Small-variant matched records. | Optional and storage-heavy; the recommended baseline above usually provides more focused evidence. |
| `cosmic_noncoding_variants` | Exact non-coding allele or COSV identifier. | Small-variant matched records. | Optional and storage-heavy; load only when non-coding interpretation is in scope. |

COSMIC query responses are bounded and projected. Source sample identifiers and
case-level phenotype identifiers are not returned to the browser.

### Supported imports without a current clinical reader

| Collection | Retained purpose | Current status |
| --- | --- | --- |
| `cosmic_gene_expression` | Raw COSMIC expression product for a future validated aggregate by gene and cancer type. | Not queried by current pages; do not confuse it with `hpaexpr` or sample `rna_expression`. |
| `cosmic_methylation` | Differential methylation source product. | Not queried by current finding pages. |
| `cosmic_classification_papers` | Paper-specific phenotype hierarchy. | Imported and versioned, but current phenotype resolution uses `cosmic_classifications`. |
| `cosmic_genes` | COSMIC gene identifier mapping. | Imported and versioned; no current runtime join. |
| `cosmic_transcripts` | COSMIC transcript-to-gene mapping. | Imported and versioned; no current runtime join. |
| `cosmic_signature_sbs` | SBS96 reference signature profiles. | Not shown until a sample-level signature interpretation workflow is implemented. |
| `cosmic_signature_dbs` | DBS78 reference signature profiles. | Not shown until a sample-level signature interpretation workflow is implemented. |
| `cosmic_signature_sv` | SV32 reference signature profiles. | Not shown until a sample-level signature interpretation workflow is implemented. |

These importers remain supported so centers can retain licensed source products
for future workflows. Installing them does not make data appear in the current
clinical interface. They should be omitted when the center has no defined use,
especially when storage cost is material.

## Finding tables

Small-variant, CNV, fusion, and translocation tables receive page-bounded
knowledgebase marker maps from the API. Markers are displayed in the status
column rather than changing the source gene label.

| Marker | Meaning |
| --- | --- |
| `OKB` | The gene is present in the installed OncoKB public cancer-gene cache. |
| `Rx` | Historical local OncoKB actionable evidence is available. |
| `PGx` | The gene is present in the installed ClinPGx gene cache. |
| `CGC` | At least one involved gene is present in the installed COSMIC Cancer Gene Census. |

The public assay catalog and matrix use the same source-membership principle.
Their gene rows may show `OncoKB`, `CGC`, `CIViC`, and `PGx` tags. The catalog
API resolves these markers in batches for the visible genes; the browser does
not make a separate knowledgebase request for every row.

The marker tooltip identifies the matched gene or source. A marker is a lookup
signal, not a clinical classification. Fusion and translocation markers may
represent either partner; CNV markers may represent any displayed affected
gene.

## Finding detail pages

The knowledgebase area is available for small variants, CNVs, fusions, and
translocations. Source sections are expanded initially and flow into responsive
columns according to their rendered height, so a short or empty section does
not reserve a fixed row beside a longer section. Each source uses its own logo
and restrained surface treatment; colors do not encode clinical conclusions.

The search field filters all loaded knowledgebase sections and their evidence
rows. It searches the evidence payload already returned for the finding; it
does not run another database query. Evidence tables show the first 10 rows
initially. **Show all** reveals every row in that response, and **Show first
10** restores the compact view. COSMIC repository responses are bounded before
they reach the browser.

Finding-specific matches are distinguished from broader gene-level context.
For example, COSMIC can label an exact small-variant allele, an overlapping CNV
interval and gene, an exact fusion pair, or a breakpoint overlap. Cancer Gene
Census and hallmark records describe an involved gene and must not be read as
proof that the specific finding is pathogenic or actionable.

Long values wrap or use an explicit expansion control. Multi-value fields such
as actionability diseases and drugs are separated into neutral badges for
readability. Semantic colors are reserved for values with defined meaning,
including tier, somatic or germline scope, and copy-number gain or loss.

Small-variant COSMIC, dbSNP, and PubMed identifiers stored on the finding are
shown as linked identifier groups under **External Evidence**. These identifiers
come from the ingested variant record and remain separate from live or local
knowledgebase query results.

## Gene pages and cohort review

The Gene Information page and Gene Cohort Explorer use the same HGNC-normalized
gene knowledgebase response. The summary shows available source families and
bounded gene-level facts, including COSMIC Cancer Gene Census tier, role,
somatic or germline scope, mutation types, and hallmarks.

Sample prevalence, recurrent findings, and tier distributions continue to come
only from access-controlled Coyote3 sample and report data. Knowledgebase data
does not add samples or reported findings to those calculations. Finding-level
actionability remains on finding detail pages.

## Release visibility

The About page and Knowledgebase Details release inventory show installed
knowledgebase products in a compact table with release identifiers, record
totals, publication times, and configured remote services. It reads the
dedicated knowledgebase version catalog and exposes no
source paths, checksums, credentials, sample identifiers, or patient data. The
dashboard shows only one compact availability entry per source family. Detailed
Cancer Gene Census aggregates are confined to Knowledgebase Details and appear
only when that collection is populated.

Knowledgebase Details also reports non-clinical aggregate coverage from local
OncoKB, ClinPGx, CIViC, and HPA collections. OncoKB gene-type slices are
mutually exclusive. ClinPGx uses separate rings for overlapping capabilities,
including VIP status, CPIC dosing guidance, and variant annotations. A missing
or empty source is omitted rather than represented as zero coverage.

For dataset acquisition, import, version publication, optional products, and
rollback, see [Knowledgebase snapshot updates](../operations/knowledgebase_updates.md).
For the database ownership boundary, see
[Application architecture](../architecture/current_application_context.md#collection-mapping).
