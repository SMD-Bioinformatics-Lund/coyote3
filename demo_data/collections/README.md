# DB Dummy Fixture

`all_collections_dummy/` contains one `*.json` file per collection with
representative documents for Mongo collections used by the app.

These documents are synthetic examples for contract, integration, and UI
validation. They are not imported by the production first-deployment workflow.

Purpose:

- provide a single, reusable source for integration and contract tests,
- keep example data privacy-safe and generic,
- exercise nested document structures expected by ingestion and runtime code.

Contract rules:

- Shared baseline collections (`permissions`, `roles`, `users`, `asp_configs`,
  `assay_specific_panels`, `insilico_genelists`) should keep aligned key-shapes across environments.
- All business identifiers are lowercase in the curated seed baseline, except sample document IDs
  where the sample-specific identifier is intentionally preserved.
- Application-owned first-load data is maintained under `api/config/bootstrap/`.
- Seed files use plain JSON scalar values for IDs/timestamps (for example ISO-8601 datetime strings),
  not Mongo Extended JSON wrappers such as `$date` / `$oid`.
- Per-collection required/optional keys are generated from Pydantic contracts into
  `docs/api/collection_contracts.md` via:
  - `PYTHONPATH=. ${PYTHON_BIN:-python} scripts/export_collection_contracts_doc.py`
