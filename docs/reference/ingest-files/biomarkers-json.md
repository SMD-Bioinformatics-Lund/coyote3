# Biomarkers: MSI and HRD JSON

Manifest key: `biomarkers`. Stored destination: `biomarkers`.

## Before submission

The root must be one object with `name`. Omit unmeasured MSI or HRD objects. Each supplied measurement object must contain all its typed fields. `per` is a producer-reported percentage, not a fraction. HRD sum validation currently checks `tai + hrd + lst` only when all three components are nonzero; producers should verify the sum for every result.

[Download the complete synthetic JSON](../../assets/examples/ingest/biomarkers.json). All example identifiers and values are synthetic.
Ingest assigns `SAMPLE_ID` from the parent sample. Do not supply database IDs or review
state in pipeline files. The file must also satisfy the assay's required/expected file policy.

## Raw structure and fields

```json
{
  "name": "SYNTHETIC-T",
  "MSIS": {
    "tot": 100,
    "som": 4,
    "per": 4.0
  },
  "MSIP": {
    "tot": 200,
    "som": 6,
    "per": 3.0
  },
  "HRD": {
    "tai": 2,
    "hrd": 3,
    "lst": 4,
    "sum": 9
  }
}
```

| Key | Description and mapping to `biomarkers` |
| --- | --- |
| `name` | Required producer sample label; separate from injected `SAMPLE_ID` |
| `MSIS`, `MSIP` | Optional MSI measurement objects; preserve these exact source labels |
| `MSIS.tot`, `MSIP.tot` | Total evaluated count, integer |
| `MSIS.som`, `MSIP.som` | Producer-reported somatic/unstable count, integer |
| `MSIS.per`, `MSIP.per` | Producer-reported percentage, number; not recomputed from counts |
| `HRD.tai` | Producer TAI score/count |
| `HRD.hrd` | Producer HRD component |
| `HRD.lst` | Producer LST component |
| `HRD.sum` | Producer aggregate; validated against the HRD contract |

Omit unavailable measurement objects. Do not invent zeros to satisfy a schema.

## Related contracts

- [Bundle preparation and file index](README.md)
- [Sample manifest](../sample-manifest.md)
- [Stored collection contracts](../mongodb-collections.md)
