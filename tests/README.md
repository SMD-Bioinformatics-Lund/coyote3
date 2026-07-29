Test suites for Coyote3 are organized by runtime behavior.

- `tests/unit`: core business logic, contracts, query builders, ingest, reporting, and persistence helpers.
- `tests/api`: FastAPI router, auth, OpenAPI, audit, rate-limit, and
  request/response behavior. Domain router tests live in `tests/api/routers`.
- `tests/integration`: architecture boundaries and selected cross-component
  contracts.
- `tests/fixtures`: deterministic mock data and architecture baselines used by the main suites.
- `tests/api/routers/test_reports_routes.py`: report preview/save API behavior.
- `tests/api/routers/test_dna_routes.py`: DNA route helpers and endpoint behavior.
- `tests/api/routers/test_rna_routes.py`: RNA route helpers and endpoint behavior.
- `tests/api/routers/test_internal_routes.py`: internal token-guarded ingest and admin behavior.
- `tests/api/routers/test_home_routes.py`: sample home, edit-context, and mutation behavior.
- `tests/unit/workflows/test_filter_normalization.py`: workflow filter normalization.
- `tests/unit/reporting/test_reporting_pipeline_and_paths.py`: reporting pipeline/path behavior.
- `tests/fixtures/api/mock_collections.py`: collection-shaped mock data used by route tests.
- `tests/fixtures/api/fake_store.py`: shared fake handler/store harness for route tests.
- `tests/api/routers/*_harness.py`: fake-store route tests for common and home flows.

Rule of thumb:
- Add pure core and service behavior tests under `tests/unit`.
- Add API request/response behavior under `tests/api`.
- Add frontend behavior checks under `frontend` as React component or browser tests are introduced.
- Keep browser contracts in `frontend/tests/e2e`. They must use intercepted
  deterministic responses and must cover primary, empty, and failed states for
  a new clinical page. Analysis tabs must also prove unavailable endpoints are
  not requested.
- `tests/api/test_ui_route_api_contracts.py` verifies that literal API contracts
  declared in `frontend/src/lib/routes/ui-route-registry.ts` resolve to real
  FastAPI routes. Keep the registry current when a page gains or loses an API
  dependency.
- Do not add one-off migration tests or meta tests that only enforce directory
  shape, import patterns, or placeholder wrappers. Tests must protect a
  current runtime, contract, safety, or user-visible behavior.
- Keep tests fast and deterministic; avoid external network/services.
- Run coverage regularly and add tests around real business logic or user-facing behavior:

```bash
PYTHONPATH=. ${PYTEST_BIN:-pytest} -q tests --cov=api --cov-report=term-missing --cov-report=xml
```

- Mutation testing should run in an isolated virtualenv to avoid dependency conflicts with the main test environment.

`tests/fixtures/api/extract_latest_docs.py` is a read-only operational helper,
not a test. It is intentionally excluded from normal test execution and must
not be run with production credentials during local validation.

Run by directory:

```bash
PYTHONPATH=. ${PYTEST_BIN:-pytest} -q tests/unit
PYTHONPATH=. ${PYTEST_BIN:-pytest} -q tests/api
```

Run the full source/build quality gate:

```bash
PYTHON_BIN=.venv/bin/python bash scripts/run_quality_suite.sh
```
