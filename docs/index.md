# Coyote3 Documentation Index

This is the single documentation entrypoint.

## Refactor Governance Note

Current engineering direction is API-centric:
- API layer owns business logic, security, audit, and persistence.
- Flask UI remains presentation-only and calls API endpoints over HTTP.
- Boundary compliance is enforced incrementally with contract tests.

## Core Documentation
- [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md)
- [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)
- [API_REFERENCE.md](API_REFERENCE.md)
- [UI_USER_GUIDE.md](UI_USER_GUIDE.md)
- [SECURITY_MODEL.md](SECURITY_MODEL.md)
- [DATA_MODEL.md](DATA_MODEL.md)
- [DEPLOYMENT_AND_OPERATIONS.md](DEPLOYMENT_AND_OPERATIONS.md)
- [TESTING_STRATEGY.md](TESTING_STRATEGY.md)
- [EXTENSION_PLAYBOOK.md](EXTENSION_PLAYBOOK.md)

## Engineering Standards
- [CODE_STYLE.md](CODE_STYLE.md)
- [RELEASE_PROCESS.md](RELEASE_PROCESS.md)
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

## Supporting References
- [API_ENDPOINT_CATALOG.md](API_ENDPOINT_CATALOG.md)
- [TRACEABILITY_MATRIX.md](TRACEABILITY_MATRIX.md)
- [GLOSSARY.md](GLOSSARY.md)

## Boundary Enforcement

UI/API separation is enforced by contract tests:
- `tests/contract/test_ui_forbidden_backend_imports.py`
- `tests/contract/test_ui_forbidden_mongo_usage.py`

Tooling baseline:
- `ruff check api coyote tests`
- `ruff format --check api coyote tests`

Backend refactor status:
- Mongo infrastructure moved to `api/infra/db` (handlers + adapter/base migration in progress).
- External annotation/data-source handlers split into `api/infra/external`.
