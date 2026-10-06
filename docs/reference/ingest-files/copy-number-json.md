# Copy-number variants: JSON

Manifest key: `cnv`. Stored destination: `cnvs`.

## Before submission

Provide `chr`, `start`, `end`, and `size` for every interval. Ingest preserves coordinates without converting their origin or end convention. Use the convention agreed with the assay pipeline. Non-object entries are skipped by the current parser; producers should reject them before submission to avoid silently losing intervals.

[Download the complete synthetic JSON](../../assets/examples/ingest/copy-number.json). All example identifiers and values are synthetic.
Ingest assigns `SAMPLE_ID` from the parent sample. Do not supply database IDs or review
state in pipeline files. The file must also satisfy the assay's required/expected file policy.

## Raw structure and fields

```json
[
  {
    "chr": "1",
    "start": 10000,
    "end": 20000,
    "size": 10000,
    "ratio": -0.6,
    "type": "loss",
    "nprobes": 12,
    "genes": [
      {
        "gene": "GENE1",
        "class": "coding",
        "cnv_type": "loss"
      }
    ],
    "callers": [
      "cnvkit"
    ]
  }
]
```

| Key | Description | Storage/normalization | Requirement / omission behavior |
| --- | --- | --- | --- |
| `chr` | Chromosome string | `cnvs.chr` | Required; no default |
| `start` | Interval start supplied by producer | `cnvs.start`; no coordinate conversion is performed | Required; no default |
| `end` | Interval end supplied by producer | `cnvs.end` | Required; no default |
| `size` | Producer-supplied interval size | `cnvs.size`; supply it explicitly | Required; no default |
| `ratio` | Numeric copy-number ratio or supported event label | Float/null; `DEL`/`LOSS` → -1, `AMP` → 1, `DUP`/`GAIN` → 0.5 | Optional; null |
| `type` | Event type | Preserved when provided; inferred from normalized ratio when absent | Optional; inferred from ratio, or null |
| `nprobes` | Probe count | Integer; missing value normalizes to 0, which is a parser default rather than measured evidence | Optional; 0 |
| `genes` | Affected-gene objects | `cnvs.genes[]`; absent → empty list | Optional; [] |
| `genes[].gene` | Gene name | Stored gene identifier | Required in each supplied gene object; no default |
| `genes[].class` | Producer gene class | Stored as supplied | Optional; null, omitted from stored gene metadata |
| `genes[].cnv_type` | Per-gene event type | Stored as supplied | Optional; null, omitted from stored gene metadata |
| `callers` | Calling tools | List, or comma/pipe/semicolon-delimited text; normalized to lowercase list | Optional; [] |

An alternative root is an object keyed by interval ID. Each value becomes one
row and receives `_pipeline_key` from its object key when not already supplied.

## Related contracts

- [Bundle preparation and file index](README.md)
- [Sample manifest](../sample-manifest.md)
- [Stored collection contracts](../mongodb-collections.md)
