# Engineering Operations Guide

This guide provides the mandated procedures for common architectural maintenance, environment verification, and quality enforcement.

## Local Quality Engineering Baseline

Engineers must maintain the following baseline within their localized virtual environment:

```bash
# Run static analysis
PYTHONPATH=. ruff check api coyote tests scripts

# Execute localized unit and functional tests
PYTHONPATH=. pytest -q
```

## Static Type Verification

For security-critical modules, the platform enforces explicit type checking to prevent boundary errors and privilege escalation:

```bash
# Focused verification for identity and notification domains
PYTHONPATH=. mypy --follow-imports=skip --ignore-missing-imports \
  api/security/auth_service.py \
  api/security/password_flows.py \
  api/infra/notifications/email.py \
  api/services/accounts/users.py
```

## Architectural Orchestration (Docker Compose)

The environment-aware orchestration layer must be validated before any configuration changes are committed to the repository:

```bash
# Verify production orchestration schema
docker compose --env-file .coyote3_env -f deploy/compose/docker-compose.yml config -q

# Verify staging orchestration schema
docker compose --env-file .coyote3_stage_env -f deploy/compose/docker-compose.stage.yml config -q

# Verify development and testing schemas
docker compose --env-file .coyote3_dev_env -f deploy/compose/docker-compose.dev.yml config -q
docker compose --env-file .coyote3_test_env -f deploy/compose/docker-compose.test.yml config -q
```

## Documentation Lifecycle

Technical documentation resides within the standalone documentation container and is managed through a strict-mode build process:

```bash
# Synchronize documentation dependencies
.venv/bin/python -m pip install -r requirements-docs.txt

# Execute strict-mode documentation verification
.venv/bin/python -m mkdocs build --strict
```

## Observability and System Telemetry

The platform emits structured log telemetry utilizing standardized prefixes for centralized dashboard ingestion:
- `auth_metric`: Operational outcomes for authentication and identity resolution.
- `mail_metric`: Transactional outcomes for SMTP delivery and token issuance.

Engineers can probe localized telemetry using the following diagnostic command:
```bash
docker logs coyote3_api_local 2>&1 | rg "auth_metric|mail_metric"
```

## Standard Release Protocol

Every platform release must satisfy the following criteria:
1. **Validation**: Pass 100% of the functional and integration test suite.
2. **Orchestration**: Confirm that all Docker Compose configuration schemas are valid.
3. **Manual Alignment**: Verify that the technical manuals built in strict-mode without warnings.
4. **Security Audit**: Ensure that environment templates contain no active secrets or credentials.
5. **Commit Atomic Preservation**: Segment changes into logical `feat`, `chore`, and `docs` commits.

*For detailed architectural specifications, refer to the [Runtime Architecture and Engineering Standards](architecture_standards.md).*
