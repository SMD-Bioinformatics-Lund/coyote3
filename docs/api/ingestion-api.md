# Ingestion API

## Purpose

Replace external ad-hoc import flows with validated API-driven ingestion.

For an end-to-end relationship map of `asp`/`aspc`/`isgl` with `samples`, `variants`, `cnvs`, and RNA collections, see [Product / DNA And RNA Workflow Chain](../product/workflow-dna-rna.md).

## Endpoints

- `POST /api/v1/internal/ingest/sample-bundle`
- `POST /api/v1/internal/ingest/dependents`
- `POST /api/v1/internal/ingest/collection`
- `POST /api/v1/internal/ingest/collection/bulk`
- `GET /api/v1/internal/ingest/collections`

## Route commands (full examples)

Set runtime variables once:

```bash
export API_BASE_URL="http://${COYOTE3_HOST:-localhost}:${COYOTE3_STAGE_API_PORT:-8806}"
# Option A: existing bearer token
export API_BEARER_TOKEN="<YOUR_API_BEARER_TOKEN>"

# Option B: login via CLI helper
python scripts/api_login.py \
  --base-url "${API_BASE_URL}" \
  --mode password \
  --username "admin@your-center.org" \
  --password "CHANGE_ME" \
  --print-token
```

One-shot ordered seeding (required + optional baseline collections):

```bash
scripts/bootstrap_center_collections.sh \
  --api-base-url "${API_BASE_URL}" \
  --bearer-token "${API_BEARER_TOKEN}" \
  --seed-file tests/fixtures/db_dummy/center_template_seed.json \
  --with-optional \
  --skip-existing
```

Validate assay consistency before ingesting sample bundles:

```bash
python scripts/validate_assay_consistency.py \
  --seed-file tests/fixtures/db_dummy/center_template_seed.json \
  --yaml tests/data/ingest_demo/generic_case_control.yaml
```

This validator checks:

- assay references across `samples`, `blacklist`, `insilico_genelists`
- `asp_configs` (`aspc_id` format, assay/environment consistency)
- `insilico_genelists` (`assays` and `assay_groups` consistency)
- bootstrap dependencies (`roles -> permissions`, `users -> roles`, `refseq_canonical -> hgnc_genes`)

Discover supported collection-ingest contracts:

```bash
curl -sS "${API_BASE_URL}/api/v1/internal/ingest/collections" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}"
```

### 1) Seed one collection document

Route:
- `POST /api/v1/internal/ingest/collection`

Command:

```bash
curl -sS -X POST "${API_BASE_URL}/api/v1/internal/ingest/collection" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<'JSON'
{
  "collection": "users",
  "document": {
    "email": "admin@your-center.org",
    "firstname": "Center",
    "lastname": "Admin",
    "fullname": "Center Admin",
    "role": "admin",
    "is_active": true,
    "permissions": [],
    "deny_permissions": [],
    "assay_groups": [],
    "assays": []
  }
}
JSON
```

### 2) Seed many documents (bulk)

Route:
- `POST /api/v1/internal/ingest/collection/bulk`

Command:

```bash
curl -sS -X POST "${API_BASE_URL}/api/v1/internal/ingest/collection/bulk" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<'JSON'
{
  "collection": "refseq_canonical",
  "documents": [
    {"gene": "EGFR", "canonical": "ENST00000275493"},
    {"gene": "TP53", "canonical": "ENST00000269305"}
  ]
}
JSON
```

### 3) Ingest fresh sample + analysis bundle

Route:
- `POST /api/v1/internal/ingest/sample-bundle`

Command (YAML content mode):

```bash
curl -sS -X POST "${API_BASE_URL}/api/v1/internal/ingest/sample-bundle" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<JSON
{
  "yaml_content": $(python - <<'PY'
import json
from pathlib import Path
print(json.dumps(Path("tests/data/ingest_demo/generic_case_control.yaml").read_text(encoding="utf-8")))
PY
  ),
  "update_existing": false
}
JSON
```

### 4) Replace dependent analysis payload for existing sample

Route:
- `POST /api/v1/internal/ingest/dependents`

Command:

```bash
curl -sS -X POST "${API_BASE_URL}/api/v1/internal/ingest/dependents" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<'JSON'
{
  "sample_id": "65f0c0ffee00000000000001",
  "sample_name": "DEMO_SAMPLE_001",
  "delete_existing": true,
  "preload": {
    "cnvs": [
      {
        "chr": "7",
        "start": 55000000,
        "end": 56000000,
        "size": 1000000,
        "ratio": 0.4,
        "nprobes": 100,
        "genes": ["EGFR"],
        "callers": ["cnvkit"]
      }
    ]
  }
}
JSON
```

## Authentication and authorization

- Ingest/collection internal endpoints require authenticated API user session and RBAC.
- Recommended RBAC: admin-level role for collection bootstrap and dependent ingest.
- `update_existing=true` on sample-bundle requires authenticated user with `edit_sample` permission.

## First-time center bootstrap order

Use this order for a clean deployment at a new center.

1. Create Mongo infrastructure users.
   - Root/admin user (`MONGO_ROOT_*`) and app user (`MONGO_APP_*`).
   - Compose init scripts create app user only on first boot of an empty Mongo volume.
   - For existing volumes, run `scripts/mongo_bootstrap_users.py`.
2. Seed core access/config collections.
   - `permissions`
   - `roles`
   - `users`
   - `asp_configs`
   - `assay_specific_panels`
   - `insilico_genelists`
3. Seed reference collections required for predictable interpretation behavior.
   - `refseq_canonical` (required for canonical transcript selection in DNA ingest)
   - `hgnc_genes` (required for gene metadata routes/UI)
4. Optionally seed external knowledge collections (recommended for full UX).
   - `civic_genes`, `civic_variants`, `oncokb_genes`, `oncokb_actionable`, `brcaexchange`, `iarc_tp53`, `cosmic`, `vep_metadata`
5. Ingest sample data.
   - `POST /api/v1/internal/ingest/sample-bundle` for fresh sample + analysis data
   - `POST /api/v1/internal/ingest/dependents` for dependent-data refresh on existing sample

## Canonical transcript baseline (`refseq_canonical`)

Minimum expected document shape:

```json
{"gene": "EGFR", "canonical": "NM_005228"}
```

Guidance:

- `gene`: HGNC symbol used in variant `CSQ.SYMBOL`.
- `canonical`: canonical transcript accession used by your center's reporting policy.
- Keep this collection versioned externally (source/version/date) and update via bulk endpoint.
- Re-validate assay and ingest flows after canonical map changes.

## Collection bootstrapping via API

Use collection endpoints to seed reference/config data with schema validation.

- Single: `POST /api/v1/internal/ingest/collection`
- Bulk: `POST /api/v1/internal/ingest/collection/bulk`

Recommended ordered commands for first-time center bootstrap:

1. `permissions` via `/collection` or `/collection/bulk`
2. `roles` via `/collection` or `/collection/bulk`
3. `users` via `/collection` or `/collection/bulk`
4. `asp_configs` via `/collection` or `/collection/bulk`
5. `assay_specific_panels` via `/collection` or `/collection/bulk`
6. `insilico_genelists` via `/collection` or `/collection/bulk`
7. `refseq_canonical` via `/collection/bulk`
8. `hgnc_genes` via `/collection/bulk`

Example bulk seed for `refseq_canonical`:

```json
{
  "collection": "refseq_canonical",
  "documents": [
    {"gene": "EGFR", "canonical": "ENST00000275493"},
    {"gene": "TP53", "canonical": "ENST00000269305"}
  ]
}
```

## Minimum required dataset (baseline)

Use this as the minimum center onboarding contract:

| Collection | Minimum required keys | Why required |
| --- | --- | --- |
| `permissions` | `permission_id`, `permission_name` | RBAC policy definitions |
| `roles` | `role_id`, `level`, `permissions[]` | RBAC role resolution |
| `users` | `email`, `role`, `environments[]` | Login + authorization subject |
| `asp_configs` | `aspc_id`, `assay_name`, `environment`, `asp_group` | Assay+environment runtime config |
| `assay_specific_panels` | `asp_id`, `assay_name`, `asp_group` | Assay metadata/UI wiring |
| `insilico_genelists` | `isgl_id`, `diagnosis`, `assays[]`, `assay_groups[]`, `genes[]` | Panel/list filtering logic |
| `refseq_canonical` | `gene`, `canonical` | DNA transcript canonicalization |
| `hgnc_genes` | `hgnc_id`, `hgnc_symbol` | Gene metadata and symbol mapping |

## Sample bundle request modes

### Mode 1: structured spec

```json
{
  "spec": {
    "name": "DEMO_SAMPLE_001",
    "assay": "ASSAY_A",
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
  "yaml_content": "name: DEMO_SAMPLE_001\nassay: ASSAY_A\n...",
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

Core collections typically seeded first:

- `permissions`
- `roles`
- `users`
- `asp_configs`
- `assay_specific_panels`
- `insilico_genelists`
- `refseq_canonical`
- `hgnc_genes`

## Test fixtures for ingestion

- `tests/data/ingest_demo/*`
- `tests/fixtures/db_dummy/center_template_seed.json` (center onboarding seed)
- `tests/fixtures/db_dummy/all_collections_dummy.json` (full contract coverage fixture)

## Client example (Python)

```python
import requests

base = "http://localhost:6802"
headers = {"Authorization": "Bearer YOUR_API_BEARER_TOKEN"}

payload = {
    "spec": {
        "name": "DEMO_SAMPLE_001",
        "assay": "ASSAY_A",
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

## Troubleshooting by error

| Error fragment | Likely cause | Fix |
| --- | --- | --- |
| `Unknown assay references in seed` | Seed collections use assay IDs not present in ASPC/panel/ISGL docs | Align assay IDs across `asp_configs`, `assay_specific_panels`, `insilico_genelists` |
| `Bootstrap dependency errors` | Missing required baseline collection docs or broken refs | Populate required collections in onboarding order |
| `No DB document model registered` | Unsupported collection name in ingest request | Use `/api/v1/internal/ingest/collections` and correct `collection` |
| `diagnosis must include at least one value` | ISGL payload missing diagnosis | Provide non-empty `diagnosis` list/string |
| `aspc_id environment segment must match environment` | `aspc_id` and `environment` mismatch | Keep `aspc_id` as `assay:environment` and matching fields |
| `403 Forbidden` on update mode | User missing `edit_sample` permission | Add `edit_sample` to role or user permissions |
