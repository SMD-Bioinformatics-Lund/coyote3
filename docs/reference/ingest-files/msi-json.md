# MSI: JSON measurement

Manifest key: `biomarkers` (shared measurement file). Analysis type: `MSI`. Stored collection: `biomarkers`.

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

## Field requirements and defaults

| Field | Meaning / type | Required | When omitted |
| --- | --- | --- | --- |
| `name` | Nonempty producer sample label | Yes | None |
| `MSIS` | Single-sample measurement object | At least one of MSIS/MSIP | Absent method remains unavailable |
| `MSIP` | Paired measurement object | At least one of MSIS/MSIP | Absent method remains unavailable |
| `*.tot` | Integer total count | In each supplied method | None |
| `*.som` | Integer somatic count | In each supplied method | None |
| `*.per` | Producer percentage, not a 0–1 fraction | In each supplied method | None; not calculated from counts |

## Measurement fields

Supply at least one of `MSIS` (single-sample) and `MSIP` (paired). Each supplied
object requires integer `tot` and `som` counts and numeric `per`. `per` is the
producer-reported percentage, not a fraction; it is not recomputed from counts.
The two methods remain separate measurements in clinical rule collections.
An MSI update replaces the complete supplied method set.

A numeric zero is a measured result. Omit this measurement when the analysis is unavailable;
do not fabricate zero values or submit an empty measurement object. Missing optional
expected files are recorded separately from successful measurements. Required files
must be readable, and all readable inputs must pass parsing and schema validation.

The shared file can also contain other supported measurements. The parser retains
all supplied analyses; an update preserves analyses omitted from the file. Review and reporting are governed independently
by the sample's ASPC analysis types and report sections.

See [measurement analysis behavior](../measurement-analyses.md),
[bundle preparation](README.md), and [collection contracts](../mongodb-collections.md).
