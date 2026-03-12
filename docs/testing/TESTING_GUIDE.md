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
