# Knowledgebase Snapshot Updates

BRCA Exchange, CIViC, the NCI TP53 Database, and COSMIC are maintained outside
Coyote3. Their local collections are full snapshots used for fast, reproducible
clinical lookup. Updates are deliberate operator actions; the application does
not download or replace these datasets automatically.

## Release management model

Each upstream release replaces the complete active collection for that source.
Do not update rows in place. Upstream curators can remove records, correct
identifiers, or change classifications, and an upsert-only process would retain
records that no longer belong to the release.

The update commands use the following publication sequence:

1. Calculate the name, size, and SHA-256 digest of every supplied file.
2. Parse the complete source and reject malformed or empty datasets.
3. Stream documents to a private staging collection in batches.
4. Build lookup and uniqueness indexes on the staging collection.
5. Verify the inserted count.
6. Rename the current collection to a temporary previous-version collection.
7. Rename the verified staging collection to the stable application name.
8. Record the active release in the knowledgebase database's `versions`
   collection.

The API always reads the stable collection name. It never queries a partially
loaded collection. If publication fails, the command restores every collection
that it already replaced and marks the release manifest as failed.

By default, the previous physical collection remains under a name beginning
with `__kb_previous__`. This provides immediate rollback but temporarily uses
space for both releases and both index sets. `--drop-previous` removes that
temporary collection only after the complete update succeeds. It does not
remove the small release manifest.

> **Warning: Capacity and backups**
>
> Safe replacement requires enough free MongoDB storage for the active
> collection, staging collection, and staging indexes at the same time. For a
> very large dataset, take and verify an external MongoDB backup first, use
> `--drop-previous`, and monitor free space throughout the import. If the volume
> cannot hold both snapshots temporarily, build the new knowledgebase database
> on another adequately sized volume and switch `KNOWLEDGEBASE_DB` during a
> controlled deployment. Do not delete the active collection before validation.

## Standard command sequence

Every command is a dry run unless `--apply` is present. The dry run reads and
validates the complete input but does not connect to MongoDB.

Use `--cpus N` to permit `N` concurrent validation or MongoDB batch workers.
Publication uses bounded concurrent inserts and submits each collection's index
set in one MongoDB operation. Start conservatively, monitor MongoDB CPU, memory,
disk latency, and replication lag, and increase the value only when the server
has capacity. A value of `1` is the default.

A compressed archive member is one sequential decompression stream. `--cpus`
does not split that stream; it accelerates independent file or collection work
and the MongoDB insertion stage. It does not bypass full validation, count
verification, or staged publication.

```bash
export MONGO_URI='mongodb://...'
export KNOWLEDGEBASE_DB='coyote3_knowledgebase'
```

1. Stop API and worker processes that use the affected collection.
2. Back up the knowledgebase database.
3. Run the updater without `--apply` and review its counts and file digests.
4. Run the same command with `--apply`.
5. Start the application and verify representative positive and negative
   lookups.
6. Drop a retained previous collection only after acceptance, or use
   `--drop-previous` when an external rollback copy is already available.

Reports contain file provenance and counts but no source records:

```bash
--report knowledgebase-update.json
```

## BRCA Exchange

BRCA Exchange publishes integrated BRCA1 and BRCA2 variant snapshots and
normally issues monthly releases. Download the complete TSV from the official
[BRCA Exchange releases page](https://brcaexchange.org/releases). The importer
stores normalized GRCh37 and GRCh38 identities for lookup and preserves all
non-empty upstream columns in `source_record`.

Required input:

- one complete BRCA Exchange TSV, not a filtered search result;
- a release identifier taken from the release date or release metadata.

```bash
PYTHONPATH=. .venv/bin/python scripts/update_brca_exchange.py \
  --input /path/to/brca_exchange_release.tsv \
  --release 2026-09-03 \
  --cpus 8
```

After reviewing the dry run, repeat with `--apply`. The command replaces
`brcaexchange` and indexes the BRCA Exchange identifier, both genome builds,
and gene symbol.

## CIViC

CIViC provides nightly snapshots and historical monthly releases in TSV and
VCF formats, as described in the official
[CIViC data-release documentation](https://docs.civicdb.org/en/latest/using/data_releases.html).
Use a monthly release for a reproducible clinical deployment. Download both
the Feature Summaries TSV and Variant Summaries TSV from the same release. Do
not combine a historical variant file with a feature file downloaded on a
different day.

The feature file contains top-level CIViC genes, fusions, and factors. Coyote3
imports Gene rows into `civic_genes`. The variant file contains variants linked
to all feature types and is imported into `civic_variants`, including fusion
partners and current CIViC v2 feature identifiers.

```bash
PYTHONPATH=. .venv/bin/python scripts/update_civic.py \
  --features /path/to/FeatureSummaries.tsv \
  --variants /path/to/VariantSummaries.tsv \
  --release 2026-09-01 \
  --cpus 4
```

The two collections are staged and published as one release. A failure in
either collection prevents the release from remaining partially active.

## NCI TP53 Database

The former IARC TP53 Database is maintained by the US National Cancer Institute.
The official [TP53 dataset download page](https://tp53.cancer.gov/get_tp53data)
provides several independent datasets. Coyote3's `iarc_tp53` detail card uses
the **Functional/structural data in TP53 with their annotations** file. For R21,
the user manual identifies this file as `MutationView_r21.csv`; despite the
extension, the published file is tab-delimited.

Download the functional/structural variant file, not the tumor case or germline
family files. The latter contain person- and sample-level research records and
are neither needed nor accepted by this updater. The TP53 site states that the
data are freely accessible with acknowledgment, while direct or indirect
monetization is prohibited; review the current site terms before operational
use.

```bash
PYTHONPATH=. .venv/bin/python scripts/update_tp53_database.py \
  --input /path/to/MutationView_r21.csv \
  --release R21 \
  --cpus 4
```

The normalized document is keyed by `MUT_ID` and canonical cDNA description.
Missing occurrence counts remain absent; they are never stored as zero.

## COSMIC

COSMIC is a licensed product family rather than one flat database. Use the
official [COSMIC download portal](https://cancer.sanger.ac.uk/cosmic/download/cosmic)
and select the required release, genome build, and product. Browser downloads
are tar archives containing compressed data and a product-specific README. The
updater reads the archive directly and does not extract multi-gigabyte files to
disk.

COSMIC describes registered **Non-Commercial** access and separately licensed
**Commercial** access. Non-commercial users must register and accept the
current terms. Commercial users must obtain access through QIAGEN. Clinical
service use can fall outside the non-commercial permission even at an academic
or public institution, so the operating center must obtain a licensing
determination before downloading, importing, displaying, or redistributing the
data. Never commit COSMIC files, derived collections, credentials, or reports
containing licensed records to this repository.

One invocation replaces one product. This keeps storage, validation, rollback,
and product-specific versioning independent:

```bash
PYTHONPATH=. .venv/bin/python scripts/update_cosmic.py \
  --directory /path/to/cosmic-release \
  --assembly GRCh38 \
  --product classifications \
  --release 104 \
  --cpus 8
```

Supported products:

| `--product` | Official archive content | Active collection |
| --- | --- | --- |
| `coding_variants` | Normalized genome-screen coding mutation VCF | `cosmic` |
| `noncoding_variants` | Normalized non-coding mutation VCF | `cosmic_noncoding_variants` |
| `targeted_variants` | Normalized targeted-screen coding mutation VCF | `cosmic_targeted_variants` |
| `breakpoints` | Breakpoint-level structural records | `cosmic_breakpoints` |
| `structural_variants` | Structural variant descriptions and intervals | `cosmic_structural_variants` |
| `copy_number` | Complete gene-level CNA records | `cosmic_copy_number` |
| `fusions` | Tested samples with detected or undetected fusions | `cosmic_fusions` |
| `gene_expression` | TCGA level 3 expression calls and z-scores | `cosmic_gene_expression` |
| `methylation` | Differential methylation probes and beta values | `cosmic_methylation` |
| `classifications` | COSMIC phenotype identifiers, sites, and histologies | `cosmic_classifications` |
| `classification_papers` | Paper-specific COSMIC phenotype hierarchy | `cosmic_classification_papers` |
| `cancer_gene_census` | Cancer genes, evidence tier, roles, and tumour associations | `cosmic_cancer_gene_census` |
| `cgc_hallmarks` | Cancer Gene Census hallmark evidence | `cosmic_cgc_hallmarks` |
| `genes` | COSMIC gene identifier and HGNC/Entrez mapping | `cosmic_genes` |
| `transcripts` | COSMIC transcript-to-gene mapping | `cosmic_transcripts` |
| `census_gene_mutations` | Coding mutation observations restricted to Census genes | `cosmic_census_gene_mutations` |
| `resistance_mutations` | Curated drug-response mutation evidence | `cosmic_resistance_mutations` |
| `mutation_census` | Coding mutation driver likelihood and population evidence | `cosmic_mutation_census` |
| `actionability` | Mutation, disease, drug, trial, and outcome relationships | `cosmic_actionability` |
| `signature_sbs` | SBS96 signature probability matrix | `cosmic_signature_sbs` |
| `signature_dbs` | DBS78 signature probability matrix | `cosmic_signature_dbs` |
| `signature_sv` | SV32 signature probability matrix | `cosmic_signature_sv` |

Each command validates or replaces exactly one product. Products are optional and
can be updated on separate schedules. A missing or empty product remains absent;
the updater does not create placeholder records. Finding detail pages identify
each applicable absent product as **Not configured**, which is distinct from a
configured product having no match for the current finding.

TSV imports retain every non-empty upstream column under a stable snake-case
field name. VCF imports retain the complete `QUAL`, `FILTER`, `INFO`, `FORMAT`,
and sample-column content in addition to normalized fields used by indexes.
Repositories expose only bounded clinical evidence projections; upstream COSMIC
sample names and identifiers are never returned to the browser.

The complete genome-screen coding, non-coding, and differential methylation
products are storage-heavy optional imports. The recommended clinical baseline
uses Cancer Mutation Census, Census Genes Mutations, and Targeted Screens for
small-variant evidence and does not load these three large products. Import them
only when the center's analysis scope requires the additional evidence.

The updater retains explicit `coding_variants`, `noncoding_variants`, and
`methylation` commands and creates their indexes only when that product is
imported. Runtime initialization does not create an empty `cosmic` collection.
Exact small-variant lookup reads `cosmic` and `cosmic_noncoding_variants` when
present. Methylation rows are not attached to SNV, CNV, fusion, or translocation
cards because a shared gene symbol is not finding-level evidence.

The signature commands transpose each published matrix into one document per
signature. The `profile` object retains every mutation type and probability from
the source matrix. Signatures are reference profiles for sample-level signature
analysis and are not matched to individual finding cards.

### Detail-page lookups

COSMIC collections supply evidence to finding detail pages. A page queries only
the products relevant to its finding type:

| Collection | Small variant | CNV | Fusion | Translocation | Lookup |
| --- | :---: | :---: | :---: | :---: | --- |
| `cosmic_mutation_census` | Yes |  |  |  | GRCh38 genomic identity or COSV identifier; driver tier and aggregate coding evidence |
| `cosmic_targeted_variants` | Yes |  |  |  | Exact chromosome, position, reference, and alternate allele |
| `cosmic_census_gene_mutations` | Yes |  |  |  | Exact Census-gene mutation identity and curated source evidence |
| `cosmic` | Yes |  |  |  | Optional genome-screen mutation evidence |
| `cosmic_noncoding_variants` | Yes |  |  |  | Optional non-coding evidence using exact genomic identity |
| `cosmic_copy_number` |  | Yes |  |  | Reported genomic interval and affected gene symbols; results are grouped into observation counts |
| `cosmic_fusions` |  |  | Yes |  | Exact gene pair in both orientations |
| `cosmic_breakpoints` |  |  |  | Yes | Reported breakends against bounded COSMIC breakpoint ranges |
| `cosmic_classifications` | Yes | Yes | Yes | Yes | Phenotype identifiers from matched records resolve to primary site, histology, and subtype |
| `cosmic_cgc_hallmarks` | Yes | Yes | Yes | When genes are available | Indexed gene symbol |
| `cosmic_cancer_gene_census` | Yes | Yes | Yes | When genes are available | Indexed gene symbol |
| `cosmic_resistance_mutations` | Yes |  |  |  | COSV identifier |
| `cosmic_actionability` | Yes |  | Yes |  | COSMIC mutation or fusion identifier |

All managed genomic, interval, partner, and identifier lookups use the indexes
created by the updater. Result sets are bounded and use restricted projections. CNV
queries require the reported interval before aggregation; they do not aggregate
the complete CNA collection by gene alone.

Every query has a result limit and returns a restricted projection. COSMIC sample
identifiers, sample names, and phenotype case identifiers are not included in API
responses. The COSMIC evidence shown in a knowledgebase card is independent of the
`cosmic_ids`, `dbsnp_id`, and `pubmed_ids` stored on a Coyote3 small-variant record;
those source identifiers are displayed separately on the variant detail page.

#### Products not presented on detail pages

The following managed collections are retained as source datasets but are not
read by a finding knowledgebase card:

| Collection | Intended role |
| --- | --- |
| `cosmic_structural_variants` | Structural descriptions and phenotype references that can enrich breakpoint matches by `cosmic_structural_id` |
| `cosmic_gene_expression` | Large sample-level expression dataset; it must be aggregated by gene and cancer type before any UI use |

These collections are not interchangeable with variant evidence. Methylation and
gene-expression rows must not be attached to a finding merely because they share
a gene symbol. Raw COSMIC expression rows and their source sample identifiers must
never be returned to the browser.

### Search and cohort use

Tiered finding search remains focused on report and finding identity and does not
add knowledgebase columns. This keeps the cross-sample result table compact.

Gene Cohort Explorer and the Gene Information page use the same gene-level
knowledgebase response for the exact approved HGNC symbol. The summary identifies
available sources and presents bounded COSMIC Cancer Gene Census roles, tiers,
mutation types, and hallmark context. Sample prevalence and tier counts still
come only from access-scoped Coyote3 reports; external knowledgebases never alter
those clinical counts.

The About page and dashboard read active releases from the knowledgebase
`versions` collection. Only source name, release, publication time, collection
names, and record counts leave the repository; importer paths, file manifests,
and checksums are not exposed by the public status endpoint.

#### Recommended evidence enrichment

The most useful extension for structural findings is to join a bounded
`cosmic_breakpoints` result to `cosmic_structural_variants` by
`cosmic_structural_id`. The card can then present the structural description,
mutation type, study, phenotype reference, and publication without exposing a
COSMIC sample record.

`cosmic_classifications` is used as a lookup table, not as independent evidence.
The detail response resolves `cosmic_phenotype_id` values from matched mutation,
CNA, fusion, breakpoint, and structural records to primary site, histology, and
subtype. Case-level classification rows are not returned.

Actionability mutation expressions are normalized to an indexed `genes` array at
import. Finding pages use that index to show bounded gene-level or gene-pair trial
context, including the original mutation selection, disease, drug or combination,
evidence rank, status, and outcome. This is broader context rather than an exact
variant assertion; the original mutation expression remains visible in the card.

The complete Cancer Gene Census adds gene tier, oncogene or tumor-suppressor
role, fusion-gene role, somatic or germline involvement, associated tumor types,
and supporting publications. `cosmic_cgc_hallmarks` contains only the hallmark
portion and is not a substitute for the complete census. The Cancer Mutation
Census supplies coding small-variant driver and population evidence and includes
both GRCh37 and GRCh38 genomic positions in its GRCh37 distribution. See the
official [COSMIC modules](https://www.cosmickb.org/knowledgebase/cosmic-modules/)
for the distinctions between Core COSMIC, Gene Census, Mutation Census,
signatures, resistance, and Actionability.

Mutational signatures belong to sample-level profile interpretation rather than
an individual finding card. COSMIC drug-resistance data can complement
Actionability after a separate identifier and disease-context mapping is defined.

The coding, non-coding, and targeted commands deliberately select normalized VCF
archives. Do not import normalized and unnormalized forms of the same product.
Cancer Mutation Census and Census Genes Mutations are separate products with
different evidence scopes; their records remain in separate collections.

Actionability has its own release cycle and must use its own version. For
example, COSMIC core v104 can coexist with Actionability v21:

```bash
PYTHONPATH=. .venv/bin/python scripts/update_cosmic.py \
  --directory /path/to/cosmic-release \
  --assembly GRCh37 \
  --product actionability \
  --release 21 \
  --cpus 8
```

Cancer Mutation Census, core COSMIC, Actionability, and signatures can reside in
different source directories. Run the same updater once for each selected file:

```bash
PYTHONPATH=. .venv/bin/python scripts/update_cosmic.py \
  --directory /data/cosmic/cmc-v104 \
  --assembly GRCh37 \
  --product mutation_census \
  --release 104 \
  --cpus 8 \
  --apply

PYTHONPATH=. .venv/bin/python scripts/update_cosmic.py \
  --directory /data/cosmic/signatures-v3.6 \
  --assembly GRCh38 \
  --product signature_sv \
  --release 3.6 \
  --cpus 8 \
  --apply
```

Each COSMIC product is stored as a flat, typed record optimized for its natural
lookup keys. Release, assembly, file digest, and import timestamps live once in
`versions`, avoiding repeated metadata in millions of records. This collection
is independent of `samples.database_versions`, which remains the immutable
pipeline database-version snapshot for each analyzed sample.

## Release inspection and rollback

Inspect active and retired releases without reading source records:

```javascript
db.getSiblingDB("coyote3_knowledgebase").versions.find(
  {},
  {source: 1, release: 1, status: 1, published_at: 1, collections: 1}
).sort({published_at: -1})
```

Previous physical collections are intentionally not selected by runtime
configuration. Rollback is an operator procedure: stop writers, rename the
current collection aside, rename the accepted `__kb_previous__...` collection
to the stable name, update the corresponding release states, and verify the
same representative lookups used during acceptance. Prefer restoring the
verified pre-update backup when `--drop-previous` was used.
