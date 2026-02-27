# Flask -> API Client Layout

This package is the web-layer adapter for calling FastAPI endpoints from Flask blueprints.

## Structure

- `api_client.py`: public facade (`CoyoteApiClient`) + stable helpers (`get_web_api_client`, header builders)
- `base.py`: shared HTTP transport and payload primitives (`BaseApiClient`, `ApiPayload`, `ApiRequestError`)
- `clients/`: domain mixins (`admin`, `dna`, `rna`, `home`, `public`, etc.)

## Adding a new API endpoint

1. Pick the correct domain mixin in `clients/`.
2. Add a thin method that calls `_get` or `_post`.
3. Keep response handling lightweight; methods return `ApiPayload`.
4. Use `get_json` / `post_json` from the facade for one-off calls if a dedicated method is not needed yet.
5. Prefer generic calls first for low-use or public endpoints; promote to mixin method only when reuse appears.

## Design rules

- RBAC is enforced by API routes, not Flask routes.
- Keep transport behavior centralized in `BaseApiClient`.
- Keep blueprint code focused on UI rendering and request/response flow.
