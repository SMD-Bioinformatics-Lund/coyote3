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

1. lint (`ruff`, `black`)
2. targeted test suites
3. coverage gates
4. contract/boundary smoke checks
5. compose config validation
6. API concurrency/latency smoke (`tests/api/test_api_latency_concurrency.py`)

## API latency and concurrency smoke

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
