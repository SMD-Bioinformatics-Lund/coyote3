# External Center Onboarding

This guide defines the minimum technical contract for onboarding a new center to Coyote3 with local installation.

## 1. Deployment baseline

1. Use isolated MongoDB instances per environment (`prod`, `stage`, `dev`), all with database name `coyote3`.
2. Use environment templates from `deploy/env/`.
3. Deploy using:
   - `scripts/install.sh` (prod)
   - `scripts/install.stage.sh` (stage)
   - `scripts/install.dev.sh` (dev)

## 2. Data format contract for sample ingestion

Current cron-style ingestion is driven by `scripts/import_coyote_sample.py`.

### 2.1 YAML mode (minimum required keys)

At minimum, ingestion payloads must contain:

- `name`
- `groups`
- `genome_build`
- DNA input: `vcf_files`
- RNA input: `fusion_files`

The importer resolves DNA vs RNA from provided input keys and enforces consistency during updates.

### 2.2 Sample metadata expectations

Important sample-level fields used downstream:

- `name` (sample identifier)
- `assay`
- `profile`
- `genome_build`
- optional case/control fields (`case_*`, `control_*`)

The importer writes metadata to `samples` and dependent records to domain collections.

## 3. Internal ingestion endpoint for dependent collections

To support center-local operational ingestion via API (instead of direct collection writes), Coyote3 now exposes:

- `POST /api/v1/internal/ingest/sample/upsert`
- `POST /api/v1/internal/ingest/dependents`

Auth:

- Header: `X-Coyote-Internal-Token: <INTERNAL_API_TOKEN>`

Request body:

```json
{
  "sample_id": "65f0a9d6b3f1af7d9d8c1a11",
  "sample_name": "25MD17060p-2",
  "delete_existing": true,
  "preload": {
    "snvs": [],
    "cnvs": [],
    "biomarkers": {},
    "transloc": [],
    "lowcov": [],
    "cov": {},
    "fusions": [],
    "rna_expr": {},
    "rna_class": {},
    "rna_qc": {}
  }
}
```

Response:

```json
{
  "status": "ok",
  "sample_id": "65f0a9d6b3f1af7d9d8c1a11",
  "written": {
    "snvs": 120,
    "cnvs": 3
  }
}
```

## 4. Variant identity/hash contract

During dependent ingest of SNVs, Coyote3 normalizes:

- `simple_id`
- `simple_id_hash`

This is now enforced in the internal ingest endpoint and in local fallback path of `import_coyote_sample.py`.

## 5. Cron migration path (recommended)

1. Keep existing parsing logic in `import_coyote_sample.py`.
2. Set:
   - `API_BASE_URL`
   - `INTERNAL_API_TOKEN`
   - optional `COYOTE3_INGEST_VIA_API=1` (default)
3. Let the script parse/prepare payloads as before.
4. Let dependent writes flow through `/api/v1/internal/ingest/dependents`.
5. Let sample metadata writes flow through `/api/v1/internal/ingest/sample/upsert`.

This preserves current ingest behavior while moving write authority behind API policy and logging.
