# Ingestion API

## Purpose

Replace external ad-hoc import flows with validated API-driven ingestion.

## Endpoints

- `POST /api/v1/internal/ingest/sample-bundle`
- `POST /api/v1/internal/ingest/dependents`
- `POST /api/v1/internal/ingest/collection`
- `POST /api/v1/internal/ingest/collection/bulk`

## Authentication and authorization

- Internal endpoints require `INTERNAL_API_TOKEN`.
- `update_existing=true` on sample-bundle requires authenticated user with `edit_sample` permission.

## Sample bundle request modes

### Mode 1: structured spec

```json
{
  "spec": {
    "name": "DEMO_SAMPLE_001",
    "assay": "hema_GMSv1",
    "profile": "test",
    "genome_build": 38,
    "vcf_files": "/data/demo.vcf",
    "cnv": "/data/demo.cnv.json",
    "cov": "/data/demo.cov.json",
    "increment": false
  },
  "update_existing": false
}
```

### Mode 2: YAML content

```json
{
  "yaml_content": "name: DEMO_SAMPLE_001\nassay: hema_GMSv1\n...",
  "update_existing": false
}
```

## Collection insert examples

### Single document

```json
{
  "collection": "variants",
  "document": {
    "SAMPLE_ID": "65f0c0ffee00000000000001",
    "CHROM": "7",
    "POS": 140453136,
    "REF": "A",
    "ALT": "T",
    "INFO": {"variant_callers": ["tnscope"], "CSQ": []},
    "GT": []
  }
}
```

### Bulk document

```json
{
  "collection": "cnvs",
  "documents": [
    {"SAMPLE_ID": "65f0c0ffee00000000000001", "chr": "7", "start": 1, "end": 2},
    {"SAMPLE_ID": "65f0c0ffee00000000000001", "chr": "12", "start": 3, "end": 4}
  ]
}
```

## Test fixtures for ingestion

- `tests/data/ingest_demo/*`
- `tests/fixtures/db_dummy/all_collections_dummy.json`

## Client example (Python)

```python
import requests

base = "http://localhost:6816"
headers = {"X-Internal-Api-Token": "YOUR_TOKEN"}

payload = {
    "spec": {
        "name": "DEMO_SAMPLE_001",
        "assay": "hema_GMSv1",
        "profile": "test",
        "genome_build": 38,
        "vcf_files": "/app/tests/data/ingest_demo/generic_case_control.final.filtered.vcf",
        "cnv": "/app/tests/data/ingest_demo/generic_case_control.cnvs.merged.json",
        "cov": "/app/tests/data/ingest_demo/generic_case_control.cov.json",
    },
    "update_existing": False,
}

r = requests.post(f"{base}/api/v1/internal/ingest/sample-bundle", json=payload, headers=headers, timeout=120)
r.raise_for_status()
print(r.json())
```
