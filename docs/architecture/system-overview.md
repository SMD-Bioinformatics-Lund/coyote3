# System Overview

## High-level architecture

```text
Flask UI (coyote) -> FastAPI backend (api) -> MongoDB
                               -> Redis
```

## Layering conventions

### API side

- `api/routers`: HTTP boundary and request/response shape
- `api/services`: orchestration and use-case logic
- `api/core`: reusable domain/core logic
- `api/contracts`: Pydantic contracts for API and DB documents
- `api/infra/db`: collection handlers and DB utilities
- `api/deps`: dependency wiring

### UI side

- `coyote/blueprints/*`: route groups and view logic
- `coyote/templates/*`: rendered pages
- `coyote/static/*`: CSS/JS assets

## Startup lifecycle

- `api/main.py`
- `api/lifecycle.py`
- `api/runtime_bootstrap.py`

Startup builds runtime context, initializes store/handlers, and ensures required indexes.

## Why split UI and API

- Keeps policy + business rules centralized in API
- Makes testing and migration to API-first workflows easier
- Reduces accidental duplication of domain logic in templates/views
