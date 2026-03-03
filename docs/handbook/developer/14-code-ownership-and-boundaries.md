# Code Ownership and Boundaries

This chapter defines the ownership contract between API and web layers.

## Ownership model

- `api/` owns backend business logic, data handlers, workflow orchestration, and persistence behavior.
- `coyote/` owns UI concerns only: Flask request/response flow, template rendering, and static assets.
- Communication between web and backend must go through `coyote/integrations/api`.

## Hard boundary rules

1. `coyote/*` must not import `api.*` modules directly.
2. Web blueprints should call API endpoints via `get_web_api_client()` and render responses.
3. API routes enforce RBAC and validation; web routes should not duplicate backend authorization logic.
4. Shared transport/payload logic belongs in `coyote/integrations/api`.

## Module naming and organization

- Prefer feature-oriented names over generic names.
  - Good: `views_variant_actions_comments.py`
  - Avoid new broad files like `helpers.py` unless scope is truly cross-feature.
- Keep route modules thin and delegate work to `api/services/*`.
- Keep domain models under `api/domain/models/*` and domain constants under `api/domain/core/*`.

## What "thin route" means

A route module should do only the following:

- Parse request params/body
- Load identity/access context
- Call a service function
- Map service result to response payload

Business rules, query construction, and persistence orchestration should live in service/domain layers.

## Guardrails implemented

- `tests/web/test_web_api_boundary.py` enforces no direct `coyote -> api` imports.
- `tests/api/test_route_module_organization.py` enforces route-module docstrings and versioned API prefixes.
- `tests/test_api_route_security.py` enforces route access guards.
