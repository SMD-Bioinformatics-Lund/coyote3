# Add a New Domain or Collection

Use this guide when adding a new analysis area such as methylation, MSI, or a
new reference-data collection.

## Current backend pattern

The backend now uses this structure:

- `api/infra/mongo/repositories/*`: collection-scoped persistence
- `api/application/*`: orchestration and use-case logic
- `api/app/deps/services.py`: service factory layer
- `api/interfaces/http/*`: HTTP boundary

## Option A: add a new analysis domain

Example: DNA methylation.

### Files to add

```text
api/contracts/schemas/dna.py              # extend or add schema
api/infra/mongo/repositories/methylation.py   # collection repository
api/application/dna/methylation.py           # application service
api/interfaces/http/methylation.py                # HTTP routes
tests/unit/test_methylation_service.py
tests/api/interfaces/http/test_methylation_routes.py
```

### 1. Add the collection contract

Register the collection in `api/contracts/schemas/registry.py`.

```python
COLLECTION_MODEL_ADAPTERS["methylation"] = TypeAdapter(MethylationDoc)
```

### 2. Add the repository

```python
# api/infra/mongo/repositories/methylation.py
from api.infra.mongo.repositories.base import BaseRepository


class MethylationRepository(BaseRepository):
    def get_sample_methylation(self, *, sample_id: str) -> list[dict]:
        return list(self.get_collection().find({"SAMPLE_ID": sample_id}))
```

### 3. Register the repository at runtime

Add it to `api/infra/mongo/runtime_adapter.py`.

```python
self.methylation_repository = MethylationRepository(self)
```

### 4. Add the service

```python
from __future__ import annotations

from typing import Any


class MethylationService:
    def __init__(self, *, methylation_repository: Any) -> None:
        self.methylation_repository = methylation_repository

    @classmethod
    def from_store(cls, store: Any) -> "MethylationService":
        return cls(methylation_repository=store.methylation_repository)
```

If the domain becomes large, keep `api/application/dna/methylation.py` as the public entrypoint
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
3. add a collection repository
4. register it in `api/infra/mongo/runtime_adapter.py`
5. add service methods only if a route or workflow needs them

## How things are wired now

### Runtime boot

- `api/app/main.py` starts the app
- `api/lifecycle.py` runs startup
- `api/app/runtime_setup.py` configures runtime pieces
- `api/app/container.py` exposes the shared `store`
- `api/infra/mongo/runtime_adapter.py` attaches repositories to `store`

### Request path

```python
router -> Depends(get_service) -> Service.from_store(get_store()) -> handler methods
```

### Example

```python
# api/app/deps/services.py
def get_sample_catalog_service() -> SampleCatalogService:
    return SampleCatalogService.from_store(get_store())
```

```python
# api/application/sample/catalog.py
class SampleCatalogService:
    @classmethod
    def from_store(cls, store):
        return cls(
            sample_repository=store.sample_repository,
            gene_list_repository=store.gene_list_repository,
            assay_panel_repository=store.assay_panel_repository,
            variant_repository=store.variant_repository,
            grouped_coverage_repository=store.grouped_coverage_repository,
        )
```

## Design rules

- One handler owns one collection
- Services may combine many handlers
- Routers should depend on services, not `store`
- `api/domain/core` should stay pure and reusable
- Do not reintroduce repository facades or hidden bridging layers
- Do not pass raw Mongo collections through the app layer unless you are at the infra/composition boundary

## Quality checks

```bash
.venv/bin/ruff check api tests
.venv/bin/python -m pytest -q
.venv/bin/python -m mkdocs build --strict
```
