# Operational Maintenance and Quality Verification

This document lists the routine checks for code quality, seed integrity, and environment validation.

## Pre-Release Quality Check

Run the contract and logic checks before pushing changes.

```bash
# Run project-wide integrity verification
PYTHON_BIN="$(command -v python)" bash scripts/check_contract_integrity.sh
```

Checks covered:
- import integrity
- removal of stray `print()` calls in runtime code
- logging and error-message checks
- seed and contract consistency
- documentation build checks

## Seed Consistency

Validate seed data and cross-collection assay relationships before using them.

```bash
# Validate core seed structures and assay relations
.venv/bin/python scripts/validate_assay_consistency.py \
  --seed-file tests/fixtures/db_dummy/all_collections_dummy \
  --reference-seed-data tests/data/seed_data \
  --validate-all-contracts
```

## Bootstrap Command

Example staging command:

```bash
scripts/center_first_run.sh \
  --env-file .coyote3_stage_env \
  --compose-file deploy/compose/docker-compose.stage.yml \
  --api-base-url "http://localhost:8806" \
  --admin-username "admin.coyote3" \
  --admin-email "admin@coyote3.local" \
  --admin-password "ENFORCED_SECRET" \
  --seed-file tests/fixtures/db_dummy/all_collections_dummy \
  --seed-data-pack tests/data/seed_data \
  --yaml-file tests/data/ingest_demo/generic_case_control.yaml \
  --with-optional
```

## Audit and Logging

### Logging Integrity
Use structured logging:
- add operation-specific metadata
- keep exception traces with `exc_info=True`
- do not use stdout `print()` for runtime telemetry

### Audit Metadata Persistence
Documents created through administrative or clinical actions must keep an audit trail:
- `created_by` / `updated_by`: Explicit identity of the originating user.
- `created_on` / `updated_on`: Standardized UTC (ISO-8601) timestamps.

## Integrated Operational Assets

Use these related documents for detailed procedures:
- [Initial Deployment Checklist](initial_deployment_checklist.md)
- [Center Deployment Guide](center_deployment_guide.md)
- [Quality Engineering and Validation Standards](../testing/testing_and_quality.md)
- [Collection Contract Reference](../api/collection_contracts.md)
