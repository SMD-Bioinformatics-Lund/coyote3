# Repository Structure

This document defines the repository layout and the ownership model behind it. It is written so that an engineer can answer three questions quickly:

1. What lives here?
2. Why does it live here?
3. Where should the next change go?

## Top-Level Layout

```text
coyote3/
├── api/
├── coyote/
├── config/
├── deploy/
├── docs/
├── scripts/
├── shared/
├── tests/
├── asgi.py
├── run_api.py
├── wsgi.py
├── mkdocs.yml
└── pyproject.toml
```

## Top-Level Responsibilities

### `api/`

Independent FastAPI backend application.

Owns:

- HTTP API routes
- request and response contracts
- authentication and authorization
- business workflows
- audit behavior
- Mongo access and persistence orchestration

Why it exists:

- to provide one authoritative backend contract
- to centralize policy enforcement
- to keep persistence and workflow logic out of the UI

Important subpackages:

- `api/main.py`: canonical FastAPI entrypoint
- `api/config.py`: backend runtime configuration assembly
- `api/lifecycle.py`: startup and shutdown orchestration
- `api/routers/`: active HTTP route registration
- `api/contracts/`: API request and response models
- `api/deps/`: dependency providers for routes
- `api/core/`: domain workflows and application logic
- `api/services/`: service-level orchestration where needed
- `api/repositories/`: repository-facing adapters used by routers and services
- `api/db/mongo/`: Mongo runtime bootstrap, collection access, indexes, settings
- `api/infra/db/`: collection-specific Mongo handlers
- `api/security/`: auth and access control
- `api/audit/`: audit event logic

### `coyote/`

Independent Flask UI application.

Owns:

- browser-facing page routes
- template rendering
- UI-level form handling
- API transport client usage

Why it exists:

- to render browser-facing pages
- to manage user navigation and interaction flow
- to consume the API without duplicating backend logic

Important subpackages:

- `coyote/blueprints/`: page and action routing by UI domain
- `coyote/templates/`: shared templates
- `coyote/static/`: CSS, JavaScript, metadata, assets
- `coyote/services/api_client/`: UI-to-API client wrappers and endpoint helpers
- `coyote/services/auth/`: UI session helpers

### `tests/`

Repository quality gates, organized by scope.

Why this split exists:

- route and API behavior should be tested differently from UI rendering
- cross-layer seams need their own tests
- business workflows need isolated unit tests

- `tests/api/`: backend route and backend-focused behavior tests
- `tests/ui/`: Flask UI and presentation-layer tests
- `tests/integration/`: cross-layer boundary and integration tests
- `tests/unit/`: isolated logic tests
- `tests/fixtures/`: reusable test fixtures, fake stores, baseline data

### `docs/`

Authoritative operational and engineering documentation.

Docs are part of the system, not an afterthought. The intended design, ownership rules, and operating model should be readable here without reverse-engineering code history.

### `deploy/`

Deployment and runtime packaging assets.

- `deploy/compose/`: Compose files for dev, portable, and default runtime modes
- `deploy/gunicorn/`: Gunicorn config and related runtime helpers

### `shared/`

Small neutral shared utilities only. This package should stay lightweight.

Why this restraint matters:

- shared code is easy to abuse
- if `shared/` starts owning domain behavior, the architecture becomes harder to reason about

## Dependency Direction

The intended dependency direction is:

```text
coyote/blueprints -> coyote/services/api_client -> api HTTP endpoints

api/routers -> api/deps -> api/core/api/services -> api/repositories -> api/infra/db + api/db/mongo
```

This dependency direction is intentional. It keeps:

- the UI from becoming a second backend
- routers from becoming persistence layers
- shared code from becoming an unbounded dependency sink

Allowed shared support:

- `shared/*`
- selected `api/contracts/*` usage where a stable contract is needed

Disallowed direction:

- `coyote/*` importing Mongo adapters or backend persistence internals
- `api/routers/*` issuing raw Mongo queries
- `shared/*` becoming a second backend domain layer

## Where To Add New Code

### Add a new API endpoint

- contract: `api/contracts/<domain>.py`
- router: `api/routers/<domain>.py`
- workflow/service: `api/core/<domain>/` or `api/services/`
- repository adapter: `api/repositories/<domain>_repository.py`
- Mongo handler support: `api/infra/db/<domain>.py`
- tests: `tests/api/`, `tests/unit/`, `tests/integration/`

### Add a new UI page

- blueprint route: `coyote/blueprints/<domain>/`
- API client helper: `coyote/services/api_client/`
- template: matching blueprint template folder
- tests: `tests/ui/`

### Add a new cross-cutting runtime concern

- backend startup/config: `api/config.py`, `api/lifecycle.py`
- deployment/runtime variables: `deploy/compose/*`, env files, deployment docs
- repository-wide conventions: `docs/development/*`, `docs/architecture/*`

## What Not To Create

Avoid adding:

- new legacy compatibility folders
- route modules outside `api/routers/`
- UI modules that call Mongo directly
- duplicate API client helpers scattered across blueprints
- large generic utility dumps with no clear ownership
