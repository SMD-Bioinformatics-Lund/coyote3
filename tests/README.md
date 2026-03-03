Test suites for Coyote3 are organized by functionality.

- `tests/api`: API route/service contract and organization tests.
- `tests/web`: Web boundary and presentation-layer tests.
- `tests/api/test_api_client_architecture.py`: transport primitives and payload behavior.
- `tests/api/test_api_route_security.py`: guardrail ensuring API routes stay protected.
- `tests/api/test_workflow_contracts.py`: strict workflow validation behavior.
- `tests/api/routes/test_reports_routes.py`: report route-family behavior tests (preview/save).

Rule of thumb:
- Add API behavior and guardrails under `tests/api`.
- Add Flask/Jinja boundary and UI behavior under `tests/web`.
- Keep tests fast and deterministic; avoid external network/services.

`tests_internal` is legacy and intentionally excluded from default pytest discovery.
