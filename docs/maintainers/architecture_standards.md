# Runtime Architecture and Engineering Standards

This document establishes the authoritative architectural boundaries and engineering standards for the Coyote3 platform. Adherence to these principles is mandatory for all system modifications and component extensions.

## Core Architectural Boundaries

The platform enforces a strict separation of concerns between presentation and business logic layers:

- **Backend Domain (`api/`)**: The definitive runtime for all business logic, security enforcement, data persistence, and contractual integrity.
- **Web Domain (`coyote/`)**: The presentation and oversight layer. It is prohibited from accessing the database directly and must interact with platform capabilities exclusively through authenticated API routes.
- **Service Isolation**: All business logic must reside within the service and core layers. Routers (FastAPI) and Blueprints (Flask) are reserved strictly for request orchestration and response management.

## Mandated Engineering Standards

Platform code must satisfy the following quality requirements:

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
The platform utilizes a factory pattern for service initialization to ensure dependencies remain explicit and easy to mock during validation:

```python
# Definitive Service Initialization Pattern
def get_user_service() -> UserService:
    return UserService.from_store(get_store())
```

## Boundary Enforcement Mechanisms

Architectural integrity is monitored through a dual-validation process:

1. **Static Enforcement**: Managed through automated Ruff import rules that block unauthorized cross-domain imports.
2. **Behavioral Enforcement**: Verified through integration testing that monitors for cross-layer logic drift.

## Contract Integrity Protocol

Engineers must verify that all database seeds and assay configurations remain synchronized with the platform's backend contracts:

```bash
# Execute contract integrity and documentation verification
PYTHON_BIN="$(command -v python)" bash scripts/check_contract_integrity.sh
```

## Runtime Separation Policy

Platform utilities are strictly partitioned by runtime to prevent dependency leakage:
- `api/core/*`: Pure backend logical rules and utilities.
- `coyote/util/*`: Web and UI runtime helpers.

These modules are not interchangeable. Any shared logic must be evaluated for appropriate promotion to a common dependency or strictly maintained through their respective runtime boundaries.

*Authoritative cross-references:*
- *[Engineering and Refactoring Standards](refactor_guidelines.md)*
- *[Operational Troubleshooting and Remediation](../operations/troubleshooting.md)*
- *[Quality Engineering and Validation Standards](../testing/testing_and_quality.md)*
