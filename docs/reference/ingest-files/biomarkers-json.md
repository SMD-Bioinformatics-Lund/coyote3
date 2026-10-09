# Biomarker measurement JSON

The DNA manifest uses one `biomarkers` key for a JSON file containing HRD, MSI,
and/or TMB measurements. HRD, MSI, and TMB remain independent analysis selections.
Their validated fields are stored together in the `biomarkers` collection and
linked to the parent sample by `SAMPLE_ID`.

## Input contracts

| Analysis | Manifest key | Raw contract |
| --- | --- | --- |
| HRD | `biomarkers` | [HRD score and components](hrd-json.md) |
| MSI | `biomarkers` | [Single and paired MSI measurements](msi-json.md) |
| TMB | `biomarkers` | [Tumor mutational burden](tmb-json.md) |

```yaml
biomarkers: /ingest/SYNTHETIC-T.biomarkers.json
```

The JSON root is an object with a nonempty `name` and at least one non-null
measurement: `HRD`, `MSIS`, `MSIP`, or `TMB`. Each supplied measurement must satisfy
its linked raw contract. The [combined synthetic example](../../assets/examples/ingest/biomarkers.json)
contains HRD and MSI. A producer can add the supported `TMB` object to the same
file without adding another manifest key. Separate `hrd`, `msi`, and `tmb` manifest
keys are not accepted.

Only supplied measurements are available: an HRD/MSI file does not supply TMB.
Zero is a valid measured value. An omitted or null measurement is not a zero result.
The ASP lists `biomarkers` once in `expected_files` and, when necessary, in
`required_files`. This requires the shared input file, not every measurement type.
The ASPC independently selects `HRD`, `MSI`, and/or `TMB` for review and reporting.

Updates replace supplied analyses and preserve omitted analyses. Supplying MSI
replaces its method set (`MSIS`/`MSIP`); an omitted method within that set is removed.
The source `name` must remain consistent with the stored measurement record.

See [measurement analysis behavior](../measurement-analyses.md) for review,
clinical-rule facts, report selection, and update behavior.
