Test suites for Coyote3 are organized by functionality.

- `tests/unit`: framework-agnostic core/infra unit tests.
- `tests/api`: API route/service contract and organization tests.
- `tests/web`: Web boundary and presentation-layer tests.
- `tests/contract`: architecture boundary contract tests.
- `tests/api/test_api_client_architecture.py`: transport primitives and payload behavior.
- `tests/api/test_api_route_security.py`: guardrail ensuring API routes stay protected.
- `tests/api/test_workflow_contracts.py`: strict workflow validation behavior.
- `tests/api/routes/test_reports_routes.py`: report route-family behavior tests (preview/save).
- `tests/api/routes/test_dna_routes.py`: DNA route helper and endpoint behavior tests.
- `tests/api/routes/test_rna_routes.py`: RNA route helper and endpoint behavior tests.
- `tests/api/routes/test_system_routes.py`: auth/session/system route behavior tests.
- `tests/api/routes/test_internal_routes.py`: internal API token-guarded route behavior tests.
- `tests/api/routes/test_home_routes.py`: home route read/mutation behavior tests.
- `tests/api/routes/test_public_routes.py`: public route read/error behavior tests.
- `tests/api/routes/test_common_routes.py`: common route search/context behavior tests.
- `tests/api/routes/test_admin_routes.py`: admin route context/mutation behavior tests.
- `tests/web/test_web_api_integration_helpers.py`: Flask-side API helper and endpoint-builder tests.
- `tests/unit/workflows/test_filter_normalization.py`: workflow filter normalization unit tests.
- `tests/unit/reporting/test_reporting_pipeline_and_paths.py`: reporting path/pipeline unit tests.
- `tests/api/fixtures/mock_collections.py`: collection-shaped mock data used by route tests.
- `tests/api/fixtures/fake_store.py`: shared fake handler/store harness for integration-style route tests.
- `tests/api/routes/*_harness.py`: integration-style route tests using the shared fake-store harness.
- `tests/api/fixtures/extract_latest_docs.py`: read-only snapshot extractor (prod full + dev RNA/WGS scope).
- `tests/api/fixtures/db_snapshots/prod_latest.json`: latest per-collection prod snapshot.
- `tests/api/fixtures/db_snapshots/dev_rna_wgs_latest.json`: latest per-collection dev snapshot scoped to RNA/WGS patterns.

Rule of thumb:
- Add pure core/infra behavior tests under `tests/unit`.
- Add API behavior and guardrails under `tests/api`.
- Add Flask/Jinja boundary and UI behavior under `tests/web`.
- Add architecture guardrails under `tests/contract`.
- Keep tests fast and deterministic; avoid external network/services.
- Run coverage regularly and add tests based on uncovered lines:

```bash
PYTHONPATH=. .venv/bin/pytest -q tests --cov=api --cov=coyote --cov-report=term-missing --cov-report=xml
```

- Mutation testing should run in an isolated virtualenv to avoid dependency conflicts with the main test environment.

- Refresh DB-backed snapshots only in read-only mode:

```bash
PYTHONPATH=. PYTHONPYCACHEPREFIX=/tmp/coyote3_pycache PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/api/fixtures/extract_latest_docs.py
```

`tests_internal` is legacy and intentionally excluded from default pytest discovery.

Run by suite marker:

```bash
PYTHONPATH=. .venv/bin/pytest -q -m unit
PYTHONPATH=. .venv/bin/pytest -q -m api
PYTHONPATH=. .venv/bin/pytest -q -m web
PYTHONPATH=. .venv/bin/pytest -q -m contract
```
