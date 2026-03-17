# Route Implementation Guide

## Why this guide exists
This guide is the operational standard for adding, changing, and validating routes in Coyote3.
Its goal is to keep changes simple to reason about and safe for clinical workflows.

## Architecture intent (why we use ports)
Ports are interface contracts between business logic and persistence adapters.
They exist to solve three concrete problems:

1. Prevent route/business code from depending on Mongo-specific APIs.
2. Keep behavior stable when storage implementation changes.
3. Make tests faster and clearer by mocking interface contracts instead of database internals.

In practice:
1. `api/core/*` depends on ports in `api/core/*/ports.py`.
2. `api/infra/repositories/*_mongo.py` implements those ports.
3. `api/services/*` owns route-facing workflow composition where a bounded context needs orchestration.
4. `api/routers/*` coordinates request/response and permissions only.

If we later add a non-Mongo provider, we implement new adapters behind existing ports and avoid rewriting route/core logic.

## Golden boundary rules
1. UI (`coyote/*`) never imports Mongo handlers or `store.*`.
2. API routes do not embed query orchestration logic.
3. Business rules live in core/service code, not Flask blueprints.
4. Persistence details live only in infra repository adapters.
5. API response shapes are defined by `api/contracts/*` and must stay explicit.

## End-to-end request flow
1. Browser calls Flask route in `coyote/blueprints/*`.
2. Flask route builds API URL via `coyote/services/api_client/endpoints.py`.
3. Flask route calls API (`get_web_api_client().get_json/post_json/...`).
4. FastAPI route in `api/routers/*` validates input and checks access.
5. FastAPI route calls core/service/repository facade.
6. Repository adapter calls Mongo handlers in `api/infra/db/*`.
7. Response is serialized and returned to UI template.

For concrete route-level examples (page render, mutation, CSV export, report preview/save, report file download), see:
- `docs/development/ui-api-request-flow.md`

## Route categories
1. UI routes: Flask endpoints that render templates or redirect.
2. API routes: FastAPI endpoints under `/api/v1/*` that enforce contracts.
3. Helper/internal API routes: API-only support for UI context operations.

## Standard process for adding a new API route
1. Add request/response contract model in `api/contracts/<domain>.py`.
2. Add route in `api/routers/<domain>.py` with explicit `response_model`.
3. Add access checks (`require_access(...)`) and keep them near route declaration.
4. Add or extend a dependency factory in `api/deps/` if the route needs a service seam.
5. Delegate behavior to a service first; let the service call repositories.
6. Serialize output using shared serialization helpers.
7. Add tests for happy path, permission failure, and not-found/validation paths.

Preferred implementation shape:

```python
@router.get("/api/v1/example/{item_id}", response_model=ExamplePayload)
def read_example(
    item_id: str,
    user: ApiUser = Depends(require_access(permission="view_example")),
    service: ExampleService = Depends(get_example_service),
):
    item = service.read_item(item_id=item_id, user=user)
    return util.common.convert_to_serializable(item)
```

## Standard process for adding a new UI route
1. Add or extend Flask view code in a feature-sized module under `coyote/blueprints/<domain>/`.
   Prefer cohesive files like `views_dna_findings.py`, `views_small_variant_actions.py`, `views_users.py`, or `views_genes.py`.
2. Build API path only via `api_endpoints.*` helpers.
3. Call API through `get_web_api_client()` helpers.
4. Render/update template under the same blueprint domain.
5. Wire links/forms with `url_for(...)`, never hardcoded Flask URLs.
6. Add UI route audit and contract coverage tests.

Page-failure rule:

- if the route cannot render the page because required API context failed to load, raise a typed web error and let the global Flask error handler render the standard error page
- if the route is handling a mutation inside an already-valid page, keep the user in context and use a clear flash message

Flash-message rule:

- use `flash_api_success(...)` for success messages
- use `flash_api_failure(...)` for upstream mutation failures
- do not interpolate raw exception text directly into the UI unless the operator genuinely needs it
- keep messages action-oriented and specific to the resource being changed

Audit rule:

- request handlers that perform meaningful reads or mutations must leave an auditable trail
- API request, access, mutation, validation, and exception audit events are emitted centrally
- UI request and error audit events are emitted centrally
- route handlers should add `g.audit_metadata` when a mutation needs resource-specific context attached to the audit record

## Endpoint builder rules
1. Never hardcode `/api/v1/...` paths in blueprints.
2. Always use `api_endpoints.*`.
3. If builder support is missing, add a new helper in `endpoints.py`.
4. Keep builder naming aligned with API route family naming.
5. Every new builder usage must resolve to a real FastAPI route template.

## Admin schema payload rule
Admin context payloads in Flask code must use `schema` key semantics.
Do not consume `schema_payload` in UI blueprint logic.

## Runtime initialization rule
`api.main` is the canonical backend entrypoint and runtime dependencies are initialized through backend startup and request guards rather than at arbitrary import sites.
Reason: test modules and tooling should be able to import backend modules without forcing immediate database bootstrap.

## What to edit when adding/changing a route
1. API contracts: `api/contracts/*.py`
2. API router: `api/routers/*.py`
3. API dependencies: `api/deps/*.py`
4. Core/service or repository facade: `api/core/*`, `api/services/*`, `api/repositories/*`
5. UI endpoint builder: `coyote/services/api_client/endpoints.py`
6. UI view/template: feature-sized `coyote/blueprints/*/views*.py` modules, matching templates
7. Tests across layers: `tests/api`, `tests/ui`, `tests/integration`, `tests/unit`

## Docstring standard

Every public route handler, service entrypoint, repository class, and error helper should have a concise docstring that answers one question:
what responsibility does this function or class own?

Good docstrings in this repository:

- describe intent and responsibility
- mention whether the function loads a page, performs a mutation, or translates data
- stay brief and factual

Bad docstrings:

- restate the function name
- describe Python syntax instead of behavior
- document internal trivia instead of responsibility

## Required tests by layer
1. API route tests:
   - File: `tests/api/routers/test_<domain>_routes.py`
   - Validate status, payload shape, authz/authn behavior, error handling.
2. Core/unit tests:
   - File: `tests/unit/...`
   - Validate behavior independent of transport and DB.
3. UI route audit:
   - File: `tests/ui/test_ui_route_audit.py`
   - Validate Flask route/link integrity and smoke rendering.
4. Web/API contract wiring:
   - File: `tests/integration/test_web_api_route_contract.py`
   - Validate that every `api_endpoints.*` path maps to an actual API route template.
5. Boundary guardrails:
   - Files: `tests/ui/test_web_api_boundary.py`, `tests/integration/test_backend_db_boundary_guardrails.py`
   - Validate no route/core leakage of direct persistence coupling.

## Minimal acceptance checklist for any new route
1. Contract model added/updated and referenced by route.
2. Route permissions declared and validated in tests.
3. Route delegates to a service or tightly scoped repository facade with no in-route query logic.
4. UI uses endpoint builder helper (no hardcoded API path).
5. UI action/form has route test coverage.
6. Contract wiring test passes for new endpoint path.
7. Boundary tests still show zero forbidden usage regressions.

## Migration standard for legacy routes

When refactoring an older route family:

1. Preserve the route path and contract first.
2. Introduce a service and dependency factory.
3. Move orchestration out of the router without changing response shape.
4. Update tests to override the new dependency instead of patching private router globals.
5. Remove the old singleton/helper seam only after tests prove the new dependency path.

## UI button/form wiring checklist
1. Template target uses `url_for(...)`.
2. Flask handler receives and validates user input.
3. Flask handler calls correct API endpoint builder.
4. API route method/path exists and matches intent.
5. Response/redirect flow handles both success and API failure.
   For GET page loads, use the standard error-page path.
   For in-page mutations, use clear flash messaging and preserve navigation context.
6. Tests cover one success and one failure branch.

## Common failure patterns and fixes
1. Failure: Flask calls hardcoded `/api/v1/...`.
   Fix: move to `api_endpoints.*` helper and cover with contract test.
2. Failure: API route directly orchestrates DB query details.
   Fix: move logic to core/service and keep route as transport layer.
3. Failure: UI imports infra/store internals.
   Fix: route all calls through API client.
4. Failure: schema key mismatch (`schema_payload` vs `schema`).
   Fix: standardize consumer to `schema`.
5. Failure: new route has no permissions check.
   Fix: add `require_access` gate and permission tests.

## Suggested implementation sequence for new features
1. Define/update contract.
2. Implement API route.
3. Implement core/service behavior.
4. Implement infra adapter method.
5. Add/extend endpoint builder.
6. Add/extend Flask route/template.
7. Add tests in all required layers.
8. Run non-CI local suite for touched route families.

## Operational note for contributors
If a route change feels like it needs direct access to Mongo handlers from UI or API route bodies, stop and redesign around a port/repository boundary first.
