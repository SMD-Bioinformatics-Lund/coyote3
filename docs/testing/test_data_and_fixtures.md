# Validation Datasets and Test Fixtures

This document defines the authoritative management and structure of the validation datasets and test fixtures utilized across the platform's engineering and onboarding lifecycles.

## Fixture Infrastructure

Validation assets are organized into standardized repositories to support isolated testing requirements:

- `tests/data/ingest_demo/`: Optimized clinical artifacts for end-to-end ingestion validation.
- `tests/fixtures/db_dummy/`: Canonical document templates for all persistent collection contracts.
- `tests/fixtures/api/`: Programmatic fixture orchestrators and API payload snapshots.

## Canonical Ingestion Datasets

The `tests/data/ingest_demo` repository contains strictly sanitized genomic artifacts used for validating analytic ingestion pipelines. These datasets consist of:
- Standardized VCF (Variant) structures.
- Structural JSON definitions for CNV and Coverage segments.
- Modeled visual assets (PNG) for reporting verification.
- Validated YAML ingestion manifests.

**Security Mandate**: All datasets maintained within the public repository must be purged of Protected Health Information (PHI) and clinical patient identifiers.

## Administrative Seeding Templates

The `db_dummy` repository provides a comprehensive diagnostic seed for organizational bootstrapping:

- **Location**: `tests/fixtures/db_dummy/all_collections_dummy`
- **Application**: Recommended as the initial configuration seed for external centers. It utilizes neutral assay nomenclature to prevent organizational configuration bias during the initial installation phase.

### Validation Commands

To verify the integrity of the database seeding templates, execute the following diagnostic command:

```bash
PYTHONPATH=. python -m pytest -q tests/unit/test_db_dummy_fixture.py
```

## Contractual Consistency Gates

To prevent schema drift between code models and persistent database records, the platform enforces an automated integrity gate:

```bash
# Execute contract consistency validation
PYTHON_BIN="$(command -v python)" bash scripts/check_contract_integrity.sh
```

This protocol programmatically verifies:
- Synchronization between Pydantic models and seeded document structures.
- Relational consistency across Assay, ASP, and configuration resource sets.
- Automatic regeneration of the standard Collection Contract documentation from the active backend logic.

## Maintenance Requirements for Validation Assets

Submissions to the fixture repository must adhere to the following engineering constraints:

1. **Minimize Footprint**: Limit fixture datasets to the smallest volume necessary to satisfy the specific test requirement.
2. **Clinical Anonymization**: Absolute removal of all clinical identifiers is non-negotiable.
3. **Structural Fidelity**: Preserve realistic data shapes, specifically within complex nested fields, to ensure valid contract testing.
4. **Contract Verification**: All fixture updates must pass the full `check_contract_integrity.sh` protocol before being merged into the master branch.
