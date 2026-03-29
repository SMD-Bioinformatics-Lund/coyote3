# Local Development

## Python environment

Create and activate a project-local virtualenv:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Then install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Run tooling from the activated environment:

```bash
python -m ruff check api coyote tests scripts
python -m pytest -q
```

## Start only application (without compose)

Use this when debugging process-level behavior:

```bash
# API
PYTHONPATH=. python -m uvicorn api.main:app --reload --port 8001

# UI
PYTHONPATH=. python -m wsgi
```

## Typical edit loop

1. Edit API contract/service/router code
2. Run focused tests
3. Run lint
4. Run family coverage gates before commit

```bash
PYTHONPATH=. python -m pytest -q tests/unit/test_db_documents.py
PYTHONPATH=. python -m ruff check api tests scripts
PYTHON_BIN="$(command -v python)" PYTHONPATH=. bash scripts/run_family_coverage_gates.sh
PYTHON_BIN="$(command -v python)" bash scripts/check_contract_integrity.sh
```

## Pre-commit

Enable repository-managed hooks once per clone:

```bash
bash scripts/setup_git_hooks.sh
```

This config blocks commits unless pre-commit checks pass.

Run all hooks manually:

```bash
python -m pre_commit run --all-files
```

Cross-machine notes:

```bash
# Always run from an activated project virtualenv
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip -r requirements.txt

# Verify pre-commit is available and hooks are installed
python -m pre_commit --version
bash scripts/setup_git_hooks.sh
```

The pre-commit config is portable and does not rely on machine-specific absolute Python paths.
If you want to force a specific interpreter for hooks, set:

```bash
export PYTHON_BIN="$(command -v python3)"
python -m pre_commit run --all-files
```
