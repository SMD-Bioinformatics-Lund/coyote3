# Coyote3 Architecture Overview

This document describes the current runtime architecture, ownership boundaries, and the working model that keeps the repository maintainable.

## System Summary

Coyote3 is organized as two applications inside one repository:

1. `api/`: a FastAPI backend that owns business rules, security, audit, and persistence
2. `coyote/`: a Flask UI that renders pages and consumes the backend over HTTP

The API is the primary backend contract. The UI is a client of that contract.

## What Is Working Today

The following architectural assumptions are implemented and validated:

- `uvicorn api.main:app` is the canonical API startup path
- route registration is centralized under `api/routers/`
- API contracts are defined under `api/contracts/`
- Mongo runtime ownership is under `api/db/mongo/`
- direct UI-to-Mongo access is blocked by repository boundaries and tests
- UI calls the API through `coyote/services/api_client/`
- development and portable Docker stacks both start successfully
- the repository test suite passes

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

## UI Request Flow

The UI remains presentation-focused.

```text
Flask blueprint -> UI api_client helper -> HTTP call to API -> API response -> template render
```

Layer roles:

- `coyote/blueprints/`: page flow, form handling, redirects, view orchestration
- `coyote/services/api_client/`: endpoint building, HTTP transport, header forwarding
- `coyote/templates/`: rendering
- `coyote/static/`: static UI assets

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

The current structure is intentionally explicit:

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

This structure keeps maintenance practical because:

- route files stay thin and predictable
- transport contracts are explicit and reviewable
- persistence logic is localized
- UI cannot quietly bypass policy enforcement
- tests mirror the repository boundaries
- deployment and runtime entrypoints are unambiguous

## How To Maintain It

When changing code, keep these maintenance rules:

1. Change the smallest layer that actually owns the behavior.
2. Do not solve a backend problem in Flask.
3. Do not solve a persistence problem in a router.
4. Add tests in the same scope as the behavior you changed.
5. Update documentation when you change architecture, startup, boundaries, or extension patterns.

## How To Add New Capability

### Add a new backend resource

1. Define or extend contracts in `api/contracts/`.
2. Add or extend the router in `api/routers/`.
3. Implement workflow logic in `api/core/` or `api/services/`.
4. Add repository methods in `api/repositories/`.
5. Add Mongo handler support in `api/infra/db/`.
6. Add tests in `tests/api/`, `tests/unit/`, and `tests/integration/`.

### Add a new UI feature

1. Add or extend a blueprint under `coyote/blueprints/`.
2. Add or extend an API client helper under `coyote/services/api_client/`.
3. Render through templates.
4. Add UI tests in `tests/ui/`.
5. If the feature depends on a new backend route, add the backend slice first.

## Working Definition Of Done

A feature or architectural change is complete when:

- runtime entrypoints still work
- boundary rules are preserved
- relevant docs are updated
- the full suite passes
- Docker startup still works if deployment behavior changed
