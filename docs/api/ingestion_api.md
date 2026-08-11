# Ingestion API

## Purpose

Use the API to load configuration data and sample bundles in a validated, repeatable way.

For an end-to-end relationship map of `asp`/`aspc`/`isgl` with `samples`, `variants`, `cnvs`, and RNA collections, see [Product / DNA And RNA Workflow Chain](../product/workflow_dna_rna.md).
For full per-collection key contracts (required and optional), see [API / Collection Contracts](collection_contracts.md).
For the sample ingest manifest shape used by these routes, see [API / Sample YAML Guide](sample_yaml.md).
For the raw VCF and JSON file shapes consumed by the ingest parsers, see [API / Sample Input Files](sample_input_files.md).

All ingest endpoints validate request documents with backend Pydantic contracts before any database write. Payloads are normalized before persistence, so the behavior is the same whether the caller is a script or an API client.

![Celery-backed sample ingest flow](../assets/diagrams/celery_ingest_flow.svg)

## Atomicity and rollback guarantees

For fresh sample creation through:

- `POST /api/v1/internal/ingest/sample-bundle`
- `POST /api/v1/internal/ingest/sample-bundle/upload`

the ingest flow follows this order:

1. Validate the top-level sample payload.
2. Parse referenced data files into preload payloads.
3. Insert the sample anchor with `ingest_status="loading"`.
4. Write dependent finding and quality collections (`variants`, `cnvs`, `fusions`, `panel_coverage`, and related evidence).
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
- `POST /api/v1/internal/ingest/sample-bundle/async`
- `POST /api/v1/internal/ingest/sample-bundle/upload`
- `POST /api/v1/internal/ingest/sample-bundle/upload/async`
- `POST /api/v1/internal/ingest/collection`
- `POST /api/v1/internal/ingest/collection/async`
- `POST /api/v1/internal/ingest/collection/bulk`
- `POST /api/v1/internal/ingest/collection/bulk/async`
- `PUT /api/v1/internal/ingest/collection`
- `PUT /api/v1/internal/ingest/collection/async`
- `POST /api/v1/internal/ingest/collection/upload`
- `GET /api/v1/internal/ingest/collections`
- `GET /api/v1/internal/tasks/{task_id}`
- `GET /api/v1/internal/metrics`

## Celery-backed async ingest

The async routes perform the same API authentication and authorization checks as
the synchronous internal ingest routes, then enqueue work on the Celery `ingest`
queue. Workers are defined in the Compose stacks as `coyote3_worker`,
`coyote3_dev_worker`, `coyote3_stage_worker`, and `coyote3_test_worker`.

Runtime settings:

- `CELERY_INGEST_QUEUE`: Queue used for ingest work. Defaults to `ingest`.
- `CELERY_WORKER_CONCURRENCY`: Worker concurrency. Defaults to `2`.
- `/data/coyote3/ingest_staging`: Fixed durable server-side staging root for async upload files.

Redis broker/result URLs are internal Compose wiring. They are not center-owned
environment-file settings.

Async response:

```json
{
  "status": "accepted",
  "task_id": "6f3a...",
  "task_name": "api.tasks.ingest.ingest_sample_bundle",
  "queue": "ingest"
}
```

Poll status:

```bash
curl -sS "${BASE_URL}/api/v1/internal/tasks/${TASK_ID}" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}"
```

The async upload route stores uploaded YAML/data files in a durable staging
directory before enqueueing the task. The worker removes that staging directory
after the ingest task finishes or fails.

## Admin ingest workspace

The Admin Ingest Workspace is a UI wrapper around the async upload endpoint.
Operators provide:

- one `coyote3.yaml` / `*.coyote3.yaml` manifest
- optional data files referenced by the manifest
- `update_existing` when the manifest should replace data for an existing sample
- `increment` when a new unique sample name should be generated from the case id

The UI submits multipart form data to:

```text
POST /api/v1/internal/ingest/sample-bundle/upload/async
```

The response returns a Celery `task_id`. The workspace polls:

```text
GET /api/v1/internal/tasks/{task_id}
```

and displays worker state, completion status, errors, and the final ingest result.
This is the supported browser workflow for manual operator-triggered ingestion.

## Folder watcher ingest

Compose also defines a Celery beat scheduler (`coyote3_beat`,
`coyote3_dev_beat`, `coyote3_stage_beat`, and `coyote3_test_beat`). When
`COYOTE3_INGEST_WATCH_ENABLED=1`, beat periodically enqueues
`api.tasks.ingest.ingest_watch_directory_once`, which scans
the fixed `/data/coyote3/copied_sample_files/yaml` directory for `coyote3.yaml`.

Watcher settings:

- `/data/coyote3/copied_sample_files/yaml`: fixed root folder scanned recursively.
- `COYOTE3_INGEST_WATCH_FILENAME`: manifest filename. Defaults to `coyote3.yaml`.
- `COYOTE3_INGEST_WATCH_INTERVAL_SECONDS`: beat interval. Defaults to `30`.
- `COYOTE3_INGEST_WATCH_UPDATE_EXISTING`: pass `allow_update=true` to sample ingest.
- `COYOTE3_INGEST_WATCH_INCREMENT`: pass `increment=true` to sample ingest.
- `COYOTE3_INGEST_DONE_SUFFIX`: success marker suffix. Defaults to `.done`.
- `COYOTE3_INGEST_FAILED_SUFFIX`: failure marker suffix. Defaults to `.failed`.

The Compose deployment mounts `COYOTE3_DATA_HOST_ROOT` at `/data` and at the
same original absolute path in ingest-capable containers. Pipeline manifests may
therefore retain absolute paths below that host root; those paths are persisted
unchanged in `samples.files.<key>.path`. Relative manifest paths and absolute
`/data/...` paths are also supported.

Pipeline identity fields are normalized before any ASP/ASPC lookup:

| Pipeline field | Internal field | Notes |
| --- | --- | --- |
| `assay` | `asp_id` | Normalized to the canonical lowercase ASP identifier. |
| `subpanel` | `subpanel_id` | Normalized to the canonical lowercase subpanel identifier. |
| `profile` | `environment` | Normalized as the environment identifier. |
| `sequencing_technology` | `platform` | Normalized against configured platform values. |

Supplying both names is allowed only when their values agree. All internal
services use only the right-hand canonical field names after this boundary.

Relative file paths inside each manifest are resolved from that manifest's
directory. After successful ingest, the watcher renames the manifest to
`coyote3.yaml.done`; failed manifests are renamed to `coyote3.yaml.failed` so
they do not loop continuously.

The success marker covers the required clinical transaction: the sample and
every declared analysis resource have been validated, persisted, and marked
`ready`. Optional public knowledgebase enrichment is queued only after that
marker is written. A slow or unavailable external service cannot hold the
watch-folder lock, leave a successful manifest pending, or turn a ready sample
into a failed ingest.

The watcher is protected by a non-overlap lock. If a previous scan is still
parsing or writing a sample bundle when the next beat tick fires, the newer task
returns `skipped` with `reason=already_running` and does not touch any manifest
files.

## Compose Mongo profile

The Compose Mongo service is optional. By default, API and worker containers use
the configured `MONGO_URI`, which can point at a local or managed MongoDB. Start
the bundled Mongo only when needed:

```bash
docker compose -f deploy/compose/docker-compose.dev.yml --profile with-mongo up -d
```

Without `--profile with-mongo`, only Redis, API, frontend/docs, Celery worker,
and Celery beat are included in the stack.

## Route commands (full examples)

Set runtime variables once:

```bash
export BASE_URL="http://${COYOTE3_HOST:-localhost}:${COYOTE3_PORT:-8804}"
# Option A: existing bearer token
export API_BEARER_TOKEN="<YOUR_API_BEARER_TOKEN>"

# Option B: login via CLI helper
${PYTHON_BIN:-python} scripts/api_login.py \
  --base-url "${BASE_URL}" \
  --mode password \
  --username "admin@your-center.org" \
  --password "CHANGE_ME" \
  --print-token
```

One-shot ordered seeding (required + optional baseline collections):

```bash
scripts/bootstrap_center_collections.sh \
  --api-base-url "${BASE_URL}" \
  --bearer-token "${API_BEARER_TOKEN}" \
  --seed-file api/config/bootstrap/demo_center \
  --reference-seed-data api/config/bootstrap/rbac \
  --reference-seed-data api/config/bootstrap/reference \
  --with-optional
```

Behavior:

- Default mode retries a failed collection seed once with `ignore_duplicates=true`.
- Add `--skip-existing` to always seed in duplicate-tolerant mode.
- Add `--strict-no-retry` to fail immediately on first error.

Seed source policy for a new deployment:

- The application-owned RBAC catalog is `api/config/bootstrap/rbac`. It installs
  every bundled permission policy and built-in role only during explicit
  first-run bootstrap or explicit upgrade synchronization.
- `api/config/bootstrap/demo_center` provides synthetic ASP, ASPC, and ISGL
  records for installation verification. Replace these with reviewed center
  definitions before clinical use.
- HGNC, VEP metadata, and other reference collections are center-supplied data;
  they are not copied from test fixtures during a production bootstrap.
- Keep center seed changes deterministic and version-controlled in the center's
  private deployment configuration.
- `asp_configs` documents are contract-driven and must carry typed `filters`,
  `analysis_types`, and `reporting` objects. Query behavior is derived from those
  typed sections and the domain query builders; arbitrary top-level Mongo query
  overrides are not part of the supported ingest contract.
  CNV behavior is configured with `filters.cnv_*` keys.
  Fusion behavior is configured with `filters.fusion_*` keys.

Validate assay consistency before ingesting sample bundles:

```bash
${PYTHON_BIN:-python} scripts/validate_assay_consistency.py \
  --seed-file api/config/bootstrap/demo_center \
  --yaml demo_data/ingest/generic_case_control.yaml
```

The DNA demo YAML intentionally omits `database_versions`. DNA VCF ingest
captures the curated `database_versions` snapshot from the `##VEP=` header.
The manifest may provide `database_versions` only as an explicit override or
supplement; a supplied value takes precedence for its matching key. The stored
keys are limited to `assembly`, `clinvar`, `cosmic`, `dbsnp`, `ensembl`,
`gencode`, `genebuild`, `gnomad`, `hgmd_public`, `polyphen`, `sift`, and `vep`.

DNA ingest writes two coordinated records for each small variant:

- The sample-local variant row stores only the clinical display anchor in
  `INFO.selected_CSQ`.
- The global `anno_vep` vault stores all parsed transcript summaries by
  `simple_id_hash` and `vep_version`.

!!! info "Transcript vault"

    `anno_vep` is version tagged. A manual transcript change for a variant
    reads from the exact VEP version recorded on the sample and then updates the
    sample-local display anchor. This keeps transcript switching deterministic
    across VEP releases while keeping the variant table compact.

Every transcript summary in `anno_vep.CSQ` is validated by the
`VepAnnoTranscriptDoc` contract. Besides the VEP fields used for review
(`Feature`, `HGVSc`, `HGVSp`, `Consequence`, `IMPACT`, `EXON`, `INTRON`,
`SIFT`, `PolyPhen`, and `CADD_PHRED`), Coyote3 enriches each row with:

- `transcript_tags`: compact source markers for NCBI MANE Plus Clinical,
  Ensembl MANE Plus Clinical, NCBI MANE Select, Ensembl MANE Select, and VEP
  canonical evidence.
- `canonical_source`: the source that made the transcript canonical for the
  current review row.
- `is_canonical`: a normalized boolean for table rendering.

SIFT, PolyPhen, CADD, and related prediction values are transcript-level VEP
outputs, so they are versioned with the transcript consequence row in
`anno_vep.CSQ[]` rather than duplicated into a separate collection. The sample
document stores the source-version snapshot under `samples.database_versions`
for `sift`, `polyphen`, `vep`, and the other configured reference databases.

Manual transcript selection is exposed through:

Automatic selected-transcript priority is deterministic:

1. NCBI/RefSeq MANE Plus Clinical
2. Ensembl MANE Plus Clinical
3. NCBI/RefSeq MANE Select
4. Ensembl MANE Select
5. VEP canonical protein-coding transcript
6. first protein-coding transcript
7. first available transcript

Within each priority, consequences are considered in `HIGH`, `MODERATE`, `LOW`,
then `MODIFIER` impact order. HGNC ID is the primary gene identity; approved,
previous, and alias symbols are lookup paths to the same HGNC record.

```http
PATCH /api/v1/samples/{sample_id}/small-variants/{var_id}/selected-transcript
```

Request body:

```json
{
  "feature_id": "ENST00000359995"
}
```

The endpoint requires small-variant management permission and returns the
standard sample-change payload used by the UI to refresh the detail view.

This validator checks:

- assay references across `samples`, `blacklist`, `insilico_genelists`
- seed document contract shape (`*.json` arrays of objects only)
- metadata field typing (`created_on`/`updated_on` ISO-8601 strings, numeric `version`)
- rejection of Mongo Extended JSON wrappers (`$date`, `$oid`) in seed files
- required baseline governance/config presence (`roles`, `permissions`)
- `asp_configs` (`aspc_id` format, assay/environment consistency)
- `insilico_genelists` (`assays` and `assay_groups` consistency)
- bootstrap dependencies (`roles -> permissions`, `users -> roles`)

Discover supported collection-ingest contracts:

```bash
curl -sS "${BASE_URL}/api/v1/internal/ingest/collections" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}"
```

### 1) Seed one collection document

Route:

- `POST /api/v1/internal/ingest/collection`

Command:

```bash
curl -sS -X POST "${BASE_URL}/api/v1/internal/ingest/collection" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<'JSON'
{
  "collection": "asp_configs",
  "document": {
    "aspc_id": "assay_1_base_production",
    "asp_id": "assay_1",
    "subpanel_id": "base",
    "environment": "production",
    "asp_group": "hematology",
    "asp_category": "dna",
    "analysis_types": ["SNV", "CNV"],
    "display_name": "assay_1 production",
    "filters": {
      "min_freq": 0.05,
      "max_freq": 1.0,
      "max_control_freq": 0.05,
      "max_popfreq": 0.01,
      "snvlists": [],
      "cnvlists": []
    },
    "reporting": {
      "report_sections": ["SNV", "CNV"],
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
curl -sS -X POST "${BASE_URL}/api/v1/internal/ingest/collection/bulk" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<'JSON'
{
  "collection": "permissions",
  "documents": [
    {"permission_id": "samples:read", "label": "Read samples"}
  ]
}
JSON
```

### 2b) Update or upsert one document

Route:

- `PUT /api/v1/internal/ingest/collection`

Command:

```bash
curl -sS -X PUT "${BASE_URL}/api/v1/internal/ingest/collection" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<'JSON'
{
  "collection": "asp_configs",
  "match": {"aspc_id": "assay_1_base_production"},
  "document": {
    "aspc_id": "assay_1_base_production",
    "asp_id": "assay_1",
    "subpanel_id": "base",
    "environment": "production",
    "asp_group": "hematology",
    "asp_category": "dna",
    "analysis_types": ["SNV", "CNV"],
    "display_name": "assay_1 production",
    "filters": {
      "min_freq": 0.05,
      "max_freq": 1.0,
      "max_control_freq": 0.05,
      "max_popfreq": 0.01,
      "snvlists": [],
      "cnvlists": []
    },
    "reporting": {
      "report_sections": ["SNV", "CNV"],
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
curl -sS -X POST "${BASE_URL}/api/v1/internal/ingest/collection/upload" \
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
curl -sS -X POST "${BASE_URL}/api/v1/internal/ingest/sample-bundle" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<JSON
{
  "yaml_content": $(${PYTHON_BIN:-python} - <<'PY'
import json
from pathlib import Path
print(json.dumps(Path("demo_data/ingest/generic_case_control.yaml").read_text(encoding="utf-8")))
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
curl -sS -X POST "${BASE_URL}/api/v1/internal/ingest/sample-bundle/upload" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  -F "yaml_file=@demo_data/ingest/generic_case_control.yaml;type=text/yaml" \
  -F "data_files=@demo_data/ingest/generic_case_control.final.filtered.vcf" \
  -F "data_files=@demo_data/ingest/generic_case_control.cnvs.merged.json" \
  -F "data_files=@demo_data/ingest/generic_case_control.cov.json" \
  -F "data_files=@demo_data/ingest/generic_case_control.modeled.png" \
  -F "increment=true" \
  -F "update_existing=false"
```

Rules:

- Keep flat file path values in YAML (`vcf_files`, `cnv`, `cov`,
  `fusion_files`, etc.) as source paths.
- Upload matching files in the same request using `data_files`.
- Matching is done by exact filename value from YAML or by basename.
- Backend stages uploaded files temporarily, parses them, ingests to DB, and removes staged files after request completion.
- Uploaded runtime files are hashed (`sha256`) and persisted on the sample as `uploaded_file_checksums`.

### 4b) Internal metrics endpoint (Prometheus text format)

Route:

- `GET /api/v1/internal/metrics`

Command:

```bash
curl -sS "${BASE_URL}/api/v1/internal/metrics" \
  -H "X-Internal-Token: ${INTERNAL_API_TOKEN}"
```

### Dependent analysis writes

Dependent SNV, CNV, fusion, translocation, coverage, biomarker, and profile
writes are internal stages of complete sample-bundle ingestion. They are not a
separate public ingest operation. Submit the full manifest through a sample
bundle endpoint with `update_existing=true` when an existing sample must be
reloaded. This preserves one validation, readiness, rollback, and audit
boundary and prevents a caller from leaving a sample partially refreshed.

## Authentication and authorization

- Ingest/collection internal endpoints require authenticated API user session and RBAC.
- Internal ingest endpoints require the `internal.ingest:manage` permission.
- `update_existing=true` on sample-bundle requires authenticated user with `sample:edit:own` permission.
- The Admin UI ingestion workspace (`/admin/ingest`) uses the same
  `internal.ingest:manage` permission.

The generic collection-ingest routes are intentionally more privileged than
normal resource-management routes. Every collection operation through this
interface requires `internal.ingest:manage`. User, role, permission-policy,
ASP, ASPC, ISGL, and sample-linked collection operations additionally enforce
the corresponding create/edit permission documented in
[Collection Operations and Permissions](collection_operations_and_permissions.md).

Normal administrative routes continue to enforce their resource-specific
permissions, such as `user:create`, `assay.panel:edit`, or
`gene_list.insilico:view`. Possessing one of those narrower permissions does
not authorize arbitrary collection ingestion.

## First-time center bootstrap order

Use this order for a clean deployment at a new center.

1. Create Mongo infrastructure users.
   - Root/admin user (`MONGO_ROOT_*`) and app user (`MONGO_APP_*`).
   - Compose init scripts create app user only on first boot of an empty Mongo volume.
   - For existing volumes, use `mongosh` with an admin-capable URI to create/rotate the app user (see [Environments and Secrets](../operations/environments_and_secrets.md)).
2. Seed mandatory shared collections.
   - `hgnc_genes`
   - `permissions`
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
   - use a complete sample bundle with `update_existing=true` to replace an existing sample's declared analysis data

## Collection bootstrapping via API

Use collection endpoints to seed reference/config data with schema validation.

- Single: `POST /api/v1/internal/ingest/collection`
- Bulk: `POST /api/v1/internal/ingest/collection/bulk`

Recommended ordered commands for a new deployment:

1. `permissions` via `/collection` or `/collection/bulk`
2. `roles` via `/collection` or `/collection/bulk`
3. `hgnc_genes` via `/collection/bulk`
4. `vep_metadata` via `/collection/bulk`
5. first superuser via `scripts/bootstrap_local_admin.py`
6. `asp_configs` via `/collection` or `/collection/bulk`
7. `assay_specific_panels` via `/collection` or `/collection/bulk`
8. optional `insilico_genelists` and annotation knowledgebase collections

Note:

- `scripts/bootstrap_center_collections.sh` intentionally skips `users`.
- If needed, seed additional `users` later via collection endpoints or admin user management UI/API.

## Minimum required dataset (baseline)

Use this as the minimum deployment contract:

| Collection | Minimum required keys | Why required |
| --- | --- | --- |
| `permissions` | `permission_id` | RBAC policy definitions |
| `roles` | `role_id`, `level`, `permissions[]` | RBAC role resolution |
| `users` | `username`, `email`, `roles[]`, `environments[]` | Login + authorization subject (first superuser should be created by `bootstrap_local_admin.py`) |
| `asp_configs` | `aspc_id`, `asp_id`, `subpanel_id`, `environment`, `asp_group`, `asp_category`, `analysis_types[]`, `display_name`, `filters{...}`, `reporting{...}`, `is_active`, `version` | Assay+subpanel+environment runtime config |
| `assay_specific_panels` | `asp_id`, `assay_name`, `asp_group`, `is_active` | Assay metadata/UI wiring |
| `insilico_genelists` | `isgl_id`, `diagnosis`, `assays[]`, `assay_groups[]`, `genes[]`, `is_active` | Panel/list filtering logic |
| `hgnc_genes` | `hgnc_id`, `hgnc_symbol` | Gene metadata and symbol mapping |

Managed-admin form source:

- For ASP/ASPC/ISGL/users/roles/permissions, admin UI forms use backend-generated schemas from contracts (`api/contracts/managed_ui_schemas.py`).
- ASP, ASPC, and ISGL start at `version: 1`. Each edit writes a successor
  document with the same business identifier and the next version, then retires
  the previous active revision. Users, roles, and permissions instead update in
  place and increment `version`. Neither model stores embedded delta arrays;
  managed mutations are also recorded in audit events.

Assay-group contract:

- `asp_group` is a fixed software taxonomy defined in
  `api/config/assay_groups.py`.
- Allowed values are `tumwgs`, `wts`, `hematology`, `myeloid`, `lymphoid`,
  `solid`, `fusion`, `fusionrna`, and `pgx`.
- `asp_family` is separate: use `panel-dna`, `panel-rna`, `wgs`, or `wts` for
  sequencing-design classification. `asp_category` is separately `dna` or
  `rna`, and `subpanel_id` identifies the in-silico target subset within the
  selected design panel.
- Centers may register any ASP they need, but each ASP and ASPC must use one
  of the fixed assay groups.
- Adding a group requires a reviewed product release and migration of affected
  clinical records; it is not an admin-side data change.

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
  - `local`
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
    "name": "seed_sample",
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
  "yaml_content": "name: seed_sample\nassay: assay_1\n...",
  "update_existing": false
}
```

## Collection insert examples

### Single document

```json
{
  "collection": "variants",
  "document": {
    "SAMPLE_ID": "sample_oid_seed",
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
    {"SAMPLE_ID": "sample_oid_seed", "chr": "7", "start": 1, "end": 2},
    {"SAMPLE_ID": "sample_oid_seed", "chr": "12", "start": 3, "end": 4}
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
- `hgnc_genes`

## Test fixtures for ingestion

- `demo_data/ingest/*`
- `demo_data/collections/all_collections_dummy` (automated tests only; not a deployment seed)

## Client example (Python)

```python
import httpx

base = "http://localhost:6801"
headers = {"Authorization": "Bearer YOUR_API_BEARER_TOKEN"}

payload = {
    "spec": {
        "name": "seed_sample",
        "assay": "assay_1",
        "profile": "test",
        "genome_build": 38,
        "vcf_files": "/app/demo_data/ingest/generic_case_control.final.filtered.vcf",
        "cnv": "/app/demo_data/ingest/generic_case_control.cnvs.merged.json",
        "cov": "/app/demo_data/ingest/generic_case_control.cov.json",
    },
    "update_existing": False,
}

response = httpx.post(
    f"{base}/api/v1/internal/ingest/sample-bundle",
    json=payload,
    headers=headers,
    timeout=120.0,
)
response.raise_for_status()
print(response.json())
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
| `aspc_id environment segment must match environment` | `aspc_id` and `environment` mismatch | Use the center ASPC identifier format and keep `environment`, `asp_id`, and `subpanel_id` aligned with the document identity |
| `403 Forbidden` on update mode | User missing `sample:edit:own` permission | Add `sample:edit:own` to an assigned role |
