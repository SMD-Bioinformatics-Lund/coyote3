# Center Onboarding Pack

This pack is intended for a new center taking this repo and standing up Coyote3 end-to-end.

## 1. Clone and prepare environment

```bash
git clone <your-fork-or-upstream>
cd coyote3
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Select your target environment template:

```bash
cp deploy/env/example.stage.env .coyote3_stage_env
# or
cp deploy/env/example.prod.env .coyote3_env
```

Set real values for all `CHANGE_ME_*` keys.

## 2. Run preflight validation

```bash
scripts/center_preflight.sh \
  --env-file .coyote3_stage_env \
  --compose-file deploy/compose/docker-compose.stage.yml \
  --seed-file tests/fixtures/db_dummy/all_collections_dummy \
  --yaml-file tests/data/ingest_demo/generic_case_control.yaml
```

This validates:

- required secrets present and non-placeholder
- compose renders successfully
- mandatory runtime keys exist
- numeric port values are valid

For first-time center deployment, do not depend on a production DB export.
Use the bundled seed directory and adapt assay/group values to your center before bootstrap.

## 3. Start stack

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_stage_env \
  -f deploy/compose/docker-compose.stage.yml \
  up -d --build
```

If Mongo volume already existed before first deploy, ensure app DB user is present:

```bash
${PYTHON_BIN:-python} scripts/mongo_bootstrap_users.py \
  --mongo-uri "mongodb://${MONGO_ROOT_USERNAME}:${MONGO_ROOT_PASSWORD}@localhost:${COYOTE3_STAGE_MONGO_PORT:-8808}/admin?authSource=admin" \
  --app-db "${COYOTE3_DB:-coyote3}" \
  --app-user "${MONGO_APP_USER}" \
  --app-password "${MONGO_APP_PASSWORD}"
```

## 4. Bootstrap first API admin (one-time)

Create the initial local API admin used for CLI/Python/API-auth flows:

```bash
${PYTHON_BIN:-python} scripts/bootstrap_local_admin.py \
  --mongo-uri "mongodb://${MONGO_APP_USER}:${MONGO_APP_PASSWORD}@localhost:${COYOTE3_STAGE_MONGO_PORT:-8808}/${COYOTE3_DB:-coyote3}?authSource=${COYOTE3_DB:-coyote3}" \
  --db "${COYOTE3_DB:-coyote3}" \
  --email "admin@your-center.org" \
  --password "CHANGE_ME_ADMIN_PASSWORD" \
  --assay-group "GROUP_A" \
  --assay "ASSAY_A"
```

## 5. Seed baseline collections in order

Seed using `POST /api/v1/internal/ingest/collection` or `/bulk` in this order:

1. `permissions`
2. `roles`
3. `asp_configs`
4. `assay_specific_panels`
5. `insilico_genelists`
6. `refseq_canonical` (required before DNA sample-bundle ingest)
7. `hgnc_genes` (required for gene metadata/UI endpoints)

Notes:

- `users` is intentionally not seeded by `bootstrap_center_collections.sh`.
- First admin/user is created in step 4 via `bootstrap_local_admin.py` (or later via admin UI/API).
- `bootstrap_local_admin.py` now writes user audit metadata (`created_by`, `created_on`, `updated_by`, `updated_on`).
- `asp_configs` must include `is_active=true`; missing this causes sample pages to fail with "Assay config not found for sample".
- Managed admin forms (ASP/ASPC/ISGL/users/roles/permissions) are backend-generated from contracts rather than DB schema JSON.

Optional but recommended next:

- `civic_genes`, `civic_variants`, `oncokb_genes`, `oncokb_actionable`, `brcaexchange`, `iarc_tp53`, `cosmic`, `vep_metadata`

See payload examples in [API / Ingestion API](../api/ingestion-api.md).

Or run one-shot bootstrap command:

```bash
scripts/bootstrap_center_collections.sh \
  --api-base-url "http://${COYOTE3_HOST:-localhost}:${COYOTE3_STAGE_API_PORT:-8806}" \
  --username "admin@your-center.org" \
  --password "CHANGE_ME" \
  --seed-file tests/fixtures/db_dummy/all_collections_dummy \
  --with-optional
```

Behavior notes:

- By default, `bootstrap_center_collections.sh` retries one failed collection insert once with `ignore_duplicates=true`.
- Use `--skip-existing` to run duplicate-tolerant mode from the start for every collection.
- Use `--strict-no-retry` if you want first error to fail immediately (CI/strict rollout mode).
- For `center_first_run.sh`, if you use `--strict-no-retry`, also pass `--skip-existing`
  because admin bootstrap runs before collection seeding and pre-creates RBAC docs.

`all_collections_dummy/` is neutral by default (`ASSAY_A`, `GROUP_A`) and
should be edited to your center's assay IDs and groups before first run.

## 6. Validate ingestion inputs

```bash
${PYTHON_BIN:-python} scripts/validate_ingest_spec.py \
  --yaml tests/data/ingest_demo/generic_case_control.yaml \
  --check-files --json
```

## 7. Run end-to-end smoke ingest

```bash
scripts/center_smoke.sh \
  --api-base-url "http://${COYOTE3_HOST:-localhost}:${COYOTE3_STAGE_API_PORT:-8806}" \
  --username "admin@your-center.org" \
  --password "CHANGE_ME" \
  --yaml-file tests/data/ingest_demo/generic_case_control.yaml
```

Notes:

- `center_smoke.sh` auto-enables `increment=true` in the submitted YAML payload, so repeated runs are idempotent (`CASE_DEMO`, `CASE_DEMO-1`, ...).
- For local Docker stacks (`localhost` API), the script stages referenced ingest files and copies them into the API container automatically.
- YAML ingest file paths must be API-runtime-visible paths (container/host where API process runs).

If this center started on an older baseline,
run one-time repair before smoke/bootstrap reruns:

```bash
${PYTHON_BIN:-python} scripts/repair_center_seed_baseline.py \
  --mongo-uri "mongodb://${MONGO_APP_USER}:${MONGO_APP_PASSWORD}@localhost:${COYOTE3_STAGE_MONGO_PORT:-8808}/${COYOTE3_DB:-coyote3}?authSource=${COYOTE3_DB:-coyote3}" \
  --db "${COYOTE3_DB:-coyote3}"
```

## One-command first-time bootstrap (recommended)

You can execute the full chain in one command:

```bash
scripts/center_first_run.sh \
  --env-file .coyote3_stage_env \
  --compose-file deploy/compose/docker-compose.stage.yml \
  --api-base-url "http://${COYOTE3_HOST:-localhost}:${COYOTE3_STAGE_API_PORT:-8806}" \
  --admin-email "admin@your-center.org" \
  --admin-password "CHANGE_ME" \
  --seed-file tests/fixtures/db_dummy/all_collections_dummy \
  --yaml-file tests/data/ingest_demo/generic_case_control.yaml \
  --with-optional \
  --skip-existing \
  --strict-no-retry
```

## 8. Verify UI/API

- API health: `GET /api/v1/health`
- Open UI and login using provisioned user
- Verify sample appears and related findings pages load

## 9. Next hardening steps

Use:

- [Minimum Production Baseline](minimum-production-baseline.md)
- [First Day Runbook](first-day-runbook.md)
- [Deployment Runbook (Subsequent Updates)](deployment-runbook.md)

Subsequent update cycles should use [Deployment Runbook (Subsequent Updates)](deployment-runbook.md)
instead of rerunning full first-time bootstrap.
