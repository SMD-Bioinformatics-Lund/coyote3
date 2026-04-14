# Data Contracts And Collection Models

## API contracts

Request/response contracts live in `api/contracts/*.py` and should be treated as API boundary schema.

## DB contracts

`api/contracts/schemas/` defines model validation for Mongo collection documents, grouped by domain:

- `samples.py`
- `dna.py`
- `rna.py`
- `assay.py`
- `governance.py`
- `reference.py`
- `registry.py`

Managed admin UI schemas for core resources are backend-owned and generated from
contract models (not read from DB schema documents):

- `api/contracts/managed_resources.py`
- `api/contracts/managed_ui_schemas.py`

Admin create/edit pages use one canonical contract per resource and render
fields directly from backend-provided schema payloads. The UI does not provide
runtime schema switching.

Design principles:

- collection document shapes are defined in Pydantic contracts
- write paths validate and normalize against those contracts before any DB write
- nested structures are modeled explicitly (`INFO.CSQ`, `filters`, coverage gene trees, etc.)
- seed fixtures in `tests/fixtures/db_dummy/all_collections_dummy` use plain JSON contract shape (no Mongo Extended JSON wrappers)

Sample ingestion contract ownership:

- `api/contracts/schemas/samples.py` defines DNA/RNA ingest file-key groups and source-path keys
- `api/services/ingest/service.py` is the public ingest service and consumes those schema-defined constants directly, with helper modules in the same package handling parsing, dependent writes, and updates
- sample documents persist canonical file path fields from the ingest payload
- dependent writes use registry-owned mappings in `api/contracts/schemas/registry.py`

## Validation flow

- internal ingest normalizes and validates documents via collection contracts in `api/contracts/schemas/registry.py`
- admin create/update for ASP, ASPC, ISGL, users, roles, and permissions validates via collection contracts before DB write
- managed admin resource-to-schema/collection mapping is centralized in `api/contracts/managed_resources.py`
- unsupported collection names fail fast
- invalid shape fails before DB write

## Adding a new collection model

1. Create Pydantic model class
2. Register in `api/contracts/schemas/registry.py::COLLECTION_MODEL_ADAPTERS`
3. Add tests for valid/invalid payloads
4. If ingestion uses it, validate before insert

## Versioning guidance

- Persist `version` and `version_history` on managed resources.
- Increment `version` on update.
- Append `version_history` entries on create/update.
- Evolve contracts intentionally and keep DB writes contract-valid at all times.

## Fixture-driven validation

Use:

- `tests/fixtures/db_dummy/all_collections_dummy`
- `tests/unit/test_db_dummy_fixture.py`
- `scripts/validate_assay_consistency.py`

to prevent drift between contracts and example documents.
