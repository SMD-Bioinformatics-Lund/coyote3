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

## Runtime concurrency model

### API (FastAPI + Uvicorn)

- API routes include both sync (`def`) and async (`async def`) handlers.
- Sync handlers are executed concurrently by FastAPI/Starlette threadpool workers.
- Process-level parallelism is controlled by `API_WORKERS` in compose:
  - prod/stage default: 4 workers
  - test default: 2 workers
  - dev uses reload mode (single-process developer workflow)

### UI (Flask + Gunicorn)

- UI runs behind Gunicorn and delegates business/data operations to API.
- UI should remain thin; heavy domain behavior belongs to API service/core layers.

## Cache and state model

- Redis is used as shared cache backend (API + UI), not as primary data store.
- Persistent source of truth remains MongoDB.
- Cache backend has explicit strict/degraded modes via `CACHE_REQUIRED`.

## Why split UI and API

- Keeps policy + business rules centralized in API
- Makes testing and migration to API-first workflows easier
- Reduces accidental duplication of domain logic in templates/views
