# HRD: JSON measurement

Manifest key: `hrd`. Analysis type: `HRD`. Stored collection: `biomarkers`.

## Raw structure

[Download the synthetic JSON](../../assets/examples/ingest/hrd.json).

```json
{
  "name": "SYNTHETIC-T",
  "HRD": {
    "tai": 2,
    "hrd": 3,
    "lst": 4,
    "sum": 9
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
| `HRD` | Object containing the four integer scores | Yes | None |
| `HRD.tai` | Producer TAI score | Yes | None |
| `HRD.hrd` | Producer HRD component score | Yes | None |
| `HRD.lst` | Producer LST score | Yes | None |
| `HRD.sum` | Producer combined score | Yes | None |

## Measurement fields

`HRD` requires integer `tai`, `hrd`, `lst`, and `sum` fields. These are producer
scores. The sum check requires `sum = tai + hrd + lst` when all components are
nonzero; producers must verify their aggregate even when a component is zero.
The application preserves the `hrd` component's name and does not reinterpret it
as a separate analysis. TAI and LST remain components of HRD.

A numeric zero is a measured result. Omit the file when this analysis is unavailable;
do not fabricate zero values or submit an empty measurement object. Missing optional
expected files are recorded separately from successful measurements. Required files
must be readable, and all readable inputs must pass parsing and schema validation.

The parser selects only HRD fields from this file. An update preserves other
analyses in the same stored document. Review and reporting are governed independently
by the sample's ASPC analysis types and report sections.

See [measurement analysis behavior](../measurement-analyses.md),
[bundle preparation](README.md), and [collection contracts](../mongodb-collections.md).
