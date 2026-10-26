# Coyote3 v3 samples

First [export the assay in batches](../exporting.md) with `--source-version 3`.
Each batch supplies original samples and sample-owned collection files for conversion.

For variants, the shared VEP vault and embedded finding comments, use the separate
`migrate_variants.py` following the [variant procedure](../variants.md).

Run `migrate_samples.py` from the repository root. It reads `coyote3.samples` and
accepts `gmshem` or `hema_gmsv1`, one at a time. See the
[sample migration procedure](../README.md) for read-only inspection, source-bound
review and output commands. The script never writes to a database.

Next use `migrate_related.py` for [non-variant sample-related data](../related-data.md):
CNVs, translocations, biomarkers, interval or structured coverage and saved report
findings. Its sample ownership comes from the completed v3 sample bundle.

Coverage is classified by document shape; normal intervals stay in `coverage` and
structured measurements go to `d4_coverage`. Use `migrate_coverage_blacklist.py`
separately for group-scoped exclusions targeting `d4_coverage_blacklist`.
