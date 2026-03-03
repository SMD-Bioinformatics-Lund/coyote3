# Testing and Quality Gates

Coyote3 uses a layered test strategy with architecture guardrails plus contract-focused checks.

## Current baseline

- API route protection guardrails (`tests/test_api_route_security.py`)
- API route organization guardrails (`tests/api/test_route_module_organization.py`)
- Web/API boundary guardrails (`tests/web/test_web_api_boundary.py`)
- API client transport tests (`tests/test_api_client_architecture.py`)
- Workflow contract validation tests (`tests/test_workflow_contracts.py`)

## Required pre-commit checks

Run compile validation:

```bash
PYTHONPYCACHEPREFIX=/tmp/coyote3_pycache PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m compileall -q api coyote tests
```

Run test suite:

```bash
PYTHONPYCACHEPREFIX=/tmp/coyote3_pycache PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q tests
```

## Coverage direction

The next expansion is endpoint-level behavior testing by domain:

- DNA routes
- RNA routes
- reports routes
- admin/public/home routes

Each new route should include success, permission, validation, and error-path tests.
