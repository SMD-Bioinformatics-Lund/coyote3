# Test Data And Fixtures

## Fixture directories

- `tests/data/ingest_demo/`: compact sample ingestion artifacts
- `tests/fixtures/db_dummy/`: collection-level document examples
- `tests/fixtures/api/`: API fixture helpers and snapshots

## Ingest demo fixture set

Use the generic files in `tests/data/ingest_demo` for API ingestion testing:

- VCF
- CNV JSON
- COV JSON
- modeled PNG
- YAML input

These fixtures are sanitized and safe for public repo use.

## DB dummy fixture

`tests/fixtures/db_dummy/all_collections_dummy` contains representative docs for all registered collection contract models.

`tests/fixtures/db_dummy/all_collections_dummy` is the recommended
first-time onboarding seed template for external centers (neutral assay names).

Validation test:

```bash
PYTHONPATH=. python -m pytest -q tests/unit/test_db_dummy_fixture.py
```

## Fixture maintenance rules

1. Keep fixtures small
2. Remove patient identifiers
3. Preserve realistic shape for nested fields
4. Validate against contracts after updates
