# RNA quality control: metrics JSON

Manifest key: `qc`. Stored destination: `rna_qc`.

## Before submission

Use one object and include every required metric. Alignment percentages use 0–100 units, not 0–1 fractions. `splice_ratio` and `flendist` are integers in the current contract. `provider_genotypes` maps marker names to strings. `sample_id` is a producer label; it does not determine the parent database record.

[Download the complete synthetic JSON](../../assets/examples/ingest/quality-control.json). All example identifiers and values are synthetic.
Ingest assigns `SAMPLE_ID` from the parent sample. Do not supply database IDs or review
state in pipeline files. The file must also satisfy the assay's required/expected file policy.

## Raw structure and fields

```json
{
  "sample_id": "SYNTHETIC-T",
  "tot_reads": 1000000,
  "mapped_pct": 95.0,
  "multimap_pct": 3.0,
  "mismatch_pct": 0.5,
  "canon_splice": 12000,
  "non_canon_splice": 200,
  "splice_ratio": 60,
  "genebody_cov": [
    100,
    102,
    99
  ],
  "genebody_cov_slope": -0.5,
  "provider_genotypes": {},
  "provider_called_genotypes": 0,
  "flendist": 150
}
```

| Key | Type | Meaning | Requirement / omission behavior |
| --- | --- | --- | --- |
| `sample_id` | string | Producer sample label; distinct from ingest-injected `SAMPLE_ID` | Required; no default |
| `tot_reads` | integer | Total reads | Required; no default |
| `mapped_pct` | number | Mapped percentage, 0–100 | Required; no default |
| `multimap_pct` | number | Multimapped percentage, 0–100 | Required; no default |
| `mismatch_pct` | number | Mismatch percentage, 0–100 | Required; no default |
| `canon_splice` | integer | Canonical splice count | Required; no default |
| `non_canon_splice` | integer | Noncanonical splice count | Required; no default |
| `splice_ratio` | integer | Producer splice ratio; current contract requires integer | Required; no default |
| `genebody_cov` | integer array | Ordered gene-body coverage measurements | Required; no default |
| `genebody_cov_slope` | number | Producer gene-body coverage slope | Required; no default |
| `provider_genotypes` | string-to-string map | Producer genotype labels | Required; no default |
| `provider_called_genotypes` | integer | Number of called provider genotypes | Required; no default |
| `flendist` | integer | Producer fragment-length metric | Required; no default |

## Related contracts

- [Bundle preparation and file index](README.md)
- [Sample manifest](../sample-manifest.md)
- [Stored collection contracts](../mongodb-collections.md)
