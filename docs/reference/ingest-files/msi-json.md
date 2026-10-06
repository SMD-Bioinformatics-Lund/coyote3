# MSI: JSON measurement

Manifest key: `msi`. Analysis type: `MSI`. Stored collection: `biomarkers`.

## Raw structure

[Download the synthetic JSON](../../assets/examples/ingest/msi.json).

```json
{
  "name": "SYNTHETIC-T",
  "MSIS": {
    "tot": 100,
    "som": 0,
    "per": 0.0
  },
  "MSIP": {
    "tot": 100,
    "som": 1,
    "per": 1.0
  }
}
```

The root is an object with a nonempty producer sample label in `name` and the
measurement fields shown above. Ingest supplies `SAMPLE_ID`; do not include database
identifiers or review state. Independently submitted measurement files for one
sample must agree on `name`.

## Measurement fields

Supply at least one of `MSIS` (single-sample) and `MSIP` (paired). Each supplied
object requires integer `tot` and `som` counts and numeric `per`. `per` is the
producer-reported percentage, not a fraction; it is not recomputed from counts.
The two methods remain separate measurements in clinical rule collections.
An MSI update replaces the complete supplied method set.

A numeric zero is a measured result. Omit the file when this analysis is unavailable;
do not fabricate zero values or submit an empty measurement object. Missing optional
expected files are recorded separately from successful measurements. Required files
must be readable, and all readable inputs must pass parsing and schema validation.

The parser selects only MSI fields from this file. An update preserves other
analyses in the same stored document. Review and reporting are governed independently
by the sample's ASPC analysis types and report sections.

See [measurement analysis behavior](../measurement-analyses.md),
[bundle preparation](README.md), and [collection contracts](../mongodb-collections.md).
