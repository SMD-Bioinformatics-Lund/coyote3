# Localized Development and Engineering Standards

This document defines the authoritative configuration and execution standards for localized engineering environments. Adherence to these protocols ensures environmental parity with staging and production clusters and maintains the platform's rigorous quality engineering baseline.

## Virtual Environment Provisioning

Localized development must occur within an isolated, project-specific virtual environment. System-level Python installations are prohibited for application execution.

```bash
# Provision the localized environment
python3 -m venv .venv
source .venv/bin/activate

# Harmonize dependencies with the project baseline
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-docs.txt
```

## Static Analysis and Validation Protocols

Engineers are required to execute continuous validation cycles within the activated environment. The following commands represent the mandatory quality markers:

```bash
# Standardized static analysis and linting
python -m ruff check api coyote tests scripts

# Unit and functional validation
python -m pytest -q

# Strict documentation build verification
python -m mkdocs build --strict
```

## Isolated Application Orchestration

For debugging process-level behaviors independent of the Docker orchestration layer, developers may initiate the core runtimes directly using the following execution strings:

```bash
# Backend Execution (FastAPI)
PYTHONPATH=. python -m uvicorn api.main:app --reload --port 8001

# Frontend Execution (Flask / WSGI)
PYTHONPATH=. python -m wsgi
```

## Standard Development Cycle

To preserve the platform's stability, every engineering contribution must follow a mandated iterative validation loop:

1. **Feature Modification**: Update API contracts, service orchestration, or routing logic.
2. **Focused Validation**: Execute targeted unit tests matching the modified domain.
3. **Static Correction**: Run full repository linting and format verification.
4. **Quality Gate Evaluation**: Pass the multi-family coverage gates and contract integrity checks before commit submission.

```bash
# Example: Focused contract and coverage validation
PYTHON_BIN="$(command -v python)" PYTHONPATH=. bash scripts/run_family_coverage_gates.sh
PYTHON_BIN="$(command -v python)" bash scripts/check_contract_integrity.sh
```

## Git Hook Architecture

The repository utilizes a mandatory pre-commit framework to enforce quality gates at the point of commit creation. This framework is strictly versioned and does not rely on host-specific Python paths.

```bash
# Initialize repository-managed hooks (Execute once per clone)
bash scripts/setup_git_hooks.sh

# Force manual verification across the entire project
python -m pre_commit run --all-files
```

**Security Mandate**: Pre-commit hooks are configured to block commits that violate static analysis thresholds or leak suspected cryptographic material. Any bypass of the pre-commit layer must be explicitly documented and approved by the core engineering maintainers.

## Execution Environment Persistence

All engineering commands must be executed within the project's `.venv` shell. If utilizing automated tools or IDE integrations, ensure the `PYTHON_BIN` environment variable points strictly to the project-local executable.

```bash
export PYTHON_BIN="$(command -v python)"
```
