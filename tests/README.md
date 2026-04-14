Test suites for Coyote3 are organized by runtime behavior.

- `tests/unit`: core business logic, contracts, query builders, ingest, reporting, and persistence helpers.
- `tests/api`: FastAPI route, auth, and request/response behavior.
- `tests/ui`: Flask route rendering, API-client integration, and key user flows.
- `tests/fixtures`: shared mock data and baseline datasets used by the main suites.
- `tests/api/routers/test_reports_routes.py`: report preview/save API behavior.
- `tests/api/routers/test_dna_routes.py`: DNA route helpers and endpoint behavior.
- `tests/api/routers/test_rna_routes.py`: RNA route helpers and endpoint behavior.
- `tests/api/routers/test_system_routes.py`: auth/session/system route behavior.
- `tests/api/routers/test_internal_routes.py`: internal token-guarded ingest and admin behavior.
- `tests/api/routers/test_home_routes.py`: sample home, edit-context, and mutation behavior.
- `tests/api/routers/test_public_routes.py`: public route read/error behavior.
- `tests/api/routers/test_common_routes.py`: shared search/context behavior.
- `tests/api/routers/test_admin_routes.py`: admin route context and mutation behavior.
- `tests/ui/test_web_api_integration_helpers.py`: Flask-side API helper behavior.
- `tests/unit/workflows/test_filter_normalization.py`: workflow filter normalization.
- `tests/unit/reporting/test_reporting_pipeline_and_paths.py`: reporting pipeline/path behavior.
- `tests/fixtures/api/mock_collections.py`: collection-shaped mock data used by route tests.
- `tests/fixtures/api/fake_store.py`: shared fake handler/store harness for route tests.
- `tests/api/routers/*_harness.py`: fake-store route tests for common and home flows.
- `tests/fixtures/api/extract_latest_docs.py`: read-only snapshot extractor (prod full + dev RNA/WGS scope).
- `tests/fixtures/api/db_snapshots/prod_latest.json`: latest per-collection prod snapshot.
- `tests/fixtures/api/db_snapshots/dev_rna_wgs_latest.json`: latest per-collection dev snapshot scoped to RNA/WGS patterns.

Rule of thumb:
- Add pure core and service behavior tests under `tests/unit`.
- Add API request/response behavior under `tests/api`.
- Add Flask/Jinja user-flow coverage under `tests/ui`.
- Avoid meta tests that only enforce directory shape, import patterns, or placeholder wrappers.
- Keep tests fast and deterministic; avoid external network/services.
- Run coverage regularly and add tests around real business logic or user-facing behavior:

```bash
PYTHONPATH=. ${PYTEST_BIN:-pytest} -q tests --cov=api --cov=coyote --cov-report=term-missing --cov-report=xml
```

- Mutation testing should run in an isolated virtualenv to avoid dependency conflicts with the main test environment.

- Refresh DB-backed snapshots only in read-only mode:

```bash
PYTHONPATH=. PYTHONPYCACHEPREFIX=/tmp/coyote3_pycache PYTHONDONTWRITEBYTECODE=1 ${PYTHON_BIN:-python} tests/fixtures/api/extract_latest_docs.py
```

`tests_internal` is legacy and intentionally excluded from default pytest discovery.

Run by suite marker:

```bash
PYTHONPATH=. ${PYTEST_BIN:-pytest} -q -m unit
PYTHONPATH=. ${PYTEST_BIN:-pytest} -q -m api
PYTHONPATH=. ${PYTEST_BIN:-pytest} -q -m web
PYTHONPATH=. ${PYTEST_BIN:-pytest} -q -m contract

Run by directory:

```bash
PYTHONPATH=. ${PYTEST_BIN:-pytest} -q tests/unit
PYTHONPATH=. ${PYTEST_BIN:-pytest} -q tests/api
PYTHONPATH=. ${PYTEST_BIN:-pytest} -q tests/ui
PYTHONPATH=. ${PYTEST_BIN:-pytest} -q tests/fixtures
```
