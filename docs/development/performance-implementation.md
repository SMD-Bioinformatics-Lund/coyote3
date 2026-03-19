# Performance Implementation Guide

This guide defines the performance architecture for Mongo-heavy runtime paths in Coyote3.
It describes the implementation as a set of enforced behaviors.

## 1. Variant Identity Is Hash-First

Variant identity in `variants` is resolved by exact pair matching:

- `simple_id_hash`
- `simple_id`

The hash input is the canonical normalized `simple_id` string.
`simple_id` is retained for readability and exact collision-safe verification.

All exact-identity variant lookups are executed as:

- prefilter by `simple_id_hash`
- verify by `simple_id`

This rule applies to:

- cross-sample identity lookups
- variant identity search helpers
- variant/gene list filtering when list items contain `simple_id` values
- reported variant identity matching

## 2. Required Variant Index Strategy

The `variants` collection uses these required indexes:

- `simple_id_hash_1_simple_id_1`
- `fp_1_simple_id_hash_1_simple_id_1`
- `sample_id_1`
- `variant_class_1`
- `fp_1`

Legacy `simple_id`-only indexes are not part of runtime policy.
Migration code removes indexes that contain `simple_id` without `simple_id_hash`.

## 3. Dashboard Variant Metrics Are Materialized

Dashboard variant counters are served from materialized metrics:

- in-memory/API cache (Redis)
- persisted metric documents in Mongo collection `dashboard_metrics`

Materialized metric keys:

- `variant_rollup_v1`
- `variant_unique_quality_v1`

`dashboard/summary` reads these metrics as the source of truth for dashboard counters.
When metrics are not present or not fresh, the API recomputes and writes them back.

## 4. Metric Freshness Contract

Metric freshness is validated against current variant cardinality:

- current `estimated_document_count()` is compared with persisted source totals
- mismatch triggers immediate recomputation

This behavior guarantees that ingestion jobs that add/remove variants are reflected on the next dashboard request.

## 5. Write-Path Invalidation Contract

Variant write paths invalidate dashboard variant metrics directly in the API layer.

The handler invalidates both Redis and persisted metric documents for:

- false-positive mark/unmark (single and bulk)
- sample variant deletion paths

Invalidation target keys:

- Redis:
  - `dashboard:variant_rollup:v1`
  - `dashboard:variant_unique_quality:v1`
- Mongo `dashboard_metrics`:
  - `variant_rollup_v1`
  - `variant_unique_quality_v1`

## 6. Unique-Count Execution Rules

Unique variant counters are grouped by compound identity:

- `{ simple_id_hash, simple_id }`

Unique-count pipelines do not group by `simple_id` alone.
This preserves index alignment and stable behavior for large alleles.

## 7. Migration Enforcement

`scripts/migrate_db_identity.py` enforces variant identity policy:

- backfills `simple_id` and `simple_id_hash`
- ensures required hash-first identity index
- removes legacy `simple_id`-only indexes

This script is idempotent and is the canonical DB normalization entrypoint.

## 8. Operational Expectations

The dashboard cold path resolves through materialized counters and bounded aggregations.
Variant growth is handled through:

- hash-first identity queries
- materialized counters
- explicit invalidation and freshness checks

This design keeps dashboard latency stable while variant volume increases.

## 9. Verification Commands

Verify variant indexes:

```bash
docker exec -i coyote3_mongo_local mongosh --quiet coyote3 --eval 'printjson(db.variants.getIndexes().map(i=>i.name))'
```

Run DB identity + variant index normalization:

```bash
/home/ram/.virtualenvs/coyote3/bin/python scripts/migrate_db_identity.py \
  --mongo-uri mongodb://localhost:37017 \
  --db coyote3_dev
```

Verify dashboard timing payload:

```bash
curl -s http://localhost:8001/api/v1/dashboard/summary | jq '.dashboard_meta.timings_ms'
```

## 10. Variant Detail Latency Contract

The small-variant detail API (`/api/v1/samples/{sample_id}/small-variants/{var_id}`) resolves
cross-sample identity by querying only exact identity keys:

- `simple_id_hash`
- `simple_id`

The current sample exclusion is performed after bounded fetch, not as a Mongo `$ne` predicate.
This prevents full-range scans on `SAMPLE_ID` and keeps query planning anchored to identity indexes.

Required lookup indexes for this path:

- `ix_simple_id_hash_simple_id_lookup`
- `simple_id_hash_1_simple_id_1_sample_id_1`

## 11. Global Index Baseline

The API creates indexes at startup for all active handler surfaces:

- identity/admin collections: users, roles, permissions, schemas
- assay and gene-list collections: assay panels, assay configs, ISGL
- sample and interpretation collections: samples, variants, annotation, blacklist, reported_variants
- structural variant collections: cnvs, translocations, fusions
- RNA collections: rna_expression, rna_classification, rna_qc
- coverage collections: coverage, panel_cov, group_coverage
- external annotation collections: civic, onkokb/onkokb_actionable/onkokb_genes, brcaexchange, iarc_tp53, hgnc, cosmic
- expression and BAM collections: hpaexpr, BAM samples

This baseline is runtime-enforced by `MongoAdapter._setup_handlers()` and index creation
is idempotent.

## 12. Interpretation Query Indexing

Annotation and reported-variant read paths use dedicated compound indexes:

- `annotation`:
  - `gene_nomenclature_variant_time_created`
  - `nomenclature_variant_time_created`
  - `variant_time_created_1`
- `reported_variants`:
  - `ix_gene_simple_id_hash_simple_id`
  - `ix_time_created_desc`

These indexes bound query cost for variant context pages, tiered variant pages, and
annotation timeline reads.
