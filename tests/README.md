Test suites for Coyote3 are organized by functionality.

- `tests/unit`: framework-agnostic core/infra unit tests.
- `tests/api`: API router/service contract and organization tests.
- `tests/ui`: Web boundary and presentation-layer tests.
- `tests/integration`: architecture boundary and cross-layer integration tests.
- `tests/fixtures`: shared test fixtures, fake stores, and baseline data.
- `tests/api/test_api_client_architecture.py`: transport primitives and payload behavior.
- `tests/api/test_api_route_security.py`: guardrail ensuring API routes stay protected.
- `tests/api/test_workflow_contracts.py`: strict workflow validation behavior.
- `tests/api/routers/test_reports_routes.py`: report route-family behavior tests (preview/save).
- `tests/api/routers/test_dna_routes.py`: DNA route helper and endpoint behavior tests.
- `tests/api/routers/test_rna_routes.py`: RNA route helper and endpoint behavior tests.
- `tests/api/routers/test_system_routes.py`: auth/session/system route behavior tests.
- `tests/api/routers/test_internal_routes.py`: internal API token-guarded route behavior tests.
- `tests/api/routers/test_home_routes.py`: home route read/mutation behavior tests.
- `tests/api/routers/test_public_routes.py`: public route read/error behavior tests.
- `tests/api/routers/test_common_routes.py`: common route search/context behavior tests.
- `tests/api/routers/test_admin_routes.py`: admin route context/mutation behavior tests.
- `tests/ui/test_web_api_integration_helpers.py`: Flask-side API helper and endpoint-builder tests.
- `tests/unit/workflows/test_filter_normalization.py`: workflow filter normalization unit tests.
- `tests/unit/reporting/test_reporting_pipeline_and_paths.py`: reporting path/pipeline unit tests.
- `tests/fixtures/api/mock_collections.py`: collection-shaped mock data used by route tests.
- `tests/fixtures/api/fake_store.py`: shared fake handler/store harness for integration-style route tests.
- `tests/api/routers/*_harness.py`: integration-style route tests using the shared fake-store harness.
- `tests/fixtures/api/extract_latest_docs.py`: read-only snapshot extractor (prod full + dev RNA/WGS scope).
- `tests/fixtures/api/db_snapshots/prod_latest.json`: latest per-collection prod snapshot.
- `tests/fixtures/api/db_snapshots/dev_rna_wgs_latest.json`: latest per-collection dev snapshot scoped to RNA/WGS patterns.

Rule of thumb:
- Add pure core/infra behavior tests under `tests/unit`.
- Add API behavior and guardrails under `tests/api`.
- Add Flask/Jinja boundary and UI behavior under `tests/ui`.
- Add architecture guardrails under `tests/integration`.
- Keep tests fast and deterministic; avoid external network/services.
- Run coverage regularly and add tests based on uncovered lines:

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
```

Marker-to-directory mapping:

- `unit` -> `tests/unit`
- `api` -> `tests/api`
- `web` -> `tests/ui`
- `contract` -> `tests/integration`

Run by directory:

```bash
PYTHONPATH=. ${PYTEST_BIN:-pytest} -q tests/unit
PYTHONPATH=. ${PYTEST_BIN:-pytest} -q tests/api
PYTHONPATH=. ${PYTEST_BIN:-pytest} -q tests/ui
PYTHONPATH=. ${PYTEST_BIN:-pytest} -q tests/integration
PYTHONPATH=. ${PYTEST_BIN:-pytest} -q tests/fixtures
```
