# DB Dummy Fixture

`all_collections_dummy.json` contains one or more representative documents per
Mongo collection used by the app.

`center_template_seed.json` is a center-agnostic bootstrap template using
neutral placeholders (`ASSAY_A`, `GROUP_A`, `DIAGNOSIS_A`) intended for
first-time onboarding at external centers.

Purpose:

- provide a single, reusable source for integration and contract tests,
- keep example data privacy-safe and generic,
- exercise nested document structures expected by ingestion and runtime code.
