# Runtime Architecture Standards

## Codebase Boundaries

- `api/` is the authoritative backend runtime for business logic, security,
  contracts, and persistence operations.
- `coyote/` is the web runtime and must call backend capabilities through API
  routes and service clients, not direct database access.
- Runtime logic must stay in services/core layers. Routers and blueprints are
  orchestration layers.

## Runtime Quality Rules

The codebase enforces the following standards for runtime code:

- no deprecated contract import paths
- no runtime `print()` statements in Python runtime paths
- no generic catch-all runtime error text
- no hardcoded user-home absolute paths in runtime Python code
- no compatibility-shim markers in runtime Python code
- no direct `api.*` imports from `coyote/*`
- no direct Mongo driver imports outside infra/common/script/test ownership zones
- seed and assay consistency validation must pass
- generated collection-contract documentation must be up to date

## Persistence Rules

- `store` is the backend composition root. It owns the runtime adapter,
  collection-scoped handlers, and shared connections.
- `api/deps/handlers.py` is the only low-level module that should expose the
  shared `store` to the rest of the backend.
- `api/deps/services.py` is the composition root for service objects.
- Collection-scoped persistence lives in `api/infra/mongo/handlers/`.
  Each handler owns one collection and should only perform operations for that
  collection.
- Multi-collection behavior belongs in `api/services/*`, grouped by workflow or
  use case.
- Runtime business logic should depend on explicit handlers/services, not raw
  Mongo collections passed through call chains.
- Datastore selection belongs to runtime bootstrap and handler wiring.
- Provider-native IDs, query syntax, exceptions, and transaction details stay in
  `api/infra/mongo/handlers` and closely related infra helpers.
- Services and workflows return domain-shaped data, not raw datastore
  records where avoidable.
- Avoid reintroducing pass-through repository facades or `ports.py` indirection
  for simple handler access.
- Avoid constructor fallbacks, compatibility shims, and hidden `or ...`
  dependency defaults in runtime code.

## Service Factory Pattern

Prefer this pattern:

```python
# api/deps/services.py
def get_user_service() -> UserService:
    return UserService.from_store(get_store())
```

```python
# api/services/accounts/user_profile.py
class UserService:
    @classmethod
    def from_store(cls, store):
        return cls(user_handler=store.user_handler)
```

This keeps:

- `store` at the composition boundary
- service dependencies explicit
- factory code concise

Avoid:

- importing `store` directly in many service modules
- service constructors with hidden fallback defaults
- handler lookup spread across routers

## Boundary Enforcement

- Runtime boundaries are enforced twice:
  - lint-time through Ruff banned-import rules
  - test-time through integration guardrails for cross-layer drift
- Prefer lint-time failures for architectural mistakes whenever a rule can be
  expressed as an import restriction.

## Required Validation Command

```bash
PYTHON_BIN="${PYTHON_BIN:-$(command -v python)}" \
bash scripts/check_contract_integrity.sh
```

## Layer Separation Policy

Helper modules are intentionally split by runtime:

- `api/core/*` for pure backend helpers and rules
- `coyote/util/*` for web/UI runtime helpers

These modules are not interchangeable and should remain separate to preserve
runtime boundaries and dependency isolation.

## Authoritative References

- [Refactor Guidelines](refactor-guidelines.md)
- [Maintenance And Quality](../operations/maintenance-and-quality.md)
- [Testing And Quality](../testing/testing-and-quality.md)
