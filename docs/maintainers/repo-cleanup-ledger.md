# Repo Cleanup Ledger

This ledger records cleanup decisions so maintainers can see what was removed,
what was consolidated, and what is intentionally kept.

## Removed And Consolidated

- Retired duplicate operations pages:
  - `center-onboarding-pack.md`
  - `first-day-guide.md`
- Consolidated operational command flows into:
  - [Operations / Maintenance And Quality](../operations/maintenance-and-quality.md)
  - [Operations / Initial Deployment Checklist](../operations/initial-deployment-checklist.md)
- Removed runtime debug residue in app code (`print(...)`).

## Guardrails Enforced

The quality gate (`scripts/check_contract_integrity.sh`) now enforces:

- no deprecated contract imports
- no runtime `print()` statements in Python runtime paths
- no generic catch-all runtime log text
- no hardcoded user-home absolute paths in runtime Python code
- no compatibility-shim markers in runtime Python code
- seed/assay consistency validation
- collection-contract documentation regeneration

Run:

```bash
PYTHON_BIN="${PYTHON_BIN:-$(command -v python)}" \
bash scripts/check_contract_integrity.sh
```

## Intentionally Kept

These modules are intentionally separate and are not treated as duplicate code:

- `api/utils/*`:
  backend/runtime helpers for API service execution.
- `coyote/util/*`:
  UI/web blueprint helpers for Flask-side rendering and view workflows.

Reason: they run in different app layers with different dependencies and request
contexts.

## Authoritative References

- [Refactor Guidelines](refactor-guidelines.md)
- [Maintenance And Quality](../operations/maintenance-and-quality.md)
- [Testing And Quality](../testing/testing-and-quality.md)
