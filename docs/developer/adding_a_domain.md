# Add a New Domain or Collection

Use this guide when adding a new analysis area such as methylation, MSI, or a
new reference-data collection.

## Current backend pattern

The backend now uses this structure:

- `api/infra/mongo/handlers/*`: collection-scoped persistence
- `api/services/*`: orchestration and use-case logic
- `api/deps/services.py`: service factory layer
- `api/routers/*`: HTTP boundary

## Option A: add a new analysis domain

Example: DNA methylation.

### Files to add

```text
api/contracts/schemas/dna.py              # extend or add schema
api/infra/mongo/handlers/methylation.py   # collection handler
api/services/dna/methylation.py           # application service
api/routers/methylation.py                # HTTP routes
tests/unit/test_methylation_service.py
tests/api/routers/test_methylation_routes.py
```

### 1. Add the collection contract

Register the collection in `api/contracts/schemas/registry.py`.

```python
COLLECTION_MODEL_ADAPTERS["methylation"] = TypeAdapter(MethylationDoc)
```

### 2. Add the handler

```python
# api/infra/mongo/handlers/methylation.py
from api.infra.mongo.handlers.base import BaseHandler


class MethylationHandler(BaseHandler):
    def get_sample_methylation(self, *, sample_id: str) -> list[dict]:
        return list(self.handler_collection.find({"SAMPLE_ID": sample_id}))
```

### 3. Register the handler at runtime

Add it to `api/infra/mongo/runtime_adapter.py`.

```python
self.methylation_handler = MethylationHandler(self)
```

### 4. Add the service

```python
from __future__ import annotations

from typing import Any


class MethylationService:
    def __init__(self, *, methylation_handler: Any) -> None:
        self.methylation_handler = methylation_handler

    @classmethod
    def from_store(cls, store: Any) -> "MethylationService":
        return cls(methylation_handler=store.methylation_handler)
```

If the domain becomes large, keep `api/services/dna/methylation.py` as the public entrypoint
and split support logic into nearby modules such as `methylation_reads.py`,
`methylation_writes.py`, or `methylation_exports.py`.

### 5. Add the factory

```python
def get_methylation_service() -> MethylationService:
    return MethylationService.from_store(get_store())
```

### 6. Add the router

```python
@router.get("/api/v1/methylation/{sample_id}")
def list_methylation(
    sample_id: str,
    service: MethylationService = Depends(get_methylation_service),
):
    sample = get_sample_service().get_user_by_id(sample_id)
    return service.list_payload(sample=sample)
```

## Option B: add a new collection only

If the collection is reference data or a support collection:

1. add the schema to `api/contracts/schemas/*`
2. register it in `api/contracts/schemas/registry.py`
3. add a collection handler
4. register it in `api/infra/mongo/runtime_adapter.py`
5. add service methods only if a route or workflow needs them

## How things are wired now

### Runtime boot

- `api/main.py` starts the app
- `api/lifecycle.py` runs startup
- `api/runtime_setup.py` configures runtime pieces
- `api/extensions.py` exposes the shared `store`
- `api/infra/mongo/runtime_adapter.py` attaches handlers to `store`

### Request path

```python
router -> Depends(get_service) -> Service.from_store(get_store()) -> handler methods
```

### Example

```python
# api/deps/services.py
def get_sample_catalog_service() -> SampleCatalogService:
    return SampleCatalogService.from_store(get_store())
```

```python
# api/services/sample/catalog.py
class SampleCatalogService:
    @classmethod
    def from_store(cls, store):
        return cls(
            sample_handler=store.sample_handler,
            gene_list_handler=store.gene_list_handler,
            assay_panel_handler=store.assay_panel_handler,
            variant_handler=store.variant_handler,
            grouped_coverage_handler=store.grouped_coverage_handler,
        )
```

## Design rules

- One handler owns one collection
- Services may combine many handlers
- Routers should depend on services, not `store`
- `api/core` should stay pure and reusable
- Do not reintroduce repository facades or compatibility layers
- Do not pass raw Mongo collections through the app layer unless you are at the infra/composition boundary

## Quality checks

```bash
.venv/bin/ruff check api tests
.venv/bin/python -m pytest -q
.venv/bin/python -m mkdocs build --strict
```
