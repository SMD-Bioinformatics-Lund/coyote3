# Codebase Map

## Top-level directories

- `api/`: FastAPI backend
- `coyote/`: Flask UI app
- `deploy/compose/`: compose stacks for prod/dev/stage
- `deploy/env/`: env templates
- `scripts/`: operational/testing/migration helpers
- `tests/`: unit/api/integration/contract/ui tests and fixtures
- `docs/`: project documentation

## Important backend files

- `api/main.py`: FastAPI app construction
- `api/settings.py`: runtime settings behavior
- `api/lifecycle.py`: startup/shutdown lifecycle
- `api/services/ingest/`: sample bundle ingestion package (`service.py`, `parsers.py`, `helpers.py`)
- `api/services/admin_resource/`: admin resource management (panels, genelists, assay configs, samples)
- `api/services/dna/`: DNA variant analysis (`variant_analysis.py`, `payloads.py`, `export.py`, `structural_variants.py`, `cnv.py`, `translocations.py`, `small_variants.py`)
- `api/services/rna/`: RNA expression and fusion analysis (`expression_analysis.py`, `fusions.py`)
- `api/services/accounts/`: user and role management (`user_admin.py`, `role_admin.py`, `permissions.py`, `common.py`, `user_profile.py`)
- `api/services/sample/`: sample catalog and workflows (`catalog.py`, `sample_lookup.py`, `coverage.py`)
- `api/services/classification/`: variant interpretation (`tiering.py`, `variant_annotation.py`)
- `api/services/reporting/`: report generation (`report_builder.py`)
- `api/services/dashboard/`: dashboard analytics (`analytics.py`)
- `api/services/biomarker/`: biomarker workflows (`biomarker_lookup.py`)
- `api/contracts/schemas/registry.py`: collection contract registry

## Important UI files

- `wsgi.py`: Flask entrypoint
- `coyote/blueprints/*`: per-domain views
- `coyote/templates/*`: server-rendered HTML

## Infra and deployment

- `deploy/compose/docker-compose.yml`: prod-style stack
- `deploy/compose/docker-compose.dev.yml`: dev stack
- `deploy/compose/docker-compose.stage.yml`: stage stack
- `deploy/compose/mongo-init/create-app-user.js`: mongo app-user bootstrap
