# Panel coverage: JSON

Manifest key: `cov`. Stored destination: `d4_coverage`.

This structure represents D4-derived coverage. Assay-group exclusions are stored
separately in `d4_coverage_blacklist`, with `group`, `gene`, `region`, and a `coord`
key for region-level exclusions. They are maintained through coverage review and
are not sample measurements in this input file.

## Before submission

Use objects keyed by gene and region identifiers, not arrays. Each gene needs `covered_by_panel` and `transcript`; each supplied region needs `chr`, `start`, and `end`. Preserve unknown coverage as `null`. A measured zero means no coverage and must not replace a missing measurement.

[Download the complete synthetic JSON](../../assets/examples/ingest/coverage.json). All example identifiers and values are synthetic.
Ingest assigns `SAMPLE_ID` from the parent sample. Do not supply database IDs or review
state in pipeline files. The file must also satisfy the assay's required/expected file policy.

## Raw structure and fields

```json
{
  "genes": {
    "GENE1": {
      "covered_by_panel": true,
      "transcript": {
        "chr": "1",
        "start": 10000,
        "end": 20000,
        "transcript_id": "ENST000001"
      },
      "exons": {
        "1": {
          "chr": "1",
          "start": 10000,
          "end": 10100,
          "nbr": 1,
          "cov": 120.5
        }
      },
      "CDS": {
        "1": {
          "chr": "1",
          "start": 10020,
          "end": 10100,
          "nbr": 1,
          "cov": 118.0
        }
      },
      "probes": {
        "p1": {
          "chr": "1",
          "start": 10000,
          "end": 10050,
          "cov": null
        }
      }
    }
  }
}
```

| Key | Description | Stored mapping | Requirement / omission behavior |
| --- | --- | --- | --- |
| `genes` | Object keyed by gene name | `d4_coverage.genes` | Optional; {} (no gene measurements) |
| `genes.<gene>.covered_by_panel` | Panel-membership boolean | Same nested field | Required per gene; no default |
| `transcript.chr`, `transcript.start`, `transcript.end` | Transcript interval | Same keys below the gene; producer coordinates preserved | Required per transcript; no default |
| `transcript.transcript_id` | Transcript identifier | Same nested field | Required per transcript; no default |
| `exons`, `CDS`, `probes` | Objects keyed by producer region ID | Same nested region maps; omitted maps default to empty objects | Optional; {} for each map |
| Region `chr`, `start`, `end` | Genomic interval | Required for each supplied region | Required per region; no default |
| Exon/CDS `nbr` | Optional region number | Integer or null | Optional; null |
| Region `cov` | Optional measured coverage | Number or null; missing does not become zero | Optional; null |
| `sample` | Parent display name | Overwritten by ingest with the parent sample name | Service-owned; parent name |
| `SAMPLE_ID` | Parent database identity | Injected by ingest | Service-owned; parent ID |

## Related contracts

- [Bundle preparation and file index](README.md)
- [Sample manifest](../sample-manifest.md)
- [Stored collection contracts](../mongodb-collections.md)
