# Operational Maintenance and Quality Verification

This document provides the definitive operational checklists for establishing and maintaining platform quality, seed integrity, and environmental compliance.

## Pre-Release Quality Mandate (Daily Gate)

All changes must pass the comprehensive contract and logic verification suite before submission to the upstream repository.

```bash
# Execute project-wide integrity verification
PYTHON_BIN="$(command -v python)" bash scripts/check_contract_integrity.sh
```

**Verification Objectives**:
- **Import Integrity**: Elimination of deprecated contract paths.
- **Output Standards**: Absolute removal of un-structured `print()` statements.
- **Messaging Standards**: Enforcement of actionable diagnostic logging.
- **Contract Consistency**: synchronization of seeded assay resources with active platform logic.
- **Documentation Parity**: Automated regeneration of technical contract manuals.

## Seed Architecture and Consistency

Engineers must validate all architectural seeds and cross-collection assay relationships to prevent analytical drift.

```bash
# Validate core seed structures and assay relations
.venv/bin/python scripts/validate_assay_consistency.py \
  --seed-file tests/fixtures/db_dummy/all_collections_dummy \
  --reference-seed-data tests/data/seed_data \
  --validate-all-contracts
```

## Authorized Bootstrap Protocol (Clean Provisioning)

Standardized procedure for the initial provisioning of a clean environment (Staging context example):

```bash
scripts/center_first_run.sh \
  --env-file .coyote3_stage_env \
  --compose-file deploy/compose/docker-compose.stage.yml \
  --api-base-url "http://localhost:8806" \
  --admin-email "admin@coyote3.local" \
  --admin-password "ENFORCED_SECRET" \
  --seed-file tests/fixtures/db_dummy/all_collections_dummy \
  --seed-data-pack tests/data/seed_data \
  --yaml-file tests/data/ingest_demo/generic_case_control.yaml \
  --with-optional
```

## Operational Audit and Telemetry Standards

### Logging Integrity
Platform runtimes must adhere to structured logging standards to support forensic analysis:
- **Context Preservation**: Every log event must carry operation-specific metadata.
- **Stack Trace Retention**: Exception paths must utilize `exc_info=True` to preserve trace context.
- **Output Boundaries**: Prohibited use of stdout `print()` for clinical or operational telemetry.

### Audit Metadata Persistence
All documents generated through administrative or clinical actions must maintain a high-fidelity audit trail:
- `created_by` / `updated_by`: Explicit identity of the originating user.
- `created_on` / `updated_on`: Standardized UTC (ISO-8601) timestamps.

## Integrated Operational Assets

Maintainers must refer to the following authoritative resources for specialized operational procedures:
- **[Initial Deployment Checklist](initial_deployment_checklist.md)**: Mandated sequence for organizational onboarding.
- **[Center Deployment Guide](center_deployment_guide.md)**: Targeted guide for external infrastructure provisioning.
- **[Quality Engineering and Validation Standards](../testing/testing_and_quality.md)**: Technical specifications for the testing infrastructure.
- **[Collection Contract Reference](../api/collection_contracts.md)**: Finalized mapping of persistent data schemas.
