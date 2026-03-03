# Testing Strategy and Route Matrix

This chapter documents the testing strategy for maintainability and safe refactoring.

## Test layers

1. **Architecture guardrails**
- Boundary checks (`tests/web/test_web_api_boundary.py`)
- Route organization checks (`tests/api/test_route_module_organization.py`)
- Route protection checks (`tests/test_api_route_security.py`)

2. **Transport and contract tests**
- API client primitives (`tests/test_api_client_architecture.py`)
- Workflow input contracts (`tests/test_workflow_contracts.py`)

3. **Feature tests (target state)**
- Add endpoint-level behavior tests by functionality area:
  - `tests/api/routes/test_dna_routes.py`
  - `tests/api/routes/test_rna_routes.py`
  - `tests/api/routes/test_reports_routes.py`
  - `tests/api/routes/test_admin_routes.py`
- Prefer collection-shaped fixture docs (`tests/api/fixtures/mock_collections.py`) and the shared fake-store harness (`tests/api/fixtures/fake_store.py`) for realistic, deterministic route testing.

## Minimum standards for new work

Every new API feature should include:

- One success-path test
- One permission/authorization test
- One input-validation test
- One error-path test (resource missing or contract violation)

Every new web feature should include:

- One UI integration test for request/response rendering
- One boundary test if transport usage changes

## Recommended route test matrix

For each route, test the following where applicable:

- Auth required / unauthorized behavior
- Permission required / forbidden behavior
- Valid request returns expected JSON shape
- Invalid request returns stable error payload
- Domain side effects are persisted correctly

## Execution

Run all default tests:

```bash
PYTHONPYCACHEPREFIX=/tmp/coyote3_pycache PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q tests
```

Run compile validation before commit:

```bash
PYTHONPYCACHEPREFIX=/tmp/coyote3_pycache PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m compileall -q api coyote tests
```
