# Repository Standards

## Codebase Boundaries

- `api/` is the authoritative backend runtime for business logic, security,
  contracts, and persistence operations.
- `coyote/` is the web runtime and must call backend capabilities through API
  routes and service clients, not direct database access.
- Runtime logic must stay in services/core layers. Routers and blueprints are
  orchestration layers.

## Runtime Quality Rules

The repository enforces the following standards for runtime code:

- no deprecated contract import paths
- no runtime `print()` statements in Python runtime paths
- no generic catch-all runtime error text
- no hardcoded user-home absolute paths in runtime Python code
- no compatibility-shim markers in runtime Python code
- seed and assay consistency validation must pass
- generated collection-contract documentation must be up to date

## Persistence Rules

- Domain code depends on repository ports, not datastore implementations.
- Datastore selection belongs to runtime bootstrap and dependency wiring.
- Provider-native IDs, query syntax, exceptions, and transaction details stay in
  `api/infra`.
- Services and core workflows return domain-shaped data, not raw datastore
  records.
- New persistence work must follow the portability plan.

## Required Validation Command

```bash
PYTHON_BIN="${PYTHON_BIN:-$(command -v python)}" \
bash scripts/check_contract_integrity.sh
```

## Layer Separation Policy

Helper modules are intentionally split by runtime:

- `api/utils/*` for backend/API runtime helpers
- `coyote/util/*` for web/UI runtime helpers

These modules are not interchangeable and should remain separate to preserve
runtime boundaries and dependency isolation.

## Authoritative References

- [Refactor Guidelines](refactor-guidelines.md)
- [Maintenance And Quality](../operations/maintenance-and-quality.md)
- [Testing And Quality](../testing/testing-and-quality.md)
