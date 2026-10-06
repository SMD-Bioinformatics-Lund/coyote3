# Pharmacogenomics: JSON payload

Manifest key: `pgx`. Stored destination: `pgx`.

## Before submission

Use a JSON object or an array containing only objects. A scalar or an array containing strings or numbers is rejected. Coyote3 preserves this payload but does not infer PharmCAT interpretation, drug recommendations, or clinical significance from arbitrary keys.

[Download the complete synthetic JSON](../../assets/examples/ingest/pharmacogenomics.json). All example identifiers and values are synthetic.
Ingest assigns `SAMPLE_ID` from the parent sample. Do not supply database IDs or review
state in pipeline files. The file must also satisfy the assay's required/expected file policy.

## Raw structure and fields

```json
{
  "pipeline_version": "synthetic-1",
  "records": [
    {
      "gene": "GENE1",
      "result": "example"
    }
  ]
}
```

PGX object keys are preserved without defining gene/drug interpretation semantics.
A root array is wrapped as `{"records": [...]}`. The resulting object is stored
in `pgx` with injected `SAMPLE_ID`; each arbitrary record is not a separate MongoDB
document. The example keys are illustrative extensions, not mandatory PGX fields.

## Field requirements and defaults

| Item | Requirement | Omission behavior |
| --- | --- | --- |
| Root object or array of objects | Required | An empty file is invalid JSON; a scalar is rejected. |
| Producer-defined keys such as `pipeline_version`, `records`, `gene`, `result` | No fixed required keys at this boundary | No interpretation or replacement values are generated. |
| `SAMPLE_ID` | Supplied by ingest | Always bound to the parent sample; not a pipeline-selected database ID. |

A valid empty object or array contains no PGX conclusions. Successful storage is
not evidence that a drug recommendation or clinically reportable result exists.

## Related contracts

- [Bundle preparation and file index](README.md)
- [Sample manifest](../sample-manifest.md)
- [Stored collection contracts](../mongodb-collections.md)
