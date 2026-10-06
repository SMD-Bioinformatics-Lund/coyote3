# Migrate from Coyote v2

The v2 migration reads an offline BSON snapshot of `coyote` through
`scripts/migrate_from_v2/`. Small variants come from **`variants_idref`** and CNVs
from **`cnvs_wgs`**. The older `variants` and `cnvs` collections are excluded.

Follow [Legacy clinical data migration](migration-guide.md) for the source
inventory, migration order, reconciliation format, TSV backfills, isolated target
application, and acceptance checks. The
[v2 script package](https://github.com/SMD-Bioinformatics-Lund/coyote3/blob/api/scripts/migrate_from_v2/README.md)
provides a separate command for each stage.

## V2-specific requirements

- Samples can contain top-level filter settings, checked consequence/gene-list
  maps, VCF path arrays, and embedded report references. Physical assay bindings,
  case identity, pipeline provenance, and current filter profiles require review.
- `variants_idref` can contain VEP consequences without a saved selected
  transcript. Conversion requires historical selection evidence; it does not
  choose a transcript using current rules.
- `cnvs_wgs` stores interval coordinates, ratio, probe count, and gene annotations.
  Original IDs and clinical values remain associated with the source sample.
- V2 has no D4 coverage; coverage collections are outside this migration scope.
- Shared annotations without assay/subpanel scope require reviewed scope additions.
  Current ASP, ASPC, ISGL, group, and subpanel configuration must already be installed.
- Saved reports remain historical artifacts. Missing finding snapshots, run names,
  counts, pipeline versions, and authorship are not reconstructed from current data.

`backfill_sample_metadata.py` accepts reviewed tab-separated metadata. Required
fields must be supplied before conversion; optional run names and read counts
also support a later conflict-checked patch against the isolated target.

Users and external knowledgebases are outside the clinical migration scope.

## Source schema assessment

Read [Full source schema inventory](schema-inventory.md) before conversion. Every
record and nested array element in the migration scope must be inventoried; one
example document or a small sample cannot establish a collection's schema.
