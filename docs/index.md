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
- `pytest -m unit|api|web|contract` for suite-focused execution.
- `.github/workflows/quality.yml` enforces the same checks in CI.
- `.pre-commit-config.yaml` enforces quick local hooks for `unit`, `web`, `api` smoke, and `contract` suites.

Backend refactor status:
- Mongo infrastructure moved to `api/infra/db` (handlers + adapter/base migration in progress).
- External annotation/data-source handlers split into `api/infra/external`.
- Authentication/session access and RBAC dependencies extracted into `api/security/access.py`.
- Access-check audit event writing extracted to `api/audit/access_events.py`.
- Workflow orchestration moved to `api/core/workflows`.
- Interpretation logic moved to `api/core/interpretation`.
- DNA domain logic moved to `api/core/dna`.
- RNA domain logic moved to `api/core/rna`.
- Reporting pipeline/path logic moved to `api/core/reporting`.
- API request/response contracts introduced under `api/contracts` (initial auth + reports coverage).
- System/auth route response contracts added under `api/contracts/system.py`.
- Internal route response contracts added under `api/contracts/internal.py`.
- Home route response contracts added under `api/contracts/home.py`.
- Common route response contracts added under `api/contracts/common.py`.
- Public route response contracts added under `api/contracts/public.py`.
- Dashboard route response contracts added under `api/contracts/dashboard.py`.
- Admin roles/users read-context contracts added under `api/contracts/admin.py`.
- Admin permission contracts/mutation envelope added under `api/contracts/admin.py`.
- Coverage route response contracts added under `api/contracts/coverage.py`.
- Admin assay/genelist/aspc/schema contracts added under `api/contracts/admin.py`.
- Samples/coverage-mutation contracts added under `api/contracts/samples.py`.
- All `/api/v1` route decorators now use explicit typed response contracts.
- Report save endpoints upgraded from generic to typed contracts in `api/contracts/reports.py`.
- Admin role/user/sample mutations and validation endpoints upgraded from generic to typed admin contracts.
- RNA fusion routes upgraded from generic payloads to typed contracts in `api/contracts/rna.py`.
- DNA mutation endpoints upgraded from generic payloads to typed shared mutation contracts (`api/contracts/samples.py`).
- DNA read/context endpoints upgraded from generic payloads to typed contracts in `api/contracts/dna.py`.
- Flask UI API client now forwards `Authorization: Bearer <api_session_token>` from API session cookies on server-side API calls.
- Flask API transport client consolidated to `coyote/services/api_client` (legacy `coyote/integrations/api` removed).
- API runtime/security settings centralized in `api/settings.py`.
