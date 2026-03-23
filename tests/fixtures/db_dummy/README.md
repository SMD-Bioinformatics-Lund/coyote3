# DB Dummy Fixture

`all_collections_dummy/` contains one `*.json` file per collection with
representative documents for Mongo collections used by the app.

`all_collections_dummy/` is the canonical seed and contract fixture source
for first-time onboarding and test coverage.

Seeding policy:

- `permissions` and `roles` ship as a complete out-of-the-box RBAC baseline.
- Admin bootstrap collections (`asp_configs`, `assay_specific_panels`,
  `insilico_genelists`) use demo-safe neutral placeholders
  (`ASSAY_A`, `GROUP_A`, `DIAGNOSIS_A`) and are expected to be customized per center.

Purpose:

- provide a single, reusable source for integration and contract tests,
- keep example data privacy-safe and generic,
- exercise nested document structures expected by ingestion and runtime code.

Contract rules:

- Shared baseline collections (`permissions`, `roles`, `users`, `asp_configs`,
  `assay_specific_panels`, `insilico_genelists`) should keep aligned key-shapes across environments.
- `all_collections_dummy/` is the first-load seed baseline used by onboarding scripts.
- Seed files use plain JSON scalar values for IDs/timestamps (for example ISO-8601 datetime strings),
  not Mongo Extended JSON wrappers such as `$date` / `$oid`.
- Per-collection required/optional keys are generated from Pydantic contracts into
  `docs/api/collection-contracts.md` via:
  - `PYTHONPATH=. ${PYTHON_BIN:-python} scripts/export_collection_contracts_doc.py`
