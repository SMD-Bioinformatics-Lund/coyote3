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
- `api/services/internal_ingest_service.py`: sample bundle ingestion
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
