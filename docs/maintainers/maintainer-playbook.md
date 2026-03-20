# Maintainer Guide

## Change management policy

1. Keep behavior stable unless change is intentional
2. Prefer explicit contracts over implicit assumptions
3. Add tests for every bug fix and critical feature path
4. Keep CI green before merge
5. Never weaken security checks for convenience

## Recommended PR sequence

1. Domain change in `api/core` and `api/services`
2. Router contract updates in `api/contracts` and `api/routers`
3. Tests (`tests/unit`, `tests/api`)
4. Docs updates in this docs tree
5. Lint and coverage gates

## Required local validation before push

```bash
PYTHONPATH=. python -m ruff check api coyote tests scripts
PYTHONPATH=. python -m pytest -q
PYTHON_BIN="$(command -v python)" PYTHONPATH=. bash scripts/run_family_coverage_gates.sh
```

## What to review in code review

- correctness and regression risk
- permissions and security boundaries
- data migration impact
- observability and logging quality
- test depth and failure modes
- docs updated with new behavior
