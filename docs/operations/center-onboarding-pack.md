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
  --compose-file deploy/compose/docker-compose.stage.yml
```

This validates:

- required secrets present and non-placeholder
- compose renders successfully
- mandatory runtime keys exist
- numeric port values are valid

## 3. Start stack

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_stage_env \
  -f deploy/compose/docker-compose.stage.yml \
  up -d --build
```

If Mongo volume already existed before first deploy, ensure app DB user is present:

```bash
python scripts/mongo_bootstrap_users.py \
  --mongo-uri "mongodb://${MONGO_ROOT_USERNAME}:${MONGO_ROOT_PASSWORD}@localhost:${COYOTE3_STAGE_MONGO_PORT:-8008}/admin?authSource=admin" \
  --app-db "${COYOTE3_DB:-coyote3}" \
  --app-user "${MONGO_APP_USER}" \
  --app-password "${MONGO_APP_PASSWORD}"
```

## 4. Seed baseline collections in order

Seed using `POST /api/v1/internal/ingest/collection` or `/bulk` in this order:

1. `permissions`
2. `roles`
3. `users` (local application users; include at least one admin-capable account)
4. `asp_configs`
5. `assay_specific_panels`
6. `insilico_genelists`
7. `refseq_canonical` (required before DNA sample-bundle ingest)
8. `hgnc_genes` (required for gene metadata/UI endpoints)

Optional but recommended next:

- `civic_genes`, `civic_variants`, `oncokb_genes`, `oncokb_actionable`, `brcaexchange`, `iarc_tp53`, `cosmic`, `vep_metadata`

See payload examples in [API / Ingestion API](../api/ingestion-api.md).

Or run one-shot bootstrap command:

```bash
scripts/bootstrap_center_collections.sh \
  --api-base-url "http://${COYOTE3_HOST:-localhost}:${COYOTE3_STAGE_API_PORT:-8006}" \
  --internal-token "${INTERNAL_API_TOKEN}" \
  --seed-file tests/fixtures/db_dummy/all_collections_dummy.json \
  --with-optional
```

## 5. Validate ingestion inputs

```bash
python scripts/validate_ingest_spec.py \
  --yaml tests/data/ingest_demo/generic_case_control.yaml \
  --check-files --json
```

## 6. Run end-to-end smoke ingest

```bash
scripts/center_smoke.sh \
  --api-base-url "http://${COYOTE3_HOST:-localhost}:${COYOTE3_STAGE_API_PORT:-8006}" \
  --internal-token "$INTERNAL_API_TOKEN" \
  --yaml-file tests/data/ingest_demo/generic_case_control.yaml
```

## 7. Verify UI/API

- API health: `GET /api/v1/health`
- Open UI and login using provisioned user
- Verify sample appears and related findings pages load

## 8. Next hardening steps

Use:

- [Minimum Production Baseline](minimum-production-baseline.md)
- [First Day Runbook](first-day-runbook.md)
- [Deployment Runbook (Subsequent Updates)](deployment-runbook.md)
