# Coyote3 Architecture Overview

This document defines the architecture of Coyote3. It explains what the system is, why it is structured this way, how the major parts interact, and how engineers are expected to extend and maintain it.

## System Summary

Coyote3 is intentionally organized as two applications inside one repository:

1. `api/`: a FastAPI backend that owns business rules, security, audit, and persistence
2. `coyote/`: a Flask UI that renders pages and consumes the backend over HTTP

The API is the primary backend contract. The UI is a client of that contract.

This distinction is the foundation of the repository:

- the API owns policy, workflow logic, and persistence
- the UI owns presentation, page flow, and browser interaction

This is not a convenience split. It is a deliberate separation of concerns:

- the API exists so that business rules, access control, persistence, and audit are implemented once and enforced consistently
- the UI exists so that browser interactions, templates, forms, and user flow remain presentation-oriented
- Mongo is owned by the backend so data access policy is not fragmented across applications
- shared utilities remain lightweight so they do not become a hidden third application

## Architectural Decisions

These are the core architectural decisions behind the repository.

### The API has a single canonical runtime entrypoint

The backend starts from `uvicorn api.main:app`.

This matters because a backend needs one authoritative assembly root. Startup behavior, middleware registration, router registration, error handling, OpenAPI behavior, and lifecycle hooks all need to be discoverable in one place. When engineers work around that with parallel app entrypoints, the runtime becomes harder to debug and harder to deploy safely.

### HTTP routing is owned by `api/routers/`

Route registration is centralized under `api/routers/`.

This keeps the transport layer explicit. If someone needs to understand what the API exposes, they should start in the routers. We do not scatter active HTTP route ownership across legacy files, data handlers, or UI code.

### Contracts are owned by `api/contracts/`

API contracts are defined under `api/contracts/`.

This is where the transport boundary becomes explicit. A contract tells clients what they can send, what they will receive, and what the API considers valid. Contracts are not persistence models and they are not workflow services.

### Mongo runtime ownership belongs to the backend

Mongo runtime ownership is under `api/db/mongo/`.

This is deliberate. Database bootstrap, collections, indexes, and low-level persistence concerns belong to the backend runtime, not to the UI and not to generic shared helpers.

### The UI talks to the API over HTTP

The UI calls the API through `coyote/services/api_client/`.

This keeps the UI honest. It prevents the Flask application from turning into a second backend with hidden business logic or direct database access. The UI renders pages and drives user flows, but the API remains the authority for behavior and policy.

### UI-to-Mongo shortcuts are intentionally blocked

Direct UI-to-Mongo access is blocked by repository boundaries and tests.

This is one of the most important guardrails in the system. If the UI can bypass the API and talk to persistence directly, then access control, workflow rules, audit, and transport contracts all start to drift.

### Development runtime is treated as a real system, not a toy setup

The development and portable Docker stacks are both part of the intended engineering workflow. They are not optional side experiments. Startup, health, and connectivity need to stay reliable because they are the fastest way to validate that the system still behaves as a whole.

### The test suite is part of the architecture

The repository test suite exists to protect boundaries, not just logic. Tests are not only there to validate happy-path behavior. They also exist to stop architecture drift:

- API tests protect route behavior and authorization
- UI tests protect page flow and API integration
- integration tests protect cross-layer seams
- unit tests protect isolated workflow logic

## Runtime Components

```text
[Browser]
   |
   v
[Flask UI: coyote/]
   |
   v
[FastAPI API: api/]
   |
   v
[MongoDB]
```

Optional runtime support:

- Redis, where enabled by deployment configuration
- asset build/watch tooling in development

## Backend Request Flow

Backend request flow follows one rule: transport, domain logic, and persistence stay separated.

```text
router -> dependency/auth -> service/core workflow -> repository -> mongo handler -> MongoDB
```

Layer roles:

- `api/routers/`: HTTP parsing, response shaping, dependency binding
- `api/deps/`: reusable route dependencies
- `api/contracts/`: request and response models
- `api/core/` and `api/services/`: workflow and business logic
- `api/repositories/`: repository-facing abstraction used by routes/services
- `api/infra/db/`: Mongo collection handlers
- `api/db/mongo/`: Mongo client, database bootstrap, index setup
- `api/middleware.py`: request authentication, request-id propagation, request/mutation audit wrapping
- `api/openapi.py`: OpenAPI security schema customization

If the term `contract` is unfamiliar, it means the typed request and response schema at the API boundary. Contracts are explained in detail in [api/concepts-and-layering.md](api/concepts-and-layering.md).

Preferred extension pattern:

```text
router -> Depends(get_<domain>_service) -> service -> repository -> Mongo handler
```

Representative route families already following this pattern:

- admin users, roles, and permissions
- admin resource management flows
- home sample context flows
- dashboard summary flows
- coverage read flows
- sample-centric genomics flows:
  - `small_variants`
  - `fusions`
  - `cnvs`
  - `translocations`
  - `biomarkers`
- `reports`
- shared `classifications` and `annotations`

## Logging, Audit, And Error Handling

Observability is part of the application design.

### Application logging

Repository logging is configured through `logging_setup.py` and exposed through `shared/logging.py`.
Use `get_logger(...)` for operational logging and `emit_audit_event(...)` for structured audit events.

The logging model separates concerns:

- application logs explain control flow, failures, and operational context
- audit logs record user-visible actions, access checks, request outcomes, and mutation outcomes
- file handlers persist both categories to the configured log directory so operators can review events outside the process console

### Audit event ownership

Audit is not limited to explicit admin mutations.
The system records:

- API request outcomes
- API access-control decisions
- API mutation results
- API validation failures
- API unhandled exceptions
- UI request outcomes
- UI upstream API failures
- UI error-page rendering events

The admin audit page reads the structured audit log and renders the fields that matter to operators:
actor, action, status, duration, target context, and additional details.

### Error-page model

The UI distinguishes between two failure classes:

- page-load failures, where the route cannot build the page because required backend context is missing or invalid
- in-page mutation failures, where the user remains on a valid page and receives a flash message

Page-load failures must raise typed application errors from `coyote/errors/exceptions.py`.
The global Flask error handlers render `coyote/templates/errors.html` with:

- HTTP status code
- user-facing summary
- optional technical details
- request id for traceability

Mutation failures should not redirect to a generic error page.
They should keep the user in context, emit audit information, and use the standardized flash helpers in `coyote/services/api_client/web.py`.

## UI Request Flow

The UI remains presentation-focused by design.

```text
Flask blueprint -> UI api_client helper -> HTTP call to API -> API response -> template render
```

Layer roles:

- `coyote/blueprints/`: page flow, form handling, redirects, view orchestration
- `coyote/services/api_client/`: endpoint building, HTTP transport, cookie/header forwarding, request-scoped client lifecycle
- `coyote/templates/`: rendering
- `coyote/static/`: static UI assets

Auth transport model:

- API login creates the session and sets the HttpOnly API session cookie
- Flask relays that cookie to the browser after successful login
- Flask forwards `Authorization: Bearer <api_session_token>` on server-side API calls
- the UI does not depend on bearer tokens embedded in JSON login payloads

## Ownership Rules

### API owns

- authentication and authorization
- business logic
- audit event generation
- mutation rules
- Mongo access

### UI owns

- page composition
- browser interaction flow
- template rendering
- translating user actions into API calls

### Shared utilities may own

- low-level neutral helpers
- logging helpers
- constants and types that do not pull business logic across boundaries

## Dependency Rules

Allowed:

- `api/routers/*` importing contracts, deps, services, repositories
- `coyote/blueprints/*` importing API client helpers
- tests importing any layer they explicitly validate

Not allowed:

- `coyote/*` importing `api/infra/db/*` or Mongo drivers
- `api/routers/*` embedding raw Mongo queries
- `shared/*` depending on Flask or FastAPI runtime details

## Repository Layout In Practice

The structure is intentionally explicit:

```text
api/
  main.py
  config.py
  lifecycle.py
  routers/
  contracts/
  deps/
  services/
  repositories/
  core/
  db/mongo/
  infra/
  security/
  audit/

coyote/
  blueprints/
  templates/
  static/
  services/api_client/

tests/
  api/
  ui/
  integration/
  unit/
  fixtures/
```

## Why This Structure Is Maintainable

This structure is maintainable because it gives each concern an obvious home and makes incorrect cross-layer shortcuts easier to spot in review.

In practice, this means:

- route files stay thin and predictable
- route dependencies can be swapped in tests without monkeypatching global handler bags
- transport contracts are explicit and reviewable
- persistence logic is localized
- UI cannot quietly bypass policy enforcement
- tests mirror the repository boundaries
- deployment and runtime entrypoints are unambiguous

## How To Maintain It

When changing code, engineers are expected to preserve the structure rather than work around it. The maintenance rules are:

1. Change the smallest layer that actually owns the behavior.
2. Do not solve a backend problem in Flask.
3. Do not solve a persistence problem in a router.
4. Prefer route -> service -> repository over route -> handler chaining.
5. Add tests in the same scope as the behavior you changed.
6. Update documentation when you change architecture, startup, boundaries, or extension patterns.
7. In tests, prefer dependency overrides and service stubs over patching private router globals.

## How To Add New Capability

### Add a new backend resource

1. Define or extend contracts in `api/contracts/`.
2. Add or extend the router in `api/routers/`.
3. Implement workflow logic in `api/core/` or `api/services/`.
4. Add repository methods in `api/repositories/`.
5. Add Mongo handler support in `api/infra/db/`.
6. Add tests in `tests/api/`, `tests/unit/`, and `tests/integration/`.

Why this order matters:

- contracts make the boundary explicit first
- routers expose the capability
- services keep workflow logic out of transport code
- repositories localize persistence concerns
- tests validate each responsibility at the correct layer

### Add a new genomics resource

Prefer resource ownership over assay buckets:

1. Add or extend a sample-centric router such as `api/routers/small_variants.py`, `api/routers/fusions.py`, or `api/routers/cnvs.py`.
2. Keep assay or omics type as context, not as the top-level route family.
3. Put shared tiering in `api/services/resource_classification_service.py`.
4. Put shared comment/annotation mutations in `api/services/resource_annotation_service.py`.
5. Put report preview/save orchestration in `api/services/report_service.py`.

Current canonical pattern:

```text
/api/v1/samples/{sample_id}/small-variants
/api/v1/samples/{sample_id}/cnvs
/api/v1/samples/{sample_id}/translocations
/api/v1/samples/{sample_id}/fusions
/api/v1/samples/{sample_id}/biomarkers
/api/v1/samples/{sample_id}/classifications
/api/v1/samples/{sample_id}/annotations
/api/v1/samples/{sample_id}/reports/{report_type}
```

### Add a new UI feature

1. Add or extend a blueprint under `coyote/blueprints/`.
2. Add or extend an API client helper under `coyote/services/api_client/`.
3. Render through templates.
4. Add UI tests in `tests/ui/`.
5. If the feature depends on a new backend route, add the backend slice first.

## Documentation Map

Use the docs in this order if you are new to the system:

1. This file for the big picture
2. [architecture/API_ARCHITECTURE.md](architecture/API_ARCHITECTURE.md) for backend structure
3. [api/concepts-and-layering.md](api/concepts-and-layering.md) for API concepts from first principles
4. [development/developer-guide.md](development/developer-guide.md) for daily engineering rules
5. [ui/ui-surface-and-permissions.md](ui/ui-surface-and-permissions.md) for UI routes, elements, and permissions

## Working Definition Of Done

A feature or architectural change is complete when:

- runtime entrypoints still work
- boundary rules are preserved
- relevant docs are updated
- the full suite passes
- Docker startup still works if deployment behavior changed
