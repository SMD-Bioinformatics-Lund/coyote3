# Testing Guide

This guide explains how tests are organized, what each suite protects, and which tests to add when extending the system.

## Test Layout

```text
tests/
├── api/
├── ui/
├── integration/
├── unit/
└── fixtures/
```

### `tests/api/`

Backend-focused tests for:

- FastAPI route behavior
- auth and permission enforcement
- API response contracts
- backend startup and route registration

### `tests/ui/`

UI-focused tests for:

- Flask routes
- template-backed view behavior
- UI route integrity
- UI-to-API integration helpers

### `tests/integration/`

Cross-layer and architectural tests for:

- API/UI boundary integrity
- route contract wiring
- forbidden imports
- forbidden Mongo usage outside approved layers

### `tests/unit/`

Isolated logic tests for:

- domain helpers
- reporting/workflow logic
- lower-level pure functions

### `tests/fixtures/`

Reusable fixtures and baseline data:

- API fake store support
- mock collections
- snapshot baselines for guardrail tests

## Core Commands

Run all tests:

```bash
python -m pytest -q
```

Run all tests with coverage:

```bash
./scripts/run_tests_with_coverage.sh
```

Run per-family coverage gates:

```bash
./scripts/run_family_coverage_gates.sh
```

If your shell is not already inside the project virtualenv, set the interpreter explicitly:

```bash
PYTHON_BIN=/home/ram/.virtualenvs/coyote3/bin/python ./scripts/run_family_coverage_gates.sh
```

Run by suite:

```bash
python -m pytest -q tests/api
python -m pytest -q tests/ui
python -m pytest -q tests/integration
python -m pytest -q tests/unit
```

Run router-focused backend tests:

```bash
python -m pytest -q tests/api/routers
```

Run suite-specific coverage snapshots:

```bash
python -m pytest tests/unit --cov=api --cov=coyote --cov-config=.coveragerc --cov-report=term-missing
python -m pytest tests/api --cov=api --cov=coyote --cov-config=.coveragerc --cov-report=term-missing
python -m pytest tests/ui --cov=api --cov=coyote --cov-config=.coveragerc --cov-report=term-missing
python -m pytest tests/integration --cov=api --cov=coyote --cov-config=.coveragerc --cov-report=term-missing
```

Run the local pre-commit pipeline:

```bash
.venv/bin/pre-commit install
.venv/bin/pre-commit run --all-files
```

The pre-commit pipeline runs these checks in order:

- `ruff-check --fix`
- `black --line-length 100`
- quick `unit` tests
- UI boundary smoke
- API smoke
- integration contract smoke

## What To Run When You Change Code

### If you change backend routes or contracts

Run:

- `tests/api/routers`
- relevant backend tests in `tests/api/`
- relevant `tests/integration/`
- full suite before finishing

### If you change UI routes or templates

Run:

- relevant `tests/ui/`
- `tests/integration/test_web_api_route_contract.py` when UI-to-API path wiring changes
- full suite before finishing

### If you change persistence behavior

Run:

- relevant backend route tests
- relevant unit tests
- `tests/integration/test_backend_db_boundary_guardrails.py`
- full suite before finishing

### If you change startup or architecture boundaries

Run:

- full suite
- deployment smoke checks if Compose or runtime files changed

## Required Coverage For New Work

When adding a new backend resource or endpoint, add:

1. happy-path route coverage
2. invalid input coverage
3. authorization failure coverage
4. not-found or missing-data coverage
5. failure-path or service error coverage where relevant

When adding a new UI integration, add:

1. route rendering or redirect coverage
2. API helper usage coverage where practical
3. failure-state coverage for API errors if the page handles them

## Standardized Test Execution

Use this order for deterministic verification:

1. targeted module tests (`tests/unit/...` or `tests/api/...`)
2. full suite (`python -m pytest -q tests`)
3. full suite with coverage (`./scripts/run_tests_with_coverage.sh`)
4. per-family coverage gates (`./scripts/run_family_coverage_gates.sh`)

Coverage is generated from `.coveragerc` and includes both `api` and `coyote` packages.

## Phase 2 Family Rollout

Phase 2 test expansion is executed family-by-family:

1. `api/core`
2. `api/services`
3. `api/routers`
4. `coyote/blueprints`

Each family is expanded with deterministic tests, then enforced by coverage gates in
`scripts/run_family_coverage_gates.sh`.

Current enforced minimums:

- `api/core >= 30%`
- `api/services >= 55%`
- `api/routers >= 60%`
- `coyote/blueprints >= 52%`

## Guardrail Tests That Should Stay

These tests protect the architecture and should not be removed casually:

- `tests/integration/test_ui_forbidden_backend_imports.py`
- `tests/integration/test_ui_forbidden_mongo_usage.py`
- `tests/integration/test_web_api_route_contract.py`
- `tests/integration/test_backend_db_boundary_guardrails.py`

## Maintenance Rules For Tests

- Keep tests aligned with the actual folder structure.
- Prefer clear setup over hidden fixtures.
- Prefer seam-level mocking over mocking internal implementation noise.
- Delete tests only when the protected behavior is genuinely gone.
- If a test breaks because the architecture changed, update the architecture and the test together.

## Working Baseline

At the time this guide was last updated:

- the full suite passes
- the canonical backend entrypoint is `api.main:app`
- router tests live under `tests/api/routers/`
- coverage execution is standardized via `.coveragerc` and `scripts/run_tests_with_coverage.sh`
