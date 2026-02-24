# Complete Click Paths

This chapter gives concrete click-by-click operating paths.

## A. Process a new DNA sample to report

1. Open `/samples/live`.
2. Find sample and click sample ID.
3. You are on `/dna/sample/<sample_id>`.
4. Review filter panel and active gene filters.
5. Open sample settings from gear icon if ISGL/ad-hoc update is needed.
6. Return to DNA page and review SNVs.
7. Click a variant row to open `/dna/<sample_id>/var/<var_id>`.
8. Apply classification and comments.
9. Return to list and repeat for key variants.
10. Review CNV/translocation sections if present for assay.
11. Click report preview action (`/dna/sample/<sample_id>/preview_report`).
12. Validate content, then save (`/dna/sample/<sample_id>/report/save`).
13. Return to `/samples` and verify sample is in done/reported.

## B. Process RNA sample

1. Open `/samples/live`.
2. Click RNA sample.
3. You are on `/rna/sample/<sample_id>K=`.
4. Review fusion candidates and thresholds.
5. Open each fusion (`/rna/fusion/<fusion_id>`).
6. Mark FP where needed.
7. Add summary/sample comments.
8. Generate preview (`/rna/sample/preview_report/<sample_id>`).
9. Generate/export PDF (`/rna/sample/report/pdf/<sample_id>`).

## C. Review historical reported occurrences of a variant

1. From variant detail or list, open history link.
2. Route opens `/reported_variants/variant/<variant_id>/<tier>`.
3. Review which samples/reports contain that reported variant identity.
4. Open linked sample/report for context.

## D. Perform global annotation search

1. Open `/search/tiered_variants`.
2. Select search mode (gene/variant/etc.).
3. Enter query and optionally assay filter.
4. Include annotation text if needed.
5. Review returned annotation docs and linked samples/reports.

## E. Edit sample gene constraints

1. Open `/samples/<sample_id>/edit`.
2. Load ISGL list from available options.
3. Apply selected ISGL entries.
4. Add ad-hoc genes if case requires targeted list.
5. Verify effective genes count/list.
6. Return to DNA page and continue review.

## F. Retrieve previously saved report

1. Open `/samples/done`.
2. Find sample and report row.
3. Click report link to view: `/samples/<sample_id>/reports/<report_id>`.
4. Click download icon/link for attachment route if needed.

## G. When to use which page

- Use `/samples` for workload and navigation.
- Use `/dna/...` or `/rna/...` for interpretation actions.
- Use `/search/tiered_variants` for cross-sample annotation discovery.
- Use `/reported_variants/...` for report-time occurrence history.
- Use `/admin/...` only for governance/configuration changes.
