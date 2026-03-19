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
```

## Pre-commit

Install hooks once:

```bash
python -m pre_commit install
```

Run all hooks:

```bash
python -m pre_commit run --all-files
```
