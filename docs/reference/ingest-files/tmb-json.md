# TMB: JSON measurement

Manifest key: `biomarkers` (shared measurement file). Analysis type: `TMB`. Stored collection: `biomarkers`.

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

## Field requirements and defaults

| Field | Meaning / type | Required | When omitted |
| --- | --- | --- | --- |
| `name` | Nonempty producer sample label | Yes | None |
| `TMB` | Measurement object | Yes | None |
| `TMB.value` | Finite nonnegative mutations per megabase | Yes | None |
| `TMB.unit` | Literal `mut/Mb` | No | `mut/Mb` |

## Measurement fields

`TMB.value` is a finite, nonnegative number in mutations per megabase.
`TMB.unit`, when supplied, must be `mut/Mb`; this is also its default.
The application does not compute burden from variant counts or assign high/low
status. Those interpretations require reviewed clinical rules.

A numeric zero is a measured result. Omit this measurement when the analysis is unavailable;
do not fabricate zero values or submit an empty measurement object. Missing optional
expected files are recorded separately from successful measurements. Required files
must be readable, and all readable inputs must pass parsing and schema validation.

The shared file can also contain other supported measurements. The parser retains
all supplied analyses; an update preserves analyses omitted from the file. Review and reporting are governed independently
by the sample's ASPC analysis types and report sections.

See [measurement analysis behavior](../measurement-analyses.md),
[bundle preparation](README.md), and [collection contracts](../mongodb-collections.md).
