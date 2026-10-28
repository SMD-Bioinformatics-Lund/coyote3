# Developer environment setup

This document describes the standard local development setup for Coyote3.

Choose the development mode before provisioning services:

| Your change | Start with | Infrastructure |
| --- | --- | --- |
| Domain rules, contracts, UI components or documentation | Install the tools below and run focused tests using synthetic fixtures. | No running deployment is required for isolated tests and mocked browser checks. Tests that explicitly require a database remain separate. |
| End-to-end ingest, worker behavior or saved reports | Use the [local container procedure](local-quickstart.md), then the focused implementation/tests for your change. | A disposable application stack with transaction-capable MongoDB and Redis. |
| API source debugging against a prepared development stack | Follow **Running the services directly** below. | Existing development infrastructure and host-reachable endpoints. |

You do not need to complete a production installation to make a first fixture-based
code change. Use the named references only when the change reaches that boundary.

## Virtual Environment

Use the project's virtual environment for Python commands. Full API development
uses Python 3.14.7, matching the API images; the shared SDK and deployment helpers
support Python 3.12 or later. Install the selected interpreter before creating the
environment; do not rely on an older distribution's `python3` default.

```bash
# Create the local environment
python3.14 --version
python3.14 -m venv .venv
source .venv/bin/activate

# Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pip install --no-deps -e .
python -m pip install --no-deps -e clients/python
python -m pip install -r requirements-docs.txt
```

## Validation Commands

Run these commands from the activated environment:

```bash
# Linting and static checks
python -m ruff check src api tests scripts

# Tests
python -m pytest -q

# Strict docs build
python -m mkdocs build --strict
```

## Running the services directly

Pip installation does not provision MongoDB, Redis, users, indexes or center
configuration. Complete the infrastructure/baseline steps in
[first installation](../deployment/first-installation.md) first. Use host-reachable
MongoDB URIs; `mongo-app` and `redis` Compose DNS names normally resolve only
inside the Docker network.

Prepare a private host runtime environment file with the settings from the
[environment reference](../deployment/configuration-reference.md). Host processes
need `COYOTE3_CENTER_CONFIG_DIR` set to the host center directory, plus explicit
host-reachable `CACHE_REDIS_URL`, `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`.
The application Compose file wires those URLs internally; copying its environment
template alone does not expose Redis to a host process. Do not point at production
databases for local development. Load only a trusted file:

```bash
set -a
. /protected/coyote3-host-development.env
set +a
```

Run the API and frontend in separate terminals, with the environment active in
the API terminal:

```bash
# API
PYTHONPATH=. python -m uvicorn api.app.main:app --reload --reload-dir api --reload-dir src --port 8001
```

```bash
# Web UI
npm --prefix frontend ci
npm --prefix frontend run dev
```

## Development Loop

For most code changes:

1. **Feature Modification**: Update contracts, service logic, routes, or templates.
2. **Focused Validation**: Execute targeted unit tests matching the modified domain.
3. **Static Correction**: Run full repository linting and format verification.
4. **Quality Gate Evaluation**: Run the coverage and contract checks before commit.

```bash
# Example: contract and coverage checks
PYTHON_BIN="$(command -v python)" PYTHONPATH=. bash scripts/quality/run_family_coverage_gates.sh
PYTHON_BIN="$(command -v python)" bash scripts/quality/check_contract_integrity.sh
```

## Git Hooks

The repository uses `.githooks/pre-commit` to enforce quality checks before a commit is created.

```bash
# Install hooks once per clone
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit

# Run hooks manually across the repository
python -m pre_commit run --all-files
```

**Security note**: The hooks are configured to block common static analysis failures and possible secret leaks. If they are bypassed, that should be documented and reviewed.

## Shell Environment

Run engineering commands inside the project's `.venv`. If you use IDE integrations or helper scripts, make sure `PYTHON_BIN` points to the project-local interpreter.

```bash
export PYTHON_BIN="$(command -v python)"
```
