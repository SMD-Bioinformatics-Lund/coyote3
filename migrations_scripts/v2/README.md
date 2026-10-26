# Coyote v2 samples

First [export the assay in batches](../exporting.md) with `--source-version 2`.
Each batch supplies original samples and sample-owned collection files for conversion.

Run `migrate_samples.py` from the repository root. It reads `coyote.samples` and
handles the v2 assays listed in the [sample migration procedure](../README.md).
Use `inspect` for read-only random structures, then `prepare` for one reviewed assay.
The script writes current MongoDB import files and never writes to a database.

Next use `migrate_related.py`, one collection at a time, for the separate
[non-variant sample-related data](../related-data.md). It handles both v2 CNV
collections, translocations, biomarkers, fusions and interval coverage.

Use `migrate_variants.py` separately for `variants` and `variants_idref`, the shared
VEP vault and embedded finding comments. Follow the
[variant preparation and import procedure](../variants.md).
