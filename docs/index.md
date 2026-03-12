# Coyote3 Documentation

This documentation set defines the repository and its operating model. The codebase is split into two runtime applications:

- `api/`: the independent FastAPI backend and the authoritative backend contract
- `coyote/`: the Flask UI that consumes the API and renders the user-facing application

The rest of the repository supports those two applications: deployment, tests, shared utilities, and documentation.

## Operating Model

The repository is built around these structural rules:

- the API starts from `api.main:app`
- the UI starts independently and calls the API through `coyote/services/api_client/`
- backend HTTP route ownership belongs to `api/routers/`
- API contracts belong to `api/contracts/`
- Mongo runtime code belongs to `api/db/mongo/`
- automated tests protect the repository boundaries and behavior

## Recommended Reading Order

1. Start with [Architecture Overview](ARCHITECTURE_OVERVIEW.md).
2. Read [Repository Structure](architecture/repository-structure.md).
3. Read [API Architecture](architecture/API_ARCHITECTURE.md).
4. Read [API Concepts And Layering](api/concepts-and-layering.md).
5. Read [Developer Guide](development/developer-guide.md).
6. Read [Maintenance Guide](development/maintenance-guide.md).
7. Read [UI Surface And Permissions](ui/ui-surface-and-permissions.md).
8. Read [Testing Guide](testing/TESTING_GUIDE.md) before changing behavior or removing tests.
9. Read [Operations](deployment/operations.md) before changing Compose files, environment variables, or startup logic.

## Documentation Map

### Architecture

- [Architecture Overview](ARCHITECTURE_OVERVIEW.md)
- [Repository Structure](architecture/repository-structure.md)
- [API Architecture](architecture/API_ARCHITECTURE.md)
- [Security Model](SECURITY_MODEL.md)
- [Data Model](DATA_MODEL.md)
- [Traceability Matrix](TRACEABILITY_MATRIX.md)
- [Glossary](GLOSSARY.md)

### API

- [API Concepts And Layering](api/concepts-and-layering.md)
- [API Reference](api/reference.md)
- [Endpoint Catalog](api/endpoint-catalog.md)
- [Auth Login Model and Stats](AUTH_LOGIN_MODEL_AND_STATS.md)

### UI

- [User Guide](ui/user-guide.md)
- [UI Surface And Permissions](ui/ui-surface-and-permissions.md)

### Development

- [Developer Guide](development/developer-guide.md)
- [Maintenance Guide](development/maintenance-guide.md)
- [Route Implementation Guide](development/route-implementation-guide.md)
- [Extension Playbook](development/extension-playbook.md)
- [Code Style](development/code-style.md)

### Deployment

- [Operations](deployment/operations.md)
- [Release Process](deployment/release-process.md)
- [Troubleshooting](deployment/troubleshooting.md)
- [Mongo Docker Dev Runtime](deployment/mongo-docker-dev-runtime.md)
- [Patient Data Backup and Recovery](deployment/patient-data-backup-and-recovery.md)

### Testing

- [Testing Guide](testing/TESTING_GUIDE.md)
- [Testing Strategy](testing/strategy.md)

## Working Repository Model

Use this model when deciding where code belongs:

- HTTP request handling belongs in `api/routers/`
- API data contracts belong in `api/contracts/`
- backend domain and workflow logic belongs in `api/core/` and `api/services/`
- backend persistence adapters belong in `api/repositories/`, `api/infra/db/`, and `api/db/mongo/`
- UI page orchestration belongs in `coyote/blueprints/`
- UI-to-API transport belongs in `coyote/services/api_client/`
- tests belong in `tests/api/`, `tests/ui/`, `tests/integration/`, `tests/unit/`, and `tests/fixtures/`

## Rules That Keep The Repository Healthy

- Treat the API as the primary backend contract.
- Keep the UI presentation-focused.
- Do not add direct Mongo access outside `api/repositories/`, `api/infra/db/`, and `api/db/mongo/`.
- Do not add backend policy logic to Flask blueprints.
- Do not hardcode UI-to-API endpoint strings when an API client helper can own the path.
- Update docs and tests in the same change set as architecture or behavior changes.

If a new engineer does not understand what a contract, service, or repository means in this repository, the intended starting points are:

- [api/concepts-and-layering.md](api/concepts-and-layering.md)
- [architecture/API_ARCHITECTURE.md](architecture/API_ARCHITECTURE.md)
- [development/developer-guide.md](development/developer-guide.md)
