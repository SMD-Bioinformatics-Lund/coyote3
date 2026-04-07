# Testing And Quality

## Test layers

- `tests/unit`: fast unit tests
- `tests/api/routers`: API route behavior and contracts
- `tests/integration`: cross-component behavior
- `tests/contract`: boundary and schema drift checks
- `tests/ui`: UI behavior checks where present

## Core commands

```bash
PYTHONPATH=. python -m pytest -q
PYTHONPATH=. python -m ruff check api coyote tests scripts
.venv/bin/python -m mkdocs build --strict
```

## Test compose stack (optional)

```bash
cp deploy/env/example.test.env .coyote3_test_env
./scripts/compose-with-version.sh \
  --env-file .coyote3_test_env \
  -f deploy/compose/docker-compose.test.yml \
  --profile tests \
  up -d --build
```

Run tests inside the runner profile:

```bash
docker compose --env-file .coyote3_test_env -f deploy/compose/docker-compose.test.yml logs -f coyote3_test_runner
```

## Coverage family gates

```bash
PYTHON_BIN="$(command -v python)" PYTHONPATH=. bash scripts/run_family_coverage_gates.sh
```

Current script enforces family-specific thresholds (`api/core`, `api/services`, `api/routers`, `coyote/blueprints`).

Uniform threshold can be enforced with:

```bash
UNIFORM_MIN=60 PYTHON_BIN="$(command -v python)" PYTHONPATH=. bash scripts/run_family_coverage_gates.sh
```

## CI workflow notes

Quality workflow should execute:

1. lint (`ruff check`)
2. format check (`ruff format --check`)
3. full test suite
4. contract/boundary quick checks
5. strict docs build from the project `.venv`
6. compose config validation
7. API concurrency/latency quick check (`tests/api/test_api_latency_concurrency.py`)

## API latency and concurrency quick check

`tests/api/test_api_latency_concurrency.py` validates:

- concurrent request handling for `/api/v1/health`
- stable average request latency under moderate parallel load
- bounded total wall-time after warm-up

It is a guardrail test, not a full performance benchmark. For true capacity
planning, run dedicated load tooling (for example k6/Locust) against deployed
stage/prod-like infrastructure.

## Writing tests for new code

- add unit tests for pure logic in `api/core`/`api/services`
- add router tests for HTTP boundary behavior
- add fixtures for realistic payloads
- avoid coupling tests to production secrets/env

## UI route testing

For Flask web routes, test the route and the Flask-to-API contract together.

- add route smoke coverage under `tests/ui`
- stub `CoyoteApiClient` methods instead of importing backend services directly
- stub `coyote.verify_external_api_dependency` when the test is about page behavior rather than startup availability checks
- prefer `tests/fixtures/api/mock_collections.py` for fixture-shaped documents
- keep payloads aligned with real collection structure from `tests/fixtures/api/db_snapshots/*`
- patch `render_template` only when the route contract is the thing under test

Example:

```python
from coyote.services.api_client.api_client import CoyoteApiClient
from coyote.services.api_client.base import ApiPayload
from tests.fixtures.api import mock_collections as fx


def _payload(value: dict) -> ApiPayload:
    return ApiPayload(value)


def _fake_get(self, path, headers=None, params=None):  # noqa: ARG001
    sample = fx.sample_doc()
    if path.endswith("/api/v1/samples/s1/small-variants"):
        return _payload({"sample": sample, "display_sections_data": {"snvs": []}})
    return _payload({})
```

This keeps UI route tests close to real API payload shapes and catches
contract drift after refactors.

When a view or helper binds `current_app` during import, load it under an app
context and keep the external API dependency check stubbed so the test focuses
on route behavior instead of startup connectivity.

## Testing roles and permissions

Role and permission tests should stay close to the boundary being exercised:

- use `tests/api` when you are validating FastAPI access control
- use `tests/ui` when you are validating whether Flask pages or actions are visible or usable
- use `tests/fixtures/api/mock_collections.py` to start from realistic user/sample payloads

API example:

```python
from tests.fixtures.api import mock_collections as fx

user = fx.api_user()
user.permissions = ["preview_report"]
user.denied_permissions = []
user.role = "user"
user.access_level = 9
```

Then pass that `user` directly into route helpers or access-control functions.

UI example:

```python
user = fx.user_doc()
user["permissions"] = ["preview_report"]
user["role"] = "user"
user["access_level"] = 9
```

Use that fixture-shaped payload in the mocked `/api/v1/auth/sessions/current` response or
in whatever Flask-side route context the page consumes. That keeps permission tests aligned
with the real stored user document shape instead of inventing a test-only schema.
