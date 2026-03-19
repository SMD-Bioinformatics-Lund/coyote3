# Data Contracts And Collection Models

## API contracts

Request/response contracts live in `api/contracts/*.py` and should be treated as API boundary schema.

## DB contracts

`api/contracts/db_documents.py` defines model validation for Mongo collection documents.

Design principles:

- keep critical keys typed and validated
- allow forward-compatible keys with `extra="allow"`
- add nested models for known nested structures (`INFO.CSQ`, `filters`, coverage gene trees, etc.)

## Validation flow

- internal ingest validates documents via `validate_collection_document(collection, payload)`
- unsupported collection names fail fast
- invalid shape fails before DB write

## Adding a new collection model

1. Create Pydantic model class
2. Register in `COLLECTION_MODEL_ADAPTERS`
3. Add tests for valid/invalid payloads
4. If ingestion uses it, validate before insert

## Fixture-driven validation

Use:

- `tests/fixtures/db_dummy/all_collections_dummy.json`
- `tests/fixtures/db_dummy/center_template_seed.json`
- `tests/unit/test_db_dummy_fixture.py`

to prevent drift between contracts and example documents.
