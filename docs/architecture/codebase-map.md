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
- `api/runtime_setup.py`: runtime setup and provider selection
- `api/deps/handlers.py`: low-level access to the shared runtime store
- `api/deps/services.py`: backend service factory/composition root
- `api/extensions.py`: shared runtime store and backend utility registrations
- `api/services/ingest/`: sample bundle ingestion package
  - `service.py`: public service entrypoint and stable caller/test seam
  - `parsers.py`: DNA/RNA file parsing
  - `helpers.py`: sample-name and metadata normalization
  - `collection_writes.py`: contract-validated collection insert/upsert helpers
  - `dependent_writes.py`: dependent analysis document writes and rollback helpers
  - `sample_updates.py`: update/rename/update-payload helpers
- `api/services/resources/`: managed resource workflows (`asp.py`, `isgl.py`, `aspc.py`, `sample.py`)
- `api/services/dna/`: DNA analysis package
  - `variant_analysis.py`: public small-variant service entrypoint
  - `payloads.py`: read payload builders
  - `variant_exports.py`: export-row and CSV helpers
  - `variant_state.py`: flag/state and CNV lookup helpers
  - `variant_classification.py`: classification/tiering helpers
  - `variant_comments.py`: comment-write helpers
  - `structural_variants.py`: CNV/translocation service
- `api/services/rna/`: RNA expression and fusion analysis (`expression_analysis.py`, `fusions.py`)
- `api/services/accounts/`: user and role management (`users.py`, `roles.py`, `permissions.py`, `common.py`, `user_profile.py`)
- `api/services/sample/`: sample catalog and workflows (`catalog.py`, `sample_lookup.py`, `coverage.py`)
- `api/services/classification/`: variant interpretation (`tiering.py`, `variant_annotation.py`)
- `api/services/reporting/`: report generation (`report_builder.py`)
- `api/services/dashboard/`: dashboard analytics (`analytics.py`)
- `api/services/biomarker/`: biomarker workflows (`biomarker_lookup.py`)
- `api/services/common/change_payload.py`: canonical change-response payload builder for write endpoints
- `api/routers/change_helpers.py`: shared router helpers for common write/change route patterns
- `api/contracts/schemas/registry.py`: collection contract registry
- `api/infra/mongo/adapter.py`: canonical Mongo adapter entrypoint
- `api/infra/mongo/handlers/`: collection-scoped Mongo handlers with human-readable module names
- `api/infra/knowledgebase/`: handlers and plugin registry for annotation knowledgebase collections stored in MongoDB
- `api/infra/integrations/ldap.py`: LDAP integration client

## Package responsibilities

### `api/routers`

- validates request shape at the HTTP boundary
- applies auth/access dependencies
- calls injected services
- should not construct business logic from `store` directly

### `api/deps`

- `handlers.py`: tiny layer for low-level store access
- `services.py`: builds service objects from the shared store

### `api/services`

- owns use-case and orchestration logic
- may combine multiple handlers
- should expose explicit constructor dependencies
- may provide `from_store(...)` helpers to keep factories concise
- when a large service is split into submodules, keep one stable public entrypoint file for callers and tests
- write endpoints should use the shared change-response helpers instead of duplicating ad hoc payload shapes

### `api/core`

- pure logic only
- formatting, normalization, query builders, models, rules
- should not import `store`

### `api/infra/mongo/handlers`

- one handler per collection
- owns Mongo-specific query shape and index-aware persistence logic

## Adding a new Mongo collection

Typical path:

1. add a schema to `api/contracts/schemas/...`
2. register it in `api/contracts/schemas/registry.py`
3. add a handler in `api/infra/mongo/handlers/`
4. register the handler in `api/infra/mongo/runtime_adapter.py`
5. use the handler from a service in `api/services/`
6. expose the service through `api/deps/services.py`
7. call the service from a router

## Important UI files

- `wsgi.py`: Flask entrypoint
- `coyote/blueprints/*`: per-domain views
- `coyote/templates/layout.html`: top-level page shell, now composed from shared includes
- `coyote/templates/includes/`: shared page shell fragments (`_site_header.html`, `_top_nav.html`, `_flash_messages.html`, `_action_modal.html`, `_layout_scripts.html`)
- `coyote/templates/components/`: reusable template fragments and macros for repeated UI patterns
- `coyote/templates/*`: server-rendered HTML

## UI structure rules

- Flask views live in `coyote/blueprints/*` and call the backend only through the web API client.
- Shared shell concerns belong in `coyote/templates/includes/`, not inlined repeatedly in page templates.
- Repeated page widgets should move into `coyote/templates/components/` as includes or macros.
- Page-specific JavaScript should prefer blueprint static files or small page-local blocks over growing `layout.html`.
- Shared static assets loaded by `layout.html` are versioned with `?v={{ APP_VERSION }}` to reduce stale browser cache after deploys.

## Infra and deployment

- `deploy/compose/docker-compose.yml`: prod-style stack
- `deploy/compose/docker-compose.dev.yml`: dev stack
- `deploy/compose/docker-compose.stage.yml`: stage stack
- `deploy/compose/mongo-init/create-app-user.js`: mongo app-user bootstrap
