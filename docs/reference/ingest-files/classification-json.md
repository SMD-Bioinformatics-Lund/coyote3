# RNA classification: score JSON

Manifest key: `classification_path`. Stored destination: `rna_classification`.

## Before submission

Use one object with a version and result array. The input key is `class`, not `class_`. `true` and `total` are integers, and `true` must not exceed `total`. The score is producer-defined; the ingest contract does not impose a universal probability scale or classify the sample again.

[Download the complete synthetic JSON](../../assets/examples/ingest/classification.json). All example identifiers and values are synthetic.
Ingest assigns `SAMPLE_ID` from the parent sample. Do not supply database IDs or review
state in pipeline files. The file must also satisfy the assay's required/expected file policy.

## Raw structure and fields

```json
{
  "classifier_version": "1.0.0",
  "classifier_results": [
    {
      "class": "SYNTHETIC_CLASS",
      "score": 0.98,
      "true": 98,
      "total": 100
    }
  ]
}
```

| Key | Description and mapping to `rna_classification` |
| --- | --- |
| `classifier_version` | Required classifier version |
| `classifier_results` | Array of result rows |
| Row `class` | Class label; Pydantic internal alias is `class_`, persisted key is `class` |
| Row `score` | Numeric producer score; no reclassification during ingest |
| Row `true` | Integer supporting count |
| Row `total` | Integer total count; `true` cannot exceed `total` |

## Related contracts

- [Bundle preparation and file index](README.md)
- [Sample manifest](../sample-manifest.md)
- [Stored collection contracts](../mongodb-collections.md)
