# Coyote3 Architecture Overview

## Audience
This document is for backend engineers, UI engineers, DevOps operators, security reviewers, and technical auditors.

## Scope
This manual defines the current architecture of Coyote3 as deployed and maintained today. It covers runtime units, code boundaries, request flows, policy enforcement, audit ownership, data and configuration patterns, and extension points.

## Key Concepts
Terminology used in this document is aligned with [GLOSSARY.md](GLOSSARY.md).

## Where To Look In Code
- API entrypoint and wiring: `api/app.py`, `api/settings.py`, `api/extensions.py`
- API route layer: `api/routes/`
- API contracts: `api/contracts/`
- API domain/workflow logic: `api/core/`
- API security: `api/security/`
- API audit events: `api/audit/`
- API persistence and integrations: `api/infra/db/`, `api/infra/external/`
- UI routes and rendering: `coyote/blueprints/`, `coyote/templates/`
- UI-to-API transport: `coyote/services/api_client/`

## Operational Implications
- The API is the authoritative layer for business logic, RBAC, audit, and MongoDB access.
- The Flask UI is presentation-first and calls API endpoints over HTTP.
- MongoDB is the persistence layer and must remain MongoDB 3.4-compatible in query and update patterns.

---

## 1. System Context (C4 Level 1 Narrative)
Coyote3 is a clinical genomics application used by analysts, clinical geneticists, and administrators to review samples, interpret variants, configure policies, and generate reports. In context terms, the system sits between human clinical workflows and governed genomic datasets.

Textual context diagram:

```text
[Clinical User / Analyst / Admin]
            |
            v
      [Flask UI (coyote)]
            |
            v
      [FastAPI API (api)]
            |
            v
       [MongoDB datastore]
            |
            +--> [Audit and operational logs]
```

Core context rules:
1. Clinically meaningful decisions are executed in API workflows.
2. User access decisions are enforced in API security dependencies.
3. Every sensitive mutation path emits backend-owned audit events.

---

## 2. Container Architecture (C4 Level 2 Narrative)
Coyote3 runs as separated runtime units:

1. **UI container (`coyote3_web` / `coyote3_dev_web`)**
- Flask, Jinja, blueprint routing, template rendering.
- Handles browser sessions and page orchestration.
- Calls API using `coyote/services/api_client/*`.

2. **API container (`coyote3_api` / `coyote3_dev_api`)**
- FastAPI route handling.
- Typed contract enforcement via Pydantic models.
- Authentication, RBAC, domain workflows, audit emission.
- Owns persistence access through infra handlers.

3. **MongoDB container**
- Persists samples, variants, reports, policies, schemas, and identity metadata.
- Query patterns must stay MongoDB 3.4-compatible.

4. **Optional support containers (environment-dependent)**
- Redis (if enabled for caching/session support).
- Tailwind watcher in development mode.

The architecture intentionally avoids direct UI-to-Mongo access and direct UI-to-API-internal imports. That boundary ensures stable policy enforcement and auditable state transitions.

### 2.1 Redis Caching Strategy
- Redis is used as a shared cache backend for both UI and API runtimes.
- API cache scope:
  - sample list retrieval (`api/infra/db/samples.py`) with keyed caching and TTL.
- UI cache scope:
  - dashboard payload snapshots and other explicit `app.cache` call sites.
- Cache keys are namespaced per runtime (`coyote3_cache:api:*`, `coyote3_cache:web:*`) to avoid collisions.
- Cache backend behavior is explicit via config:
  - `CACHE_ENABLED=1|0`
  - `CACHE_REQUIRED=1|0`
  - `CACHE_REDIS_URL`
  - `CACHE_REDIS_CONNECT_TIMEOUT`
  - `CACHE_REDIS_SOCKET_TIMEOUT`
- If `CACHE_REQUIRED=1`, startup fails when Redis is unreachable.
- If `CACHE_REQUIRED=0`, runtime falls back to disabled cache backend (functional behavior preserved, performance reduced).

---

## 3. Layering and Ownership Boundaries

### 3.1 API layering
The backend uses explicit layers with clear placement rules.

1. `api/routes/`
- HTTP adapters only.
- Responsibilities: parse request parameters, bind dependencies, call core functions, return typed contracts.
- Non-responsibilities: direct workflow branching, direct Mongo queries.

2. `api/contracts/`
- Request/response schemas.
- Defines API shape as explicit contracts, used both at runtime and OpenAPI generation.

3. `api/core/`
- Business logic and workflow orchestration.
- Includes domain-specific logic (`dna`, `rna`, `reporting`, `coverage`, `workflows`, `interpretation`, `admin`, `public`).

4. `api/security/`
- Authentication services and access control dependencies.
- Role/permission resolution and enforcement hooks.

5. `api/audit/`
- Audit event creation and write helpers.
- Backend is authoritative owner of audit lifecycle.

6. `api/infra/db/`
- Mongo handlers/repositories.
- Collection-oriented read/write operations.

7. `api/infra/external/`
- External system clients (LDAP and annotation providers).

8. `api/domain/`
- Domain models and types.
- No route/framework binding, no persistence orchestration.

### 3.2 UI layering

1. `coyote/blueprints/`
- Page orchestration and request->template mapping.
- No backend policy ownership.

2. `coyote/templates/` and blueprint templates
- Rendering only.

3. `coyote/services/api_client/`
- Centralized API transport logic, endpoint paths, header forwarding, error wrapping.

4. `coyote/util/`
- UI-scoped utility behavior (formatting, rendering helpers).

### 3.3 Boundary enforcement
Boundary integrity is verified by contract tests:
- `tests/contract/test_ui_forbidden_backend_imports.py`
- `tests/contract/test_ui_forbidden_mongo_usage.py`

These tests fail when UI code imports backend internals or Mongo/BSON drivers directly.

---

## 4. API Contracts and Response Model Strategy
All API routes under `/api/v1/*` expose explicit response models from `api/contracts/*`. Contract definitions are versioned through source control and reviewed as compatibility surfaces.

Practical effects:
1. Response shape drift is visible at review time.
2. OpenAPI output remains deterministic.
3. UI consumers have stable typed expectations.
4. Contract tests can target exact fields and envelopes.

Representative contract modules:
- `api/contracts/samples.py`
- `api/contracts/dna.py`
- `api/contracts/rna.py`
- `api/contracts/reports.py`
- `api/contracts/admin.py`

Representative route modules:
- `api/routes/samples.py`
- `api/routes/dna.py`
- `api/routes/rna.py`
- `api/routes/reports.py`

---

## 5. UI to API Interaction Model
UI communication with API is centralized in `coyote/services/api_client/`.

### 5.1 Request flow
1. Browser request hits Flask blueprint route.
2. Blueprint gathers user input and page context.
3. Blueprint/helper calls API endpoint through `CoyoteApiClient`.
4. API validates identity/access, executes workflow, returns typed payload.
5. Flask renders template or returns redirect/JSON depending on endpoint style.

### 5.2 Header and session forwarding
`forward_headers()` in `coyote/services/api_client/api_client.py` forwards cookie context and adds bearer token when available (`API_SESSION_COOKIE_NAME`).

### 5.3 Routing rule for prefixed blueprints
When a blueprint is registered with `url_prefix`, route decorators must be prefix-relative.

Example:
```python
app.register_blueprint(home_bp, url_prefix="/samples")

@home_bp.route("")
def samples_home():
    ...
```

Defining `@home_bp.route("/samples")` in this case would create `/samples/samples`, which is invalid by design and treated as a routing bug.

---

## 6. Authentication and Session Ownership
Authentication and access checks are API-authoritative.

1. UI owns browser-facing session experience (login/logout flow and redirects).
2. API owns credential validation and access decisions per request.
3. UI transport passes session context to API; API never trusts UI as policy authority.

Key modules:
- API auth and access: `api/security/auth_service.py`, `api/security/access.py`
- UI session handling: `coyote/services/auth/user_session.py`
- UI API headers/transport: `coyote/services/api_client/api_client.py`

Security implication: every request affecting clinical or administrative state is validated by API route dependencies and permission checks before persistence operations execute.

---

## 7. RBAC and Permission Evaluation
Coyote3 uses role-based access with explicit permission checks.

Common pattern:
1. Resolve authenticated user context.
2. Load role grants and explicit permission entries.
3. Apply route-level requirements.
4. Deny request if missing required permission or level.

Permission enforcement is route-local but policy resolution is centralized in backend security modules. UI visibility may hide unavailable actions, but API remains the final enforcement point.

---

## 8. Audit Ownership and Event Lifecycle
Audit generation is backend-owned and tied to API-handled operations.

### 8.1 Lifecycle
1. Request reaches API route.
2. Authentication and authorization pass.
3. Core workflow mutates or reads governed state.
4. Audit event is emitted by backend event helper.
5. Response is returned to caller.

### 8.2 Ownership rule
UI does not authoritatively write audit records. UI may display audit data, but event creation, sequencing, and integrity are backend responsibilities.

Primary backend module:
- `api/audit/access_events.py`

---

## 9. Schema-Driven Configuration and Versioned Documents
Coyote3 supports schema-driven administrative configuration and version-tracked records for controlled change.

### 9.1 Schema-driven configuration
- Schema documents define expected structures for configurable entities (roles, permissions, assay settings, etc.).
- API validates and persists these entities; UI provides editing interfaces.

### 9.2 Versioning and changelog behavior
- Versioned records keep revision metadata and change context.
- Rewind/recovery operations rely on stored version history and controlled update semantics.

### 9.3 Design intent
- Preserve traceability and reproducibility.
- Support reversible administration changes when clinically safe.
- Avoid silent policy drift.

---

## 10. Data Access Strategy and MongoDB 3.4 Constraints
All persistence operations must pass through `api/infra/db/*` handlers.

Constraints due to MongoDB 3.4 compatibility:
1. Avoid unsupported modern operators and pipeline assumptions.
2. Keep query patterns explicit and index-aware.
3. Use incremental evolution for document shape changes.
4. Validate compatibility in tests and release checks.

Operationally, this means schema evolution is treated as controlled rollout work with explicit validation and rollback planning.

---

## 11. Runtime Configuration and Environment Boundaries
Configuration is environment-driven and split by runtime concern.

- API runtime config: API auth, Mongo URI, report paths, audit behavior.
- UI runtime config: Flask session/cookie settings, API base URL, UI rendering flags.
- Deploy-time composition: `deploy/compose/docker-compose.yml` and `deploy/compose/docker-compose.dev.yml` separate API and UI services.

Route/path behavior behind reverse proxies is supported through prefix handling in Flask initialization (`SCRIPT_NAME` support).

---

## 12. Extension Points
A new domain feature should extend all relevant layers in order.

1. Define/extend contract models in `api/contracts/`.
2. Add or update route endpoint in `api/routes/`.
3. Implement workflow logic in `api/core/`.
4. Add/extend persistence handlers in `api/infra/db/`.
5. Add audit emission if operation is security/clinical relevant.
6. Add UI integration call in `coyote/services/api_client/`.
7. Add/adjust UI blueprint rendering path and templates.
8. Add tests across unit, api, web, and contract layers.
9. Update docs in `docs/` consistently.

This sequence keeps the system cohesive and prevents UI-local policy forks.

---

## 13. Failure Modes and Recovery Posture

### 13.1 API unavailable
- UI route handlers should fail gracefully and show actionable messages.
- Operators validate API health endpoint and dependency connectivity.

### 13.2 Contract mismatch
- Symptoms: UI rendering failures or missing fields.
- Mitigation: update `api/contracts/*`, route implementation, and UI client usage in a single reviewable change.

### 13.3 Permission denial mismatch
- Symptoms: UI shows action, API denies request.
- Mitigation: keep UI display hints aligned with backend policy; API remains source of truth.

### 13.4 Data-shape inconsistency
- Symptoms: workflow errors for old records.
- Mitigation: normalize in `api/core/workflows/*`, validate in tests, run controlled data evolution scripts.

---

## 14. Architecture Governance Checklist
Use this checklist before merging architecture-impacting changes:

- [ ] Correct layer placement (`routes`, `contracts`, `core`, `security`, `infra`, `audit`)
- [ ] UI contains no backend-internal imports
- [ ] API contract updates included for response/request changes
- [ ] RBAC and audit behavior validated for affected routes
- [ ] MongoDB 3.4 compatibility validated for new queries/updates
- [ ] Tests added or updated across affected suites
- [ ] Docs updated in architecture, developer, API, or UI manuals as needed

---

## 15. Related Documents
- [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)
- [API_REFERENCE.md](API_REFERENCE.md)
- [SECURITY_MODEL.md](SECURITY_MODEL.md)
- [DATA_MODEL.md](DATA_MODEL.md)
- [DEPLOYMENT_AND_OPERATIONS.md](DEPLOYMENT_AND_OPERATIONS.md)
- [TESTING_STRATEGY.md](TESTING_STRATEGY.md)
- [EXTENSION_PLAYBOOK.md](EXTENSION_PLAYBOOK.md)
