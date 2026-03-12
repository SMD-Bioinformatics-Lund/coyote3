# Coyote3 Documentation Hub

This documentation set is organized by concern so engineers, operators, and reviewers can start from the layer they own instead of reading a single long manual front to back.

## Start Here

- Architecture overview: [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md)
- API architecture: [architecture/API_ARCHITECTURE.md](architecture/API_ARCHITECTURE.md)
- Developer guide: [development/developer-guide.md](development/developer-guide.md)
- Testing guide: [testing/TESTING_GUIDE.md](testing/TESTING_GUIDE.md)
- Deployment and operations: [deployment/operations.md](deployment/operations.md)

## Architecture

- System architecture and boundaries: [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md)
- API package structure and startup: [architecture/API_ARCHITECTURE.md](architecture/API_ARCHITECTURE.md)
- Security model and RBAC: [SECURITY_MODEL.md](SECURITY_MODEL.md)
- Data model and Mongo conventions: [DATA_MODEL.md](DATA_MODEL.md)
- Requirement-to-control mapping: [TRACEABILITY_MATRIX.md](TRACEABILITY_MATRIX.md)
- Shared terminology: [GLOSSARY.md](GLOSSARY.md)

## API

- API reference: [api/reference.md](api/reference.md)
- Endpoint inventory: [api/endpoint-catalog.md](api/endpoint-catalog.md)
- Login/session model notes: [AUTH_LOGIN_MODEL_AND_STATS.md](AUTH_LOGIN_MODEL_AND_STATS.md)

## UI

- User-facing workflow and page behavior: [ui/user-guide.md](ui/user-guide.md)

## Development

- Contributor workflow and repository map: [development/developer-guide.md](development/developer-guide.md)
- Route and endpoint implementation rules: [development/route-implementation-guide.md](development/route-implementation-guide.md)
- Feature extension playbook: [development/extension-playbook.md](development/extension-playbook.md)
- Code and naming standards: [development/code-style.md](development/code-style.md)

## Deployment

- Operations manual: [deployment/operations.md](deployment/operations.md)
- Release process: [deployment/release-process.md](deployment/release-process.md)
- Troubleshooting: [deployment/troubleshooting.md](deployment/troubleshooting.md)
- Dev and portable Mongo runtime: [deployment/mongo-docker-dev-runtime.md](deployment/mongo-docker-dev-runtime.md)
- Backup and recovery: [deployment/patient-data-backup-and-recovery.md](deployment/patient-data-backup-and-recovery.md)

## Testing

- Testing command guide: [testing/TESTING_GUIDE.md](testing/TESTING_GUIDE.md)
- Testing strategy and quality policy: [testing/strategy.md](testing/strategy.md)

## Repository Map

- API entrypoint: `api/main.py`
- API HTTP layer: `api/routers/`
- API contracts: `api/contracts/`
- API services and workflows: `api/services/`, `api/core/`
- API repositories and Mongo runtime: `api/repositories/`, `api/db/mongo/`, `api/infra/db/`
- UI route and template layer: `coyote/blueprints/`, `coyote/templates/`
- UI-to-API transport layer: `coyote/services/api_client/`
- Test suites: `tests/api/`, `tests/web/`, `tests/contract/`, `tests/unit/`

## Reading Order

1. Read architecture docs before moving modules or changing dependency direction.
2. Read API docs before changing endpoint behavior or response contracts.
3. Read development docs before adding a feature or removing a layer.
4. Read deployment docs before changing Compose files, env vars, or startup defaults.
5. Read testing docs before removing tests or introducing new quality gates.
