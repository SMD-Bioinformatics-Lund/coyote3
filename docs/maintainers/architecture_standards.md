# Runtime Architecture and Engineering Standards

This document defines the architectural boundaries and engineering standards for Coyote3. Follow these rules for all code changes.

## Core Architectural Boundaries

Keep presentation code and business logic separate:

- **Backend Domain (`api/`)**: business logic, security, persistence, and contracts.
- **Web Domain (`coyote/`)**: presentation only. It must not access MongoDB directly and must call the API over HTTP.
- **Service Isolation**: business logic belongs in services and core modules. Routers and blueprints handle request and response flow.

## Mandated Engineering Standards

Platform code must satisfy these requirements:

- **Path Cleanliness**: Prohibited use of absolute system paths or machine-specific home directories.
- **Output Protocols**: Explicit prohibition of stdout `print()` statements in runtime paths; all diagnostic information must flow through the structured logging layer.
- **Error Handling**: Use of generic or uninformative error text is forbidden. All exceptions must provide contextual diagnostic detail.
- **Dependency Isolation**: Direct imports from `api/` into `coyote/` are prohibited. The two runtimes must remain decoupled and interact through the API boundary.
- **Persistence Encapsulation**: Direct MongoDB driver interactions are restricted to the infrastructure layer. Application logic must utilize managed handlers.

## Persistence and Dependency Composition

### Composition Root
The `store` object serves as the architectural composition root, managing runtime adapters and collection-scoped handlers.
- **Handler Isolation**: Each persisted collection is managed by a dedicated handler within `api/infra/mongo/handlers/`.
- **Workflow Management**: Multi-collection interactions belong exclusively to the `api/services/` domain.
- **Dependency Declaration**: Services and routers must depend on explicit handler or service interfaces rather than raw datastore connections.

### Service Factory Architecture
Use explicit service factories so dependencies stay easy to trace and test:

```python
# Service initialization pattern
def get_user_service() -> UserService:
    return UserService.from_store(get_store())
```

## Boundary Enforcement Mechanisms

These boundaries are checked in two ways:

1. **Static Enforcement**: Managed through automated Ruff import rules that block unauthorized cross-domain imports.
2. **Behavioral Enforcement**: Verified through integration testing that monitors for cross-layer logic drift.

## Contract Integrity Protocol

Keep seed data and assay configurations aligned with backend contracts:

```bash
# Execute contract integrity and documentation verification
PYTHON_BIN="$(command -v python)" bash scripts/check_contract_integrity.sh
```

## Runtime Separation Policy

Platform utilities are strictly partitioned by runtime to prevent dependency leakage:
- `api/core/*`: Pure backend logical rules and utilities.
- `coyote/util/*`: Web and UI runtime helpers.

These modules are not interchangeable. Any shared logic must be evaluated for appropriate promotion to a common dependency or strictly maintained through their respective runtime boundaries.

Related references:
- *[Engineering and Refactoring Standards](refactor_guidelines.md)*
- *[Operational Troubleshooting and Remediation](../operations/troubleshooting.md)*
- *[Quality Engineering and Validation Standards](../testing/testing_and_quality.md)*
