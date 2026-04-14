# Ingestion API

## Purpose

Use the API to load configuration data and sample bundles in a validated, repeatable way.

For an end-to-end relationship map of `asp`/`aspc`/`isgl` with `samples`, `variants`, `cnvs`, and RNA collections, see [Product / DNA And RNA Workflow Chain](../product/workflow_dna_rna.md).
For full per-collection key contracts (required and optional), see [API / Collection Contracts](collection_contracts.md).
For the sample ingest manifest shape used by these routes, see [API / Sample YAML Guide](sample_yaml.md).

All ingest endpoints validate request documents with backend Pydantic contracts before any database write. Payloads are normalized from those contracts and then persisted, so the behavior is the same whether the caller is a script or an API client.

## Atomicity and rollback guarantees

For fresh sample creation through:

- `POST /api/v1/internal/ingest/sample-bundle`
- `POST /api/v1/internal/ingest/sample-bundle/upload`

the ingest flow now follows this order:

1. Validate the top-level sample payload.
2. Parse referenced data files into preload payloads.
3. Insert the sample anchor with `ingest_status="loading"`.
4. Write dependent analysis collections (`variants`, `cnvs`, `fusions`, coverage, and related evidence).
5. Mark the sample as `ingest_status="ready"` only after all dependent writes succeed.

Failure behavior:

- If validation or file parsing fails, no sample document is inserted.
- If any write fails after the sample anchor is created, ingest attempts rollback cleanup and deletes the staged sample plus dependent analysis documents.
- When Mongo sessions/transactions are supported by the runtime, the create flow executes inside a transaction boundary as an additional safeguard.

Scope note:

- These guarantees apply to **fresh sample creation**.
- `update_existing=true` still uses dependent-data replacement with rollback for evidence collections, but sample metadata updates are not yet a full multi-document transaction.

## Endpoints

- `POST /api/v1/internal/ingest/sample-bundle`
- `POST /api/v1/internal/ingest/sample-bundle/upload`
- `POST /api/v1/internal/ingest/dependents`
- `POST /api/v1/internal/ingest/collection`
- `POST /api/v1/internal/ingest/collection/bulk`
- `PUT /api/v1/internal/ingest/collection`
- `POST /api/v1/internal/ingest/collection/upload`
- `GET /api/v1/internal/ingest/collections`
- `GET /api/v1/internal/metrics`

## Route commands (full examples)

Set runtime variables once:

```bash
export API_BASE_URL="http://${COYOTE3_HOST:-localhost}:${COYOTE3_STAGE_API_PORT:-8806}"
# Option A: existing bearer token
export API_BEARER_TOKEN="<YOUR_API_BEARER_TOKEN>"

# Option B: login via CLI helper
${PYTHON_BIN:-python} scripts/api_login.py \
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
  --seed-file tests/fixtures/db_dummy/all_collections_dummy \
  --reference-seed-data tests/data/seed_data \
  --with-optional
```

Behavior:

- Default mode retries a failed collection seed once with `ignore_duplicates=true`.
- Add `--skip-existing` to always seed in duplicate-tolerant mode.
- Add `--strict-no-retry` to fail immediately on first error.

Seed source policy for first-time center bootstrap:

- Use the repository baseline seed: `tests/fixtures/db_dummy/all_collections_dummy`.
- Use `--reference-seed-data tests/data/seed_data` to load compressed baseline packs for
  `permissions`, `roles`, `refseq_canonical`, `hgnc_genes`, and `vep_metadata`.
- Update assay/group identifiers (`assay_1`, `hematology`) to your center values before bootstrap.
- Keep bootstrap deterministic by versioning those seed changes in git for your center deployment repo.
- `asp_configs` and `assay_specific_panels` belong to first-sample demo onboarding
  seed files (`--seed-file`, for example `tests/fixtures/db_dummy/all_collections_dummy`).
  If matching compressed files exist in `--reference-seed-data`, bootstrap loads them,
  but they are not required reference-pack files.
- `asp_configs` documents are contract-driven and must carry `filters` and `reporting` objects.
  Base behavior is configured with `filters` keys and optional assay-specific
  operator overrides in top-level `query.snv`, `query.cnv`, `query.fusion`, and `query.transloc`.
  CNV behavior is configured with `filters.cnv_*` keys.
  Fusion behavior is configured with `filters.fusion_*` keys.

Validate assay consistency before ingesting sample bundles:

```bash
${PYTHON_BIN:-python} scripts/validate_assay_consistency.py \
  --seed-file tests/fixtures/db_dummy/all_collections_dummy \
  --yaml tests/data/ingest_demo/generic_case_control.yaml
```

The demo YAML includes `vep_version`. It is stored on the sample and later used to resolve the correct `vep_metadata` translations and consequence-group mappings during DNA findings and reporting.

This validator checks:

- assay references across `samples`, `blacklist`, `insilico_genelists`
- seed document contract shape (`*.json` arrays of objects only)
- metadata field typing (`created_on`/`updated_on` ISO-8601 strings, numeric `version`)
- `version_history` structure and timestamp typing
- rejection of Mongo Extended JSON wrappers (`$date`, `$oid`) in seed files
- required baseline governance/config presence (`roles`, `permissions`)
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
  "collection": "asp_configs",
  "document": {
    "aspc_id": "assay_1:production",
    "assay_name": "assay_1",
    "environment": "production",
    "asp_group": "hematology",
    "asp_category": "dna",
    "analysis_types": ["small_variants", "cnv"],
    "display_name": "assay_1 production",
    "filters": {
      "min_freq": 0.05,
      "max_freq": 1.0,
      "max_control_freq": 0.05,
      "max_popfreq": 0.01
    },
    "query": {
      "snv": {
        "$or": [
          {"INFO.MYELOID_GERMLINE": 1}
        ]
      }
    },
    "reporting": {
      "report_sections": ["summary", "snv", "cnv"],
      "report_header": "assay_1 Report",
      "report_method": "Standard analysis",
      "report_description": "Validated reporting profile",
      "general_report_summary": "Prepared in Coyote3",
      "plots_path": "reports/plots",
      "report_folder": "reports/output"
    },
    "is_active": true
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

### 2b) Update or upsert one document

Route:

- `PUT /api/v1/internal/ingest/collection`

Command:

```bash
curl -sS -X PUT "${API_BASE_URL}/api/v1/internal/ingest/collection" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<'JSON'
{
  "collection": "asp_configs",
  "match": {"aspc_id": "assay_1:production"},
  "document": {
    "aspc_id": "assay_1:production",
    "assay_name": "assay_1",
    "environment": "production",
    "asp_group": "hematology",
    "asp_category": "dna",
    "analysis_types": ["small_variants", "cnv"],
    "display_name": "assay_1 production",
    "filters": {
      "min_freq": 0.05,
      "max_freq": 1.0,
      "max_control_freq": 0.05,
      "max_popfreq": 0.01
    },
    "query": {
      "snv": {
        "$or": [
          {"INFO.MYELOID_GERMLINE": 1}
        ]
      }
    },
    "reporting": {
      "report_sections": ["summary", "snv", "cnv"],
      "report_header": "assay_1 Report",
      "report_method": "Standard analysis",
      "report_description": "Validated reporting profile",
      "general_report_summary": "Prepared in Coyote3",
      "plots_path": "reports/plots",
      "report_folder": "reports/output"
    },
    "is_active": true
  },
  "upsert": true
}
JSON
```

### 2c) Upload collection JSON file (multipart)

Route:

- `POST /api/v1/internal/ingest/collection/upload`

Notes:

- This route validates uploaded JSON via the same collection Pydantic contracts used by
  `/collection`, `/collection/bulk`, and `/collection` upsert.
- For governance/config uploads in admin workflows, supported collections are:
  `users`, `roles`, `permissions`, `asp_configs`, `assay_specific_panels`, `insilico_genelists`.
- `mode=insert` expects a JSON object.
- `mode=bulk` expects a JSON array.
- `mode=upsert` expects a JSON object plus `match_json` form field.

Command:

```bash
curl -sS -X POST "${API_BASE_URL}/api/v1/internal/ingest/collection/upload" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  -F "collection=users" \
  -F "mode=insert" \
  -F "documents_file=@/path/to/users.json;type=application/json"
```

### 3) Ingest fresh sample + analysis bundle (YAML string mode)

Route:

- `POST /api/v1/internal/ingest/sample-bundle`

Command (YAML content mode):

```bash
curl -sS -X POST "${API_BASE_URL}/api/v1/internal/ingest/sample-bundle" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<JSON
{
  "yaml_content": $(${PYTHON_BIN:-python} - <<'PY'
import json
from pathlib import Path
print(json.dumps(Path("tests/data/ingest_demo/generic_case_control.yaml").read_text(encoding="utf-8")))
PY
  ),
  "update_existing": false
}
JSON
```

### 4) Ingest fresh sample + analysis bundle (upload YAML + data files)

Route:

- `POST /api/v1/internal/ingest/sample-bundle/upload`

Command (multipart upload mode):

```bash
curl -sS -X POST "${API_BASE_URL}/api/v1/internal/ingest/sample-bundle/upload" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  -F "yaml_file=@tests/data/ingest_demo/generic_case_control.yaml;type=text/yaml" \
  -F "data_files=@tests/data/ingest_demo/generic_case_control.final.filtered.vcf" \
  -F "data_files=@tests/data/ingest_demo/generic_case_control.cnvs.merged.json" \
  -F "data_files=@tests/data/ingest_demo/generic_case_control.cov.json" \
  -F "data_files=@tests/data/ingest_demo/generic_case_control.modeled.png" \
  -F "increment=true" \
  -F "update_existing=false"
```

Rules:

- Keep file path values in YAML (`vcf_files`, `cnv`, `cov`, `fusion_files`, etc.) as source paths.
- Upload matching files in the same request using `data_files`.
- Matching is done by exact filename value from YAML or by basename.
- Backend stages uploaded files temporarily, parses them, ingests to DB, and removes staged files after request completion.
- Uploaded runtime files are hashed (`sha256`) and persisted on the sample as `uploaded_file_checksums`.

### 4b) Internal metrics endpoint (Prometheus text format)

Route:

- `GET /api/v1/internal/metrics`

Command:

```bash
curl -sS "${API_BASE_URL}/api/v1/internal/metrics" \
  -H "X-Internal-Token: ${INTERNAL_API_TOKEN}"
```

### 5) Replace dependent analysis payload for existing sample

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
- Internal ingest endpoints are restricted to `developer` and `admin` role levels.
- `update_existing=true` on sample-bundle requires authenticated user with `edit_sample` permission.
- Admin UI ingestion workspace (`/admin/ingest`) is also restricted to `developer` and `admin`.

Collection action permissions (from seeded permission catalog):

| Collection group | Create/Bulk permission | Update/Upsert permission |
| --- | --- | --- |
| `users` | `create_user` | `edit_user` |
| `roles` | `create_role` | `edit_role` |
| `permissions` | `create_permission_policy` | `edit_permission_policy` |
| `assay_specific_panels` (`asp`) | `create_asp` | `edit_asp` |
| `asp_configs` (`aspc`) | `create_aspc` | `edit_aspc` |
| `insilico_genelists` (`isgl`) | `create_isgl` | `edit_isgl` |
| Sample-linked data (`samples`, `variants`, `cnvs`, `translocations`, `biomarkers`, `panel_coverage`, `fusions`, `rna_expression`, `rna_classification`, `rna_qc`, `reported_variants`, `group_coverage`) | `edit_sample` | `edit_sample` |
| Shared and annotation knowledgebase collections (`hgnc_genes`, `refseq_canonical`, `vep_metadata`, `civic_*`, `oncokb_*`, `cosmic`, `hpaexpr`, `iarc_tp53`, `annotation`, `blacklist`, `dashboard_metrics`, `brcaexchange`, `mane_select`, `asp_to_groups`) | developer/admin role-level gate | developer/admin role-level gate |

`admin` role-level users are always allowed for these operations.

## First-time center bootstrap order

Use this order for a clean deployment at a new center.

1. Create Mongo infrastructure users.
   - Root/admin user (`MONGO_ROOT_*`) and app user (`MONGO_APP_*`).
   - Compose init scripts create app user only on first boot of an empty Mongo volume.
   - For existing volumes, run `scripts/mongo_bootstrap_users.py`.
2. Seed mandatory shared collections.
   - `hgnc_genes`
   - `permissions`
   - `refseq_canonical`
   - `roles`
   - `vep_metadata`
3. Bootstrap mandatory runtime collections.
   - first superuser via `scripts/bootstrap_local_admin.py` (writes user audit metadata)
   - `asp_configs`
   - `assay_specific_panels`
4. Optionally seed filtering and annotation knowledgebase collections.
   - `insilico_genelists`
   - `civic_genes`, `civic_variants`, `oncokb_genes`, `oncokb_actionable`, `brcaexchange`, `iarc_tp53`, `cosmic`, `hpaexpr`
5. Ingest sample data.
   - `POST /api/v1/internal/ingest/sample-bundle` for fresh sample + analysis data
   - `POST /api/v1/internal/ingest/sample-bundle/upload` for fresh sample + uploaded data files
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
3. `refseq_canonical` via `/collection/bulk`
4. `hgnc_genes` via `/collection/bulk`
5. `vep_metadata` via `/collection/bulk`
6. first superuser via `scripts/bootstrap_local_admin.py`
7. `asp_configs` via `/collection` or `/collection/bulk`
8. `assay_specific_panels` via `/collection` or `/collection/bulk`
9. optional `insilico_genelists` and annotation knowledgebase collections

Note:

- `scripts/bootstrap_center_collections.sh` intentionally skips `users`.
- If needed, seed additional `users` later via collection endpoints or admin user management UI/API.

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
| `users` | `username`, `email`, `roles[]`, `environments[]` | Login + authorization subject (first superuser should be created by `bootstrap_local_admin.py`) |
| `asp_configs` | `aspc_id`, `assay_name`, `environment`, `asp_group`, `asp_category`, `analysis_types[]`, `display_name`, `filters{...}`, `reporting{...}`, `is_active` | Assay+environment runtime config |
| `assay_specific_panels` | `asp_id`, `assay_name`, `asp_group`, `is_active` | Assay metadata/UI wiring |
| `insilico_genelists` | `isgl_id`, `diagnosis`, `assays[]`, `assay_groups[]`, `genes[]`, `is_active` | Panel/list filtering logic |
| `refseq_canonical` | `gene`, `canonical` | DNA transcript canonicalization |
| `hgnc_genes` | `hgnc_id`, `hgnc_symbol` | Gene metadata and symbol mapping |

Managed-admin form source:

- For ASP/ASPC/ISGL/users/roles/permissions, admin UI forms use backend-generated schemas from contracts (`api/contracts/managed_ui_schemas.py`).
- Version and history are tracked via `version` and `version_history`.

Assay-group contract:

- `asp_group` is a fixed platform vocabulary defined in `shared/config_constants.py`.
- Current allowed values are:
  - `hematology`
  - `solid`
  - `pgx`
  - `tumwgs`
  - `wts`
  - `myeloid`
  - `lymphoid`
  - `dna`
  - `rna`
- Centers may register any ASP they need, but each ASP and ASPC must link to one of those existing assay groups.
- Adding a new assay group requires a product/code release, not only an admin-side data change.

Other fixed admin/runtime vocabularies:

- `asp_family`:
  - `panel-dna`
  - `panel-rna`
  - `wgs`
  - `wts`
- `asp_category`:
  - `dna`
  - `rna`
- `environment` / sample `profile`:
  - `production`
  - `development`
  - `testing`
  - `validation`
- sample `sequencing_scope`:
  - `panel`
  - `wgs`
  - `wts`
- `auth_type`:
  - `coyote3`
  - `ldap`
- `platform`:
  - `illumina`
  - `pacbio`
  - `nanopore`
  - `iontorrent`
- permission `category`:
  - `Analysis Actions`
  - `Assay Configuration Management`
  - `Assay Panel Management`
  - `Audit & Monitoring`
  - `Data Downloads`
  - `Gene List Management`
  - `Permission Policy Management`
  - `Reports`
  - `Role Management`
  - `Sample Management`
  - `Schema Management`
  - `User Management`
  - `Variant Curation`
  - `Visualization`

## Sample bundle request modes

### Mode 1: structured spec

```json
{
  "spec": {
    "name": "DEMO_SAMPLE_001",
    "assay": "assay_1",
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
  "yaml_content": "name: DEMO_SAMPLE_001\nassay: assay_1\n...",
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
- first local superuser via `scripts/bootstrap_local_admin.py`
- `asp_configs`
- `assay_specific_panels`
- `insilico_genelists`
- `refseq_canonical`
- `hgnc_genes`

## Test fixtures for ingestion

- `tests/data/ingest_demo/*`
- `tests/fixtures/db_dummy/all_collections_dummy` (center onboarding seed)

## Client example (Python)

```python
import requests

base = "http://localhost:6802"
headers = {"Authorization": "Bearer YOUR_API_BEARER_TOKEN"}

payload = {
    "spec": {
        "name": "DEMO_SAMPLE_001",
        "assay": "assay_1",
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
| `Seed contract-shape errors` | Seed files contain invalid document shape/metadata typing | Keep each collection file as `list[object]`, use ISO-8601 datetimes, numeric `version`, and plain JSON scalar values |
| `Unknown assay references in seed` | Seed collections use assay IDs not present in ASPC/panel/ISGL docs | Align assay IDs across `asp_configs`, `assay_specific_panels`, `insilico_genelists` |
| `Bootstrap dependency errors` | Missing required baseline collection docs or broken refs | Populate required collections in onboarding order |
| `Assay config not found for sample` | `asp_configs` doc missing, inactive, or mismatched `aspc_id`/profile | Ensure `aspc_id=assay:profile`, set `is_active=true`, and keep `sample.profile` aligned |
| `No DB document model registered` | Unsupported collection name in ingest request | Use `/api/v1/internal/ingest/collections` and correct `collection` |
| `diagnosis must include at least one value` | ISGL payload missing diagnosis | Provide non-empty `diagnosis` list/string |
| `aspc_id environment segment must match environment` | `aspc_id` and `environment` mismatch | Keep `aspc_id` as `assay:environment` and matching fields |
| `403 Forbidden` on update mode | User missing `edit_sample` permission | Add `edit_sample` to role or user permissions |
