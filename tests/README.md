# Test suites

Choose tests by the behavior they protect. Detailed commands, coverage thresholds,
and release requirements are in the
[test strategy](../docs/testing/test-strategy-and-quality-gates.md).

## Suite ownership

| Location | Coverage |
| --- | --- |
| `tests/unit/` | Application/domain logic, collection contracts, query builders, repositories, and operational helpers. |
| `tests/unit/reporting/` | Reporting rules, templates, HTML/PDF output, and report pipeline behavior. |
| `tests/unit/workflows/` | Workflow services and clinical filter normalization. |
| `tests/api/` | Cross-route authentication, permissions, OpenAPI, audit, rate limits, and UI route contracts. |
| `tests/api/routers/` | Resource-specific request/response, validation, and permission behavior. |
| `tests/integration/` | Transactions, delivery/recovery, runtime database permissions, architecture boundaries, and contract generation. |
| `tests/fixtures/` | Synthetic records, shared fake repositories, and architecture baselines. |
| `tests/docs/` | Markdown tooling and rendering checks. |
| `tests/load/` | Opt-in synthetic HTTP workloads; see the [load-testing guide](../docs/testing/load-and-capacity-testing.md). |
| `clients/python/tests/` | Independent HTTP client authentication, sync/async operations, timeouts, and errors. |
| `frontend/src/` | Colocated TypeScript module, component, and page tests. |
| `frontend/tests/e2e/` | Browser workflows with deterministic intercepted API responses. |
| `frontend/tests/e2e-real/` | Explicit checks against a running synthetic deployment. |

Audit unit tests separate runtime-role provisioning (`test_mongo_runtime_roles.py`),
collection retention and replay (`test_audit_retention.py`), and archival exports
(`test_audit_checkpoints.py`). Real MongoDB authorization enforcement belongs in
`tests/integration/test_audit_runtime_permissions.py`.

## Running tests

Run from the repository root with the development environment installed:

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/unit
PYTHONPATH=. .venv/bin/pytest -q tests/api
.venv/bin/python -m pytest -q clients/python/tests
```

To exercise database transactions with temporary, loopback-only MongoDB replicas:

```bash
.venv/bin/python scripts/quality/run_transaction_tests.py -- \
  -q tests/unit tests/api tests/integration \
  --cov=api --cov=coyote3 --cov-config=.coveragerc \
  --cov-report=term-missing --cov-report=xml
```

This requires `mongod`; the runner creates and removes its own databases and
processes. Tests with explicit database prerequisites may skip in a plain pytest
run. Never supply production database settings to integration tests.

For all source, contract, frontend, browser, and documentation checks:

```bash
PYTHON_BIN=.venv/bin/python bash scripts/quality/run_quality_suite.sh
```

## Adding tests

Use synthetic data and existing fixtures. Name the condition and expected result;
add docstrings for non-obvious clinical or security invariants rather than repeating
fixture names. Keep tests with the relevant runtime boundary and avoid assertions
that only enforce directory names or reproduce implementation details.

Clinical changes need regression cases for filtering, classification, identity,
and report provenance where affected. Authorization changes need both permitted
and denied cases. New clinical pages need primary, empty, and failed browser states;
analysis views must verify that unavailable endpoints are not requested.

Keep `frontend/src/lib/routes/ui-route-registry.ts` synchronized with page API
dependencies. `tests/api/test_ui_route_api_contracts.py` verifies those operations
against FastAPI routes; generated TypeScript contracts are checked separately by
the [OpenAPI pipeline](../docs/development/frontend-api-contracts.md).
