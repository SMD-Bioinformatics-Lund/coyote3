# Local Development

This document describes the standard local development setup for Coyote3.

## Virtual Environment

Use a project-local virtual environment. Do not run the application from a system Python installation.

```bash
# Create the local environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-docs.txt
```

## Validation Commands

Run these commands from the activated environment:

```bash
# Linting and static checks
python -m ruff check api coyote tests scripts

# Tests
python -m pytest -q

# Strict docs build
python -m mkdocs build --strict
```

## Running The Services Directly

If you want to debug outside Docker, you can run the main services directly:

```bash
# API
PYTHONPATH=. python -m uvicorn api.main:app --reload --port 8001

# Web UI
PYTHONPATH=. python -m wsgi
```

## Development Loop

For most code changes:

1. **Feature Modification**: Update contracts, service logic, routes, or templates.
2. **Focused Validation**: Execute targeted unit tests matching the modified domain.
3. **Static Correction**: Run full repository linting and format verification.
4. **Quality Gate Evaluation**: Run the coverage and contract checks before commit.

```bash
# Example: contract and coverage checks
PYTHON_BIN="$(command -v python)" PYTHONPATH=. bash scripts/run_family_coverage_gates.sh
PYTHON_BIN="$(command -v python)" bash scripts/check_contract_integrity.sh
```

## Git Hooks

The repository uses `pre-commit` hooks to enforce basic quality checks before a commit is created.

```bash
# Install hooks once per clone
bash scripts/setup_git_hooks.sh

# Run hooks manually across the repository
python -m pre_commit run --all-files
```

**Security note**: The hooks are configured to block common static analysis failures and possible secret leaks. If they are bypassed, that should be documented and reviewed.

## Shell Environment

Run engineering commands inside the project's `.venv`. If you use IDE integrations or helper scripts, make sure `PYTHON_BIN` points to the project-local interpreter.

```bash
export PYTHON_BIN="$(command -v python)"
```
