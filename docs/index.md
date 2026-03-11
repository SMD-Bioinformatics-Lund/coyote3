# Coyote3 Documentation Hub

## Audience
This documentation set is intended for:
- backend and frontend engineers
- DevOps and platform operators
- security and compliance reviewers
- clinical geneticists, doctors, and bioinformatics analysts

## Scope
The documentation describes the current production design of Coyote3: architecture, API contracts, data model, UI behavior, security controls, deployment, testing policy, release governance, and extension workflows.

## Key Concepts
For shared terminology, start with [GLOSSARY.md](GLOSSARY.md).

## How To Navigate
- System architecture and boundaries: [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md)
- Database-agnostic backend and ports strategy: [BACKEND_DB_AGNOSTIC_REFACTOR.md](BACKEND_DB_AGNOSTIC_REFACTOR.md)
- Developer onboarding and coding patterns: [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)
- Route design, wiring, and test checklist: [ROUTE_IMPLEMENTATION_GUIDE.md](ROUTE_IMPLEMENTATION_GUIDE.md)
- API usage and contracts: [API_REFERENCE.md](API_REFERENCE.md)
- Clinical/user-facing UI behavior: [UI_USER_GUIDE.md](UI_USER_GUIDE.md)
- Security controls and access model: [SECURITY_MODEL.md](SECURITY_MODEL.md)
- Authentication/login runtime model and measured stats: [AUTH_LOGIN_MODEL_AND_STATS.md](AUTH_LOGIN_MODEL_AND_STATS.md)
- Data architecture and document lifecycle: [DATA_MODEL.md](DATA_MODEL.md)
- Deployment and operations: [DEPLOYMENT_AND_OPERATIONS.md](DEPLOYMENT_AND_OPERATIONS.md)
- Operations verification evidence (latest): [OPERATIONS_VERIFICATION_2026-03-11.md](OPERATIONS_VERIFICATION_2026-03-11.md)
- Dev/portable Mongo Docker runtime and snapshot workflow: [MONGO_DOCKER_DEV_RUNTIME.md](MONGO_DOCKER_DEV_RUNTIME.md)
- Testing policy and quality gates: [TESTING_STRATEGY.md](TESTING_STRATEGY.md)
- Safe extension workflows: [EXTENSION_PLAYBOOK.md](EXTENSION_PLAYBOOK.md)

## Engineering Standards
- Code and naming standards: [CODE_STYLE.md](CODE_STYLE.md)
- Release governance: [RELEASE_PROCESS.md](RELEASE_PROCESS.md)
- Incident diagnostics: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

## Supporting References
- Route inventory: [API_ENDPOINT_CATALOG.md](API_ENDPOINT_CATALOG.md)
- Requirement-to-test mapping: [TRACEABILITY_MATRIX.md](TRACEABILITY_MATRIX.md)

## Where To Look In Code
- API HTTP layer: `api/routes/`
- API contracts: `api/contracts/`
- API workflows and domain logic: `api/core/`
- API security: `api/security/`
- API persistence and integrations: `api/infra/`
- API audit events: `api/audit/`
- Flask UI routes and templates: `coyote/blueprints/`
- Flask UI API transport: `coyote/services/api_client/`

## Operational Implications
- UI renders server-side templates and calls API over HTTP for business operations.
- API is the authoritative layer for RBAC, audit logging, and MongoDB access.
- Changes to contracts, permissions, and schema-driven configuration must be tested and documented before release.
