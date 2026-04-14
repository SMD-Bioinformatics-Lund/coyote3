# Add a New Feature

This guide describes the current backend/UI feature path after the handler and
service cleanup.

## The standard path

1. Add or update request/response contracts.
2. Add or update collection-scoped handler methods if persistence changes.
3. Add or update a service in `api/services/*`.
4. Expose the service from `api/deps/services.py`.
5. Inject the service into a router.
6. Update the UI if the feature is user-facing.
7. Add tests and docs.

## Package rules

- `api/infra/mongo/handlers/*`: one collection per handler
- `api/services/*`: use-case and orchestration logic
- if a service grows large, split it into package-local helper modules and keep one public entrypoint module
- `api/core/*`: pure helpers only
- `api/deps/services.py`: service factory layer
- `api/routers/*`: HTTP boundary only
- `coyote/*`: UI runtime that talks to the API

Examples of the current pattern:

- `api/services/ingest/service.py` is the public ingest service, with helper modules such as `collection_writes.py`, `dependent_writes.py`, and `sample_updates.py`
- `api/services/dna/variant_analysis.py` is the public DNA small-variant service, with helper modules such as `variant_exports.py`, `variant_state.py`, `variant_classification.py`, and `variant_comments.py`

## Example: add a backend read feature

### 1. Add a handler method

```python
# api/infra/mongo/handlers/methylation.py
class MethylationHandler(BaseHandler):
    def get_sample_methylation(self, *, sample_id: str) -> list[dict]:
        return list(self.handler_collection.find({"SAMPLE_ID": sample_id}))
```

### 2. Add a service

```python
# api/services/dna/methylation.py
from __future__ import annotations

from typing import Any

from api.http import api_error


class MethylationService:
    def __init__(self, *, methylation_handler: Any) -> None:
        self.methylation_handler = methylation_handler

    @classmethod
    def from_store(cls, store: Any) -> "MethylationService":
        return cls(methylation_handler=store.methylation_handler)

    def list_payload(self, *, sample: dict) -> dict:
        if not sample:
            raise api_error(404, "Sample not found")
        rows = list(
            self.methylation_handler.get_sample_methylation(sample_id=str(sample["_id"]))
        )
        return {"sample": sample, "meta": {"count": len(rows)}, "methylation": rows}
```

If the service gets large, split it like this instead:

```text
api/services/dna/methylation.py          # public entrypoint
api/services/dna/methylation_reads.py    # read/query helpers
api/services/dna/methylation_writes.py   # write helpers
api/services/dna/methylation_exports.py  # export helpers
```

Keep the router and tests importing `api/services/dna/methylation.py`, not the helper modules directly.

### 3. Add the factory

```python
# api/deps/services.py
def get_methylation_service() -> MethylationService:
    return MethylationService.from_store(get_store())
```

### 4. Inject it in the router

```python
# api/routers/methylation.py
@router.get("/api/v1/methylation/{sample_id}")
def list_methylation(
    sample_id: str,
    user: ApiUser = Depends(require_access()),
    service: MethylationService = Depends(get_methylation_service),
):
    sample = get_sample_service().get_sample_by_id(sample_id)
    return service.list_payload(sample=sample)
```

## Example: add a write feature

When a feature changes persisted state:

- perform validation in the service
- keep Mongo-specific write details inside the handler
- invalidate cache in the service or workflow if needed
- return a shared change payload when the endpoint is reporting a simple write outcome

```python
from api.services.accounts.common import change_payload


class PermissionManagementService:
    def archive(self, *, permission_id: str, actor_username: str) -> dict:
        policy = self.permissions_handler.get_permission(permission_id)
        if not policy:
            raise api_error(404, "Permission policy not found")
        self.permissions_handler.archive_permission(permission_id, actor_username)
        return change_payload(
            resource="permission",
            resource_id=permission_id,
            action="archive",
        )
```

## Example: UI wiring

The Flask UI should call the API, not backend handlers directly.

```python
payload = get_web_api_client().get_json(
    api_endpoints.dashboard("summary"),
    headers=forward_headers(),
)
return render_template("dashboard.html", **payload)
```

### Error handling with `api_page_guard`

Use the `api_page_guard` context manager for any UI view that loads data from the
API. It catches `ApiRequestError` and `AttributeError`, logs the failure, and
raises a user-friendly error page automatically.

```python
from coyote.services.api_client.web import api_page_guard

@admin_bp.route("/things")
@login_required
def list_things() -> str:
    with api_page_guard(
        logger=app.logger,
        log_message="Failed to fetch things",
        summary="Unable to load things.",
        not_found_summary="Thing not found.",  # optional, for 404s
    ):
        payload = get_web_api_client().get_json(
            api_endpoints.admin("things"),
            headers=forward_headers(),
        )
    return render_template("things/list.html", things=payload.things)
```

Do **not** write manual `try/except ApiRequestError` blocks that call
`raise_page_load_error` — `api_page_guard` replaces that pattern.

## When to add a new handler

Add a handler method when:

- the feature needs a new collection query
- the behavior is collection-local
- the logic is Mongo-specific

Do not add a handler method when:

- the work combines multiple collections
- the work is mostly domain/business logic
- the work belongs to reporting, interpretation, or orchestration

Those belong in a service.

## Quality checks

```bash
.venv/bin/ruff check api coyote tests scripts
.venv/bin/python -m pytest -q
.venv/bin/python -m mkdocs build --strict
```
