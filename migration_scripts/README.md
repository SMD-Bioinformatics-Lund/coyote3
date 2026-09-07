# Local Migration Scripts

This directory is the only approved location for one-off migration, repair, or
local data-conversion scripts.

The directory is ignored by git so center-specific migration code, sample
paths, exported payloads, and operational scratch files do not enter normal
reviews. Keep only this README tracked.

Rules:

- Do not place reusable application code here.
- Do not store secrets, patient data, full sample manifests, or exported
  production records here.
- Promote repeatable maintenance workflows into `scripts/` with tests and
  documentation.
- Name local scripts clearly, for example
  `migration_scripts/20260717-normalize-sample-documents.py`.
- Delete scripts after the migration evidence has been captured.

Use `scripts/` for supported bootstrap, backup, restore, validation, seed, and
operations commands.
