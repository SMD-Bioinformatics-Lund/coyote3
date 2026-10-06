# RNA expression: sample and reference JSON

Manifest key: `expression_path`. Stored destination: `rna_expression`.

## Before submission

Use one object containing `expression_version`, `sample`, and `reference`. Every sample row requires all listed measurements. Document expression units, normalization, reference cohort, and z-score calculation in the producing pipeline; ingest stores these values without recomputing them. Do not mix incompatible units between sample and reference rows.

[Download the complete synthetic JSON](../../assets/examples/ingest/expression.json). All example identifiers and values are synthetic.
Ingest assigns `SAMPLE_ID` from the parent sample. Do not supply database IDs or review
state in pipeline files. The file must also satisfy the assay's required/expected file policy.

## Raw structure and fields

```json
{
  "expression_version": "1.0.0",
  "sample": [
    {
      "hgnc_symbol": "GENE1",
      "ensembl_gene_id": "ENSG000001",
      "sample_expression": 12.0,
      "reference_sd": 2.0,
      "reference_mean": 10.0,
      "reference_median": 9.5,
      "reference_mean_mod": 10.0,
      "sample_mod": 12.0,
      "z": 1.0
    }
  ],
  "reference": [
    {
      "hgnc_symbol": "GENE1",
      "ensembl_gene_id": "ENSG000001",
      "reference_sd": 2.0,
      "reference_mean": 10.0,
      "reference_median": 9.5,
      "quant_values": {
        "reference_a": 9.0,
        "reference_b": 11.0
      }
    }
  ]
}
```

| Key | Description and mapping to `rna_expression` | Requirement / omission behavior |
| --- | --- | --- |
| `expression_version` | Required producer format/analysis version, not VEP version | Required; no default |
| `sample` | Array of sample gene-expression rows | Required; no default |
| `reference` | Array of reference gene-expression rows | Required; no default |
| Row `hgnc_symbol` | Gene symbol | Required; no default |
| Row `ensembl_gene_id` | Ensembl gene identifier | Required; no default |
| Sample `sample_expression` | Producer expression measurement; units follow the upstream pipeline | Required; no default |
| Row `reference_sd` | Reference standard deviation | Required; no default |
| Row `reference_mean` | Reference mean | Required; no default |
| Row `reference_median` | Reference median | Required; no default |
| Sample `reference_mean_mod` | Producer-modified reference mean | Required; no default |
| Sample `sample_mod` | Producer-modified sample expression | Required; no default |
| Sample `z` | Producer z-score; ingest does not recompute it | Required; no default |
| Reference `quant_values` | Map of reference labels to numeric values | Optional; {} before dynamic keys are collected |
| Other reference-row keys | Collected into `quant_values` and converted to float; matching top-level values override explicit map entries | Optional; no additional quantifications |

## Related contracts

- [Bundle preparation and file index](README.md)
- [Sample manifest](../sample-manifest.md)
- [Stored collection contracts](../mongodb-collections.md)
