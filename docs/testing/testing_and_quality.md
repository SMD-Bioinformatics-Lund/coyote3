# Quality Engineering and Validation Standards

## Testing Boundary Diagram

```text
Unit tests
  -> pure logic, contracts, helpers

API router tests
  -> request validation, auth dependencies, response shapes

Integration tests
  -> selected multi-component seams

UI tests
  -> Flask routes, templates, user-facing flows

Docs build / lint / coverage gates
  -> repo-wide quality checks
```

This document defines the test and validation expectations for Coyote3.

## Formal Testing Tiers

The test suite is grouped by runtime boundary:

- **Unit Logic (`tests/unit`)**: pure functions, domain logic, contracts, and services.
- **REST Interface (`tests/api/routers`)**: HTTP boundary behavior and typed payload handling.
- **Integration Layer (`tests/integration`)**: cross-component checks that are still worth keeping.
- **Visual Interface (`tests/ui`)**: Flask route rendering and user-facing flows.

## Primary Execution Commands

Run the validation suite in an isolated virtual environment:

```bash
# Run the full test suite
PYTHONPATH=. python -m pytest -q

# Execute static analysis and linting
PYTHONPATH=. python -m ruff check api coyote tests scripts

# Execute strict documentation build verification
.venv/bin/python -m mkdocs build --strict
```

## Coverage Verification and Quality Gates

Coverage checks enforce minimum thresholds for key logic families.

```bash
# Execute multi-family coverage validation
PYTHON_BIN="$(command -v python)" PYTHONPATH=. bash scripts/run_family_coverage_gates.sh
```

The system applies distinct minimum coverage requirements for `api/core`, `api/services`, `api/routers`, and `coyote/blueprints`.

## Continuous Integration

CI should run these checks:

1. **Static Analysis**: Linting and formatting verification via the Ruff engine.
2. **Functional Validation**: Execution of the complete localized test suite.
3. **Boundary Verification**: Contract and schema consistency evaluation.
4. **Documentation Accuracy**: Strict-mode build verification of operational manuals.
5. **Compose Validation**: verification of Docker Compose configuration where relevant.

## Standards for New Feature Development

- **Logic Separation**: Pure algorithmic logic within `api/core` must maintain 100% test coverage through isolated unit tests.
- **Boundary Mocking**: UI and Integration tests must utilize the `CoyoteApiClient` stubs and `verify_external_api_dependency` mocks to isolate presentation logic from transient network states.
- **Payload Alignment**: All validation datasets must strictly align with the persistent collection snapshots maintained in `tests/fixtures/api/db_snapshots/`.

## Authorization and Permission Validation

All permission-gate testing must operate at the logical boundary being enforced:
- **API Access**: Use the `api_user` mocks to validate FastAPI `Depends` authentication and RBAC logic.
- **UI visibility**: Verify selective rendering of UI components using mocked session contexts.
- **Constraint Matching**: Test datasets must define explicit `permissions` and `denied_permissions` arrays to verify both positive and negative authorization outcomes.

## Performance Checks

Use dedicated profiling or staged environment testing when you need performance numbers.

See also:

- [System Relationships](../architecture/system_relationships.md)
