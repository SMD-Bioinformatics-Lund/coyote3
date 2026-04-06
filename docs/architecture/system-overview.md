# System Overview

## High-level architecture

```text
Flask UI (coyote) -> FastAPI backend (api) -> MongoDB
                               -> Redis
```

## Layering conventions

### API side

- `api/routers`: HTTP boundary and request/response shape
- `api/deps/handlers.py`: low-level dependency access to the shared `store`
- `api/deps/services.py`: service composition root
- `api/services`: orchestration and use-case logic
- `api/core`: pure reusable domain/core logic
- `api/contracts`: Pydantic contracts for API and DB documents
- `api/infra/mongo`: Mongo adapter, runtime helpers, and collection-handler package
- `api/infra/mongo/handlers`: collection-scoped Mongo handlers
- `api/infra/knowledgebase`: annotation knowledgebase handlers and plugin registry backed by MongoDB collections
- `api/infra/integrations`: true external integrations such as LDAP
- `api/deps`: dependency wiring

### UI side

- `coyote/blueprints/*`: route groups and view logic
- `coyote/templates/*`: rendered pages
- `coyote/static/*`: CSS/JS assets

## Startup lifecycle

- `api/main.py`
- `api/lifecycle.py`
- `api/runtime_setup.py`

Startup builds runtime context, initializes the shared `store`, attaches
collection-scoped handlers, and ensures required indexes.

## Wiring model

The backend now follows one consistent wiring style:

1. `api/extensions.py` owns the shared runtime `store`
2. `api/deps/handlers.py` exposes the small set of low-level dependency getters
3. `api/deps/services.py` builds service instances
4. services declare explicit constructor dependencies
5. routers depend on services, not on `store`

### Example

```python
# api/deps/services.py
@lru_cache
def get_dashboard_service() -> DashboardService:
    return DashboardService.from_store(get_store())
```

```python
# api/services/dashboard/analytics.py
class DashboardService:
    @classmethod
    def from_store(cls, store):
        return cls(
            user_handler=store.user_handler,
            roles_handler=store.roles_handler,
            assay_panel_handler=store.assay_panel_handler,
            assay_configuration_handler=store.assay_configuration_handler,
            gene_list_handler=store.gene_list_handler,
            sample_handler=store.sample_handler,
            variant_handler=store.variant_handler,
            copy_number_variant_handler=store.copy_number_variant_handler,
            translocation_handler=store.translocation_handler,
            fusion_handler=store.fusion_handler,
            blacklist_handler=store.blacklist_handler,
            reported_variant_handler=store.reported_variant_handler,
            coyote_db=store.coyote_db,
        )
```

```python
# api/routers/dashboard.py
@router.get("/api/v1/dashboard/summary")
def summary(service: DashboardService = Depends(get_dashboard_service)):
    return service.get_dashboard(...)
```

## Persistence rule

- One collection-scoped handler owns one Mongo collection.
- Handlers should not orchestrate across multiple collections.
- Multi-collection behavior belongs in `api/services/*`.
- `api/core/*` should stay pure and reusable; it should not import `store`.

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
