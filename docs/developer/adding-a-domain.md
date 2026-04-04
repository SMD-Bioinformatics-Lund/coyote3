# Add a New Analysis Domain

This guide walks through adding a new analysis domain to Coyote3, using
**DNA methylation** as a concrete example. The same pattern applies to any
new domain — structural variants, microsatellite instability, etc.

## DNA-based or RNA-based?

Coyote3 organises analysis by analyte type:

| Analyte | Service package | Handler base | Examples |
|---------|----------------|--------------|----------|
| **DNA** | `api/services/dna/` | `api/infra/db/` | SNVs, CNVs, translocations, methylation |
| **RNA** | `api/services/rna/` | `api/infra/db/` | Gene expression, fusions |

**Decision rule**: if the data originates from DNA sequencing (whole-genome,
targeted panels, bisulfite-seq, EPIC arrays), it belongs under DNA. If it
comes from RNA-seq or expression profiling, it belongs under RNA.

Methylation is DNA-based — CpG sites, promoter methylation status, and
methylation-class predictions all derive from DNA.

## File checklist

Creating a new domain touches 6-8 files:

```text
api/infra/db/methylation.py          # 1. DB handler
api/services/dna/methylation.py      # 2. Service
api/contracts/dna.py                 # 3. Contract (extend)
api/routers/methylation.py           # 4. Router
api/deps/services.py                 # 5. DI factory
api/routers/registry.py              # 6. Router registration
tests/unit/test_methylation.py       # 7. Unit test
tests/api/routers/test_methylation_routes.py  # 8. Router test
```

## Step-by-step

### 1. DB handler

Create a handler that extends `BaseHandler` and sets its collection:

```python
# api/infra/db/methylation.py
"""MongoDB handler for methylation data."""

from api.infra.db.base import BaseHandler


class MethylationHandler(BaseHandler):
    """Handle methylation collection operations."""

    def get_sample_methylation(self, *, sample_id: str) -> list[dict]:
        return list(
            self.handler_collection.find({"sample_id": sample_id})
        )

    def get_methylation_by_id(self, methylation_id: str) -> dict | None:
        from bson import ObjectId
        return self.handler_collection.find_one({"_id": ObjectId(methylation_id)})
```

Register the handler in `api/infra/db/mongo.py` inside `_setup_handlers()`:

```python
from api.infra.db.methylation import MethylationHandler

self.methylation_handler = MethylationHandler(self)
self.methylation_handler.set_collection(self.coyote_db.methylation)
```

### 2. Service

Add a service file in the appropriate analyte package:

```python
# api/services/dna/methylation.py
"""Methylation analysis service."""

from __future__ import annotations

from typing import Any

from api.extensions import store
from api.http import api_error


class MethylationService:
    """Sample-scoped methylation workflows."""

    def __init__(self, repository: Any | None = None) -> None:
        self.repository = repository or store.get_dna_route_repository()

    def list_payload(self, *, sample: dict) -> dict:
        if not sample:
            raise api_error(404, "Sample not found")
        results = list(
            self.repository.methylation_handler.get_sample_methylation(
                sample_id=str(sample["_id"])
            )
        )
        return {
            "sample": sample,
            "meta": {"count": len(results)},
            "methylation": results,
        }
```

### 3. Contract

Extend the existing DNA contracts:

```python
# in api/contracts/dna.py

class MethylationListPayload(BaseModel):
    """Response for methylation list endpoint."""
    sample: dict
    meta: dict
    methylation: list[dict]
```

### 4. Router

```python
# api/routers/methylation.py
"""Methylation analysis routes."""

from fastapi import APIRouter, Depends

from api.contracts.dna import MethylationListPayload
from api.deps.services import get_methylation_service
from api.security.access import require_access

router = APIRouter(prefix="/api/v1/methylation", tags=["methylation"])


@router.get("/{sample_id}", response_model=MethylationListPayload)
def list_methylation(
    sample_id: str,
    user=Depends(require_access()),
    service=Depends(get_methylation_service),
):
    sample = service.repository.sample_handler.get_sample(sample_id)
    return service.list_payload(sample=sample)
```

### 5. DI wiring

Add the factory to `api/deps/services.py`:

```python
from api.services.dna.methylation import MethylationService

def get_methylation_service() -> MethylationService:
    """Return the methylation service."""
    return MethylationService()
```

### 6. Router registration

Add to `api/routers/registry.py`:

```python
from api.routers import methylation

app.include_router(methylation.router)
```

### 7. Tests

**Unit test** — test service logic with a stub repository:

```python
# tests/unit/test_methylation.py
import pytest
from api.services.dna.methylation import MethylationService


class _MethylationHandlerStub:
    def get_sample_methylation(self, *, sample_id):
        return [{"_id": "m1", "sample_id": sample_id, "gene": "MGMT", "status": "methylated"}]


class _RepoStub:
    methylation_handler = _MethylationHandlerStub()


@pytest.mark.unit
def test_list_payload_returns_methylation_data():
    service = MethylationService(repository=_RepoStub())
    payload = service.list_payload(sample={"_id": "s1", "name": "sample1"})
    assert payload["meta"]["count"] == 1
    assert payload["methylation"][0]["gene"] == "MGMT"
```

**Router test** — test the HTTP endpoint with monkeypatching:

```python
# tests/api/routers/test_methylation_routes.py
import pytest
from api.services.dna import methylation as methylation_module
from api.services.dna.methylation import MethylationService


@pytest.mark.api
def test_list_methylation(client, monkeypatch, authenticated_user):
    # Stub the service to return known data
    monkeypatch.setattr(
        methylation_module, "store",
        # ... stub store as needed
    )
    response = client.get("/api/v1/methylation/sample123")
    assert response.status_code == 200
```

## Existing domain examples

Use these as reference implementations:

| Domain | Handler | Service | Router |
|--------|---------|---------|--------|
| **Biomarkers** | `api/infra/db/biomarkers.py` | `api/services/biomarker/biomarker_lookup.py` | `api/routers/biomarkers.py` |
| **CNVs** | `api/infra/db/cnvs.py` | `api/services/dna/cnv.py` | `api/routers/cnvs.py` |
| **Fusions** (RNA) | `api/infra/db/fusions.py` | `api/services/rna/fusions.py` | `api/routers/fusions.py` |

## Quality gates

After adding a new domain, verify:

```bash
PYTHONPATH=. ruff check api/
PYTHONPATH=. pytest -q -m unit tests/unit/test_methylation.py
PYTHONPATH=. pytest -q
mkdocs build --strict
```
