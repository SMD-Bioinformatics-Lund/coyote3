# System Reference (End-to-End)

This document is the canonical technical reference for the current Coyote3 architecture.

It explains:

- what each layer owns
- why key refactors were made
- how request/response logic flows through the system
- what invariants contributors must preserve

## 1. Current architecture in one view

```text
Browser
  -> Flask (coyote/*): UI routes + template rendering only
    -> API integration client (coyote/integrations/api/*)
      -> FastAPI (api/routes/*): authz + request contracts
        -> Services (api/services/*): business orchestration
          -> Domain + DB handlers (api/domain/*, api/db/*)
            -> MongoDB/infra
```

## 2. Ownership model

### Web layer (`coyote/`)

Owns:

- HTML rendering (Jinja templates)
- view composition and page navigation
- session/UI concerns
- calling backend endpoints through `coyote.integrations.api`

Does not own:

- backend business rules
- persistence logic
- backend authorization policy decisions

### API layer (`api/`)

Owns:

- route contracts and validation
- RBAC enforcement
- workflow orchestration
- data persistence and retrieval
- shared domain models/constants

## 3. Why these refactors were done

The core problem before refactoring was blurred boundaries:

- UI code had backend dependencies
- compatibility shims and fallback paths increased ambiguity
- report generation responsibilities were split unclearly

Refactor direction:

- enforce strict API/UI responsibility split
- remove temporary shims and legacy fallback behavior
- centralize contract validation in service workflows
- add guardrail tests to keep boundaries stable over time

## 4. Key refactor milestones (completed)

Recent commits (newest first):

1. `11ff758`: boundary hardening + docs + maintainability guardrails
2. `d5f4140`: strict workflow contracts + legacy fallback removal
3. `c11a799`: utility ownership consolidation and cleanup
4. `2b1b20c`: removed `api.models.user` shim
5. `fdf1f77`: moved shared ownership under `api/domain`
6. `65bae89` + `476308e`: clarified report boundary (Flask render / API persist)

## 5. Runtime logic flows

### 5.1 Authentication flow

1. User submits credentials on Flask login route.
2. Web calls API `/api/v1/auth/login`.
3. API validates credentials and returns user/session token payload.
4. Flask stores session context and API cookie.
5. Subsequent web calls include API auth token/cookie through integration client.

Important invariant:

- API no longer relies on legacy Flask-session fallback for authentication.

### 5.2 DNA report preview/save flow

1. Web route collects request context and calls API report endpoint.
2. API route loads sample + assay config, enforces access.
3. Workflow contract validation runs (strict `400` on invalid inputs).
4. Service builds report payload/snapshot data.
5. For save actions, API persists report metadata and snapshot records.
6. Web receives structured response and renders UI.

### 5.3 RNA fusion/report flow

1. API normalizes RNA filter keys in workflow service.
2. Contract validation rejects malformed filter payloads early.
3. Service builds query context, fetches fusions, enriches annotations.
4. API returns stable response payload used by web templates/pages.

## 6. Contract and error model

### Contract validation

- `api/services/workflow/contracts.py` enforces strict input contracts.
- Contract violations produce HTTP `400` with stable error payload.

### Error handling

- API unexpected exceptions are mapped to consistent JSON error response.
- Web layer has its own `AppError` and Flask error handlers for UI responses.

## 7. Module map (what goes where)

### API modules

- `api/routes/*`: endpoint adapters
- `api/services/*`: business/workflow orchestration
- `api/domain/*`: shared domain entities and constants
- `api/db/*`: handler-level data access
- `api/errors/*`: API error types

### Web modules

- `coyote/blueprints/*`: UI page routes by feature area
- `coyote/templates/*`: Jinja templates
- `coyote/integrations/api/*`: web-to-api transport boundary
- `coyote/services/auth/*`: web session handling
- `coyote/errors/*`: web error types/handlers

## 8. Guardrails now enforced

- `tests/web/test_web_api_boundary.py`
  - fails if `coyote/*` imports `api.*` directly
- `tests/api/test_route_module_organization.py`
  - enforces route module docstrings and versioned API path prefixes
- `tests/api/test_api_route_security.py`
  - verifies non-public API routes are guarded
- `tests/api/test_api_route_auth_matrix.py`
  - dynamic check that protected routes fail closed without auth

## 9. Testing strategy and standards

Current suite organization:

- `tests/api/*`: API behavior and architecture guardrails
- `tests/web/*`: web boundary/UI guardrails

Required checks before merge:

```bash
PYTHONPYCACHEPREFIX=/tmp/coyote3_pycache PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m compileall -q api coyote tests
PYTHONPYCACHEPREFIX=/tmp/coyote3_pycache PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q tests
```

## 10. Contributor rules (non-negotiable)

1. Do not add `coyote -> api.*` direct imports.
2. Keep business logic in API services/domain layers.
3. Keep web routes focused on rendering and user flow.
4. Add/update tests for every route change (success + permission + validation + error path).
5. Update handbook docs in the same change when behavior changes.

## 11. Open technical debt (next steps)

1. Split oversized modules for long-term maintainability:
   - `api/routes/admin.py`
   - `api/routes/dna.py`
   - `api/utils/common_utility.py`
2. Expand endpoint-level tests per route family:
   - DNA, RNA, reports, admin, public, home
3. Wire strict CI quality gates for lint/type/test execution.
