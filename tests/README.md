# Test suites

<!-- badges:start -->
![Scope: Tests and fixtures](https://img.shields.io/badge/Scope-Tests%20and%20fixtures-4F46A5?style=flat)
<!-- badges:end -->

Choose tests by the behavior they protect. Detailed commands, coverage thresholds,
and release requirements are in the
[test strategy](../docs/testing/test-strategy-and-quality-gates.md).

## Suite ownership

| Location | Coverage |
| --- | --- |
| `core/tests/unit/` | Portable clinical rules, contracts, query policies, ingest and reporting services using fake ports. |
| `api/tests/unit/`, `api/tests/http/` | Host configuration, security, workers, HTTP requests, permissions and packaged presentation. |
| `adapters/mongo/tests/unit/` | Query compilation, repository operations, connection settings and persistence contracts. |
| `adapters/mongo/tests/integration/` | Adapter implementations exercised with core services and synthetic in-memory collections. |
| Each package's `tests/smoke/` | A fast subset of real behavior checks included in that package's full suite. |
| `tests/unit/` | Repository tooling, deployment definitions, documentation and release checks. |
| `tests/smoke/` | In-process client/API communication and adapter/core record integrity. |
| `tests/integration/` | Transactions, delivery/recovery, runtime database permissions, architecture boundaries, and contract generation. |
| `tests/fixtures/` | Application-level synthetic datasets and architecture baselines. Package helpers stay inside their own test trees. |
| `tests/docs/` | Markdown tooling and rendering checks. |
| `tests/load/` | Opt-in synthetic HTTP workloads; see the [load-testing guide](../docs/testing/load-and-capacity-testing.md). |
| External `coyote-pyclient` test suite | Independent HTTP client authentication, sync/async operations, timeouts, and errors. |
| `frontend/src/`, `frontend/tests/smoke/` | Colocated TypeScript tests and a separately selectable fast component suite. |
| `frontend/tests/e2e/` | Browser workflows with deterministic intercepted API responses. |
| `frontend/tests/e2e-real/` | Explicit checks against a running synthetic deployment. |

Audit unit tests separate runtime-role provisioning (`test_mongo_runtime_roles.py`),
collection retention and replay (`test_audit_retention.py`), and archival exports
(`test_audit_checkpoints.py`). Real MongoDB authorization enforcement belongs in
`tests/integration/test_audit_runtime_permissions.py`.

## Running tests

Run from the repository root with the development environment installed:

```bash
scripts/quality/run_package_tests.sh all --smoke
scripts/quality/run_package_tests.sh core
scripts/quality/run_package_tests.sh all --coverage
.venv/bin/python -m pytest -q tests/smoke
.venv/bin/python -m pytest -q tests
# Discover application tests and all Python package suites using pytest.ini
.venv/bin/python -m pytest -q
npm --prefix frontend run test:smoke
```

To exercise database transactions with temporary, loopback-only MongoDB replicas:

```bash
.venv/bin/python scripts/quality/run_transaction_tests.py -- \
  -q tests core/tests api/tests adapters/mongo/tests \
  --cov=coyote_api --cov=coyote --cov=coyote_mongo --cov-config=.coveragerc \
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
dependencies. `tests/integration/http/test_ui_route_api_contracts.py` verifies those operations
against FastAPI routes; generated TypeScript contracts are checked separately by
the [OpenAPI pipeline](../docs/development/frontend-api-contracts.md).

Package coverage runs from the package directory using its `pyproject.toml`, writes
its own `.coverage` database and `coverage/coverage.xml`, and measures its entire
runtime namespace, including unexecuted modules. The root report and existing
clinical gates use the complete application suite. Smoke runs do not enforce full
coverage; they exclude wheel builds, PDF pagination and configured-service tests.

Installed-distribution tests require `./install.sh dependencies` first. They use the
prepared Relay wheel from `.release/relay` and do not fetch Git dependencies.
