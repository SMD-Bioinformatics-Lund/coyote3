# Flask -> API Client Layout

This package is the web-layer adapter for calling FastAPI endpoints from Flask blueprints.

## Structure

- `api_client.py`: public facade (`CoyoteApiClient`) + stable helpers (`get_web_api_client`, header builders)
- `base.py`: shared HTTP transport and payload primitives (`BaseApiClient`, `ApiPayload`, `ApiRequestError`)
- `clients/`: legacy placeholders kept for backward compatibility during migration.

## Adding a new API endpoint

1. Call API endpoints directly from blueprints using `get_json` / `post_json`.
2. Keep endpoint paths explicit at call sites for easier traceability.
3. Keep response handling lightweight; transport returns `ApiPayload`.
4. Add endpoint-specific helpers only if reuse is high and maintenance burden decreases.

## Design rules

- RBAC is enforced by API routes, not Flask routes.
- Keep transport behavior centralized in `BaseApiClient`.
- Keep blueprint code focused on UI rendering and request/response flow.
