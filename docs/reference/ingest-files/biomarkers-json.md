# Shared measurement storage

HRD, MSI, and TMB have independent manifest keys and analysis selections.
Their validated fields are stored together in the `biomarkers` collection and
linked to the parent sample by `SAMPLE_ID`.

## Input contracts

| Analysis | Manifest key | Raw contract |
| --- | --- | --- |
| HRD | `hrd` | [HRD score and components](hrd-json.md) |
| MSI | `msi` | [Single and paired MSI measurements](msi-json.md) |
| TMB | `tmb` | [Tumor mutational burden](tmb-json.md) |

A combined producer JSON can be referenced under multiple individual keys. Each
parser selects only its analysis's fields. The [combined synthetic example](../../assets/examples/ingest/biomarkers.json)
contains HRD and MSI; it can be referenced by both `hrd` and `msi`.

See [measurement analysis behavior](../measurement-analyses.md) for review,
clinical-rule facts, report selection, and update behavior.
