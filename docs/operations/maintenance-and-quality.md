# Maintenance And Quality

Use this page as the single operational checklist for code quality, seed integrity,
bootstrap validation, and environment smoke checks.

Scope note:

- Use this page as the compact command reference.
- For first-day end-to-end sequencing and rationale, use
  [Initial Deployment Checklist](initial-deployment-checklist.md) as canonical.

## Daily Quality Gate

Run the full contract/seed/quality checks before opening a PR:

```bash
PYTHON_BIN="${PYTHON_BIN:-$(command -v python)}" \
bash scripts/check_contract_integrity.sh
```

What this validates:

- no deprecated `api.contracts.db_documents` imports
- no runtime `print()` statements in `api/` + `coyote/`
- no generic `"An error occurred"` log messages
- no runtime compatibility-shim markers
- seed contract + assay consistency
- generated collection contract documentation is up to date

## Seed Integrity Checks

Validate only seed structures and cross-collection assay relations:

```bash
./.venv/bin/python scripts/validate_assay_consistency.py \
  --seed-file tests/fixtures/db_dummy/all_collections_dummy \
  --reference-seed-data tests/data/seed_data
```

Validate all registered collection contracts from the seed bundle:

```bash
./.venv/bin/python scripts/validate_assay_consistency.py \
  --seed-file tests/fixtures/db_dummy/all_collections_dummy \
  --reference-seed-data tests/data/seed_data \
  --validate-all-contracts
```

## First Bootstrap (Clean Environment)

Minimal first-bootstrap command (stage example):

```bash
scripts/center_first_run.sh \
  --env-file .coyote3_stage_env \
  --compose-file deploy/compose/docker-compose.stage.yml \
  --api-base-url "http://localhost:8806" \
  --admin-email "admin@coyote3.local" \
  --admin-password "CHANGE_ME" \
  --seed-file tests/fixtures/db_dummy/all_collections_dummy \
  --seed-data-pack tests/data/seed_data \
  --yaml-file tests/data/ingest_demo/generic_case_control.yaml \
  --with-optional
```

Credential source rule:

- For `scripts/center_first_run.sh`, pass `--admin-email` and `--admin-password` as CLI args.

Notes:

- demo assay id is `assay_1`
- demo assay group is `hematology`
- ISGL demo collection is optional and requires `--with-optional`

## Smoke Verification

Run ingest smoke after bootstrap:

```bash
bash scripts/center_smoke.sh \
  --api-base-url "http://localhost:8806" \
  --username "admin@coyote3.local" \
  --password "CHANGE_ME" \
  --yaml-file tests/data/ingest_demo/generic_case_control.yaml
```

## Logging And Audit Expectations

Runtime expectations:

- use structured logger messages with operation context
- include `exc_info=True` for exception paths that need stack traces
- avoid generic error text without collection/route context
- avoid stdout `print()` in API/UI runtime paths

Audit metadata expectations for seeded and admin-created docs:

- `created_by`
- `created_on` (UTC ISO-8601)
- `updated_by`
- `updated_on` (UTC ISO-8601)

## Related Docs

- [Initial Deployment Checklist](initial-deployment-checklist.md)
- [Center Deployment Guide](center-deployment-guide.md)
- [Testing And Quality](../testing/testing-and-quality.md)
- [Collection Contracts](../api/collection-contracts.md)
