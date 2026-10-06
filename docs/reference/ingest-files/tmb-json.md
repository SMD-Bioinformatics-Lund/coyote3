# TMB: JSON measurement

Manifest key: `tmb`. Analysis type: `TMB`. Stored collection: `biomarkers`.

## Raw structure

[Download the synthetic JSON](../../assets/examples/ingest/tmb.json).

```json
{
  "name": "SYNTHETIC-T",
  "TMB": {
    "value": 12.4,
    "unit": "mut/Mb"
  }
}
```

The root is an object with a nonempty producer sample label in `name` and the
measurement fields shown above. Ingest supplies `SAMPLE_ID`; do not include database
identifiers or review state. Independently submitted measurement files for one
sample must agree on `name`.

## Measurement fields

`TMB.value` is a finite, nonnegative number in mutations per megabase.
`TMB.unit`, when supplied, must be `mut/Mb`; this is also its default.
The application does not compute burden from variant counts or assign high/low
status. Those interpretations require reviewed clinical rules.

A numeric zero is a measured result. Omit the file when this analysis is unavailable;
do not fabricate zero values or submit an empty measurement object. Missing optional
expected files are recorded separately from successful measurements. Required files
must be readable, and all readable inputs must pass parsing and schema validation.

The parser selects only TMB fields from this file. An update preserves other
analyses in the same stored document. Review and reporting are governed independently
by the sample's ASPC analysis types and report sections.

See [measurement analysis behavior](../measurement-analyses.md),
[bundle preparation](README.md), and [collection contracts](../mongodb-collections.md).
