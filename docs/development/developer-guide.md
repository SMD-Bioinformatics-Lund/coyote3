# Coyote3 Developer Guide

This guide is the practical handbook for engineers changing the repository.

## Repository Layout

```text
coyote3/
├── api/
│   ├── main.py
│   ├── config.py
│   ├── lifecycle.py
│   ├── contracts/
│   ├── routers/
│   ├── deps/
│   ├── services/
│   ├── repositories/
│   ├── core/
│   ├── db/mongo/
│   ├── infra/
│   ├── security/
│   ├── audit/
│   └── settings.py
├── coyote/
│   ├── blueprints/
│   ├── templates/
│   ├── static/
│   ├── services/api_client/
│   └── util/
├── tests/
│   ├── api/
│   ├── ui/
│   ├── integration/
│   ├── unit/
│   └── fixtures/
├── docs/
├── deploy/
├── shared/
└── scripts/
```

## What Each Part Owns

### Backend

- `api/main.py`: FastAPI app entrypoint
- `api/config.py`: runtime config assembly
- `api/lifecycle.py`: startup/shutdown behavior
- `api/contracts/`: request and response models
- `api/routers/`: HTTP endpoints
- `api/deps/`: dependency injection helpers
- `api/core/` and `api/services/`: backend workflows and business logic
- `api/repositories/`: repository-facing adapters and access seams
- `api/db/mongo/`: Mongo runtime bootstrap and shared DB setup
- `api/middleware.py`: request middleware assembly
- `api/openapi.py`: OpenAPI customization
- `api/infra/db/`: collection-specific Mongo handlers
- `api/security/`: auth and authorization
- `api/audit/`: audit emission

### UI

- `coyote/blueprints/`: Flask routes and view orchestration
- `coyote/services/api_client/`: all UI-to-API communication, including session-cookie relay and request-scoped client lifecycle
- `coyote/templates/`: HTML rendering
- `coyote/static/`: client assets

### Tests

- `tests/api/`: backend endpoint and backend behavior tests
- `tests/ui/`: UI route and rendering tests
- `tests/integration/`: boundary and cross-layer tests
- `tests/unit/`: isolated logic tests
- `tests/fixtures/`: reusable fixtures and baseline data

## Local Development

### Run the API

```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload
```

### Run the UI

```bash
python -m wsgi
```

### Run the development Compose stack

```bash
docker compose -f deploy/compose/docker-compose.dev.yml up --build
```

### Run the portable Compose stack

```bash
docker compose -f deploy/compose/docker-compose.dev.portable.yml up --build
```

### Restore a curated dev snapshot into Docker Mongo

The dev Mongo container listens on `mongodb://localhost:37017` and uses the stable
volume name `coyote3-dev-mongo-data`.

Create a snapshot from a source Mongo environment:

```bash
python scripts/create_mongo_micro_snapshot.py \
  --mongo-uri "mongodb://172.17.0.1:27017" \
  --db coyote3 \
  --db BAM_Service \
  --out var/mongo/micro_snapshot
```

Snapshot rules:

- collections come from `config/coyote3_collections.toml`
- `samples` exports the latest 10 samples per assay
- collections with `SAMPLE_ID` export only docs linked to the sampled `samples._id` values
- collections without `SAMPLE_ID` export in full

Restore that snapshot into the dev Docker Mongo and map the prod DB name into the dev DB name:

```bash
python scripts/restore_mongo_micro_snapshot.py \
  --snapshot-dir var/mongo/micro_snapshot \
  --target dev \
  --drop-db \
  --db-map coyote3=coyote_dev_3
```

Restore behavior:

- restores into `mongodb://localhost:37017`
- remaps collection names through `config/coyote3_collections.toml`
- backfills required business-key fields automatically after import
- leaves the dev stack immediately usable for login and linked sample workflows

## Maintenance Rules

These rules keep the codebase maintainable:

1. Keep routers thin.
2. Keep UI blueprints thin.
3. Put backend logic behind API boundaries, not in Flask.
4. Put raw Mongo logic only in repository and Mongo handler layers.
5. Use explicit contracts for API request and response shapes.
6. Prefer explicit service dependencies over router-level singletons.
7. Extend existing domain packages before creating new generic utility modules.
8. Update tests and docs in the same change set as code.
9. Prefer canonical REST endpoints and keep compatibility aliases explicitly deprecated.
10. Treat the API session cookie as authoritative for login flows; do not introduce new UI code that depends on bearer tokens in JSON auth payloads.

## Standard Backend Extension Pattern

For new or refactored API behavior, use this sequence:

1. Router validates input and enforces `require_access(...)`.
2. Router receives a service via `Depends(get_<domain>_service)`.
3. Service owns orchestration, normalization, and workflow branching.
4. Repository owns persistence-facing operations and handler composition.
5. Mongo handlers own raw collection queries.
6. New routes should use resource nouns and HTTP semantics before introducing any alias.

Practical rule: if a router needs to branch on domain state, normalize payloads, or coordinate multiple persistence calls, move that logic into a service.

Practical rule: if a service starts building Mongo query documents directly, move that work into the repository or handler layer.

## How To Change Existing Behavior Safely

### Backend behavior change

1. Identify the owning router and contract.
2. Identify the owning workflow or service.
3. Identify the owning repository or Mongo handler.
4. Change only the layer that owns the behavior.
5. Update tests in `tests/api/`, `tests/unit/`, and `tests/integration/` as needed.
6. Update docs if the route contract, startup model, or extension pattern changed.

### UI behavior change

1. Update the blueprint handler.
2. Use or extend the API client helper.
3. Update the template.
4. Update `tests/ui/`.
5. If the UI needs new data, add the API contract first.

Auth/client rule:

- the API issues the session cookie
- the Flask login flow relays that cookie to the browser
- Flask server-side calls forward `Authorization: Bearer <api_session_token>`
- request-scoped API clients are closed automatically at Flask teardown

## Testing The Modern Router Pattern

When testing a route family:

1. Unit-test the service with a fake repository.
2. Route-test the HTTP layer with FastAPI dependency overrides.
3. Keep direct route-function tests focused on serialization and permission seams.
4. Avoid reintroducing private module singleton patching when a dependency factory exists.

Use route tests for:

- auth and permission checks
- payload shape
- error mapping
- dependency wiring

Use service tests for:

- branching logic
- normalization
- default handling
- multi-repository orchestration

## How To Add A New API Resource

Use this sequence:

1. Add contracts in `api/contracts/<domain>.py`.
2. Add the router in `api/routers/<domain>.py`.
3. Add or extend dependency factories in `api/deps/` when the route needs a service or repository seam.
4. Register the router in the central router registry if needed.
5. Implement workflow logic in `api/core/<domain>/` or `api/services/`.
6. Add repository support in `api/repositories/<domain>_repository.py`.
7. Add or extend Mongo handlers in `api/infra/db/`.
8. Add tests:
   - `tests/api/routers/test_<domain>_routes.py`
   - relevant `tests/unit/`
   - relevant `tests/integration/`
9. Update API docs.

## How To Add A New UI Integration

Use this sequence:

1. Confirm the backend endpoint and contract already exist.
2. Add or extend the API client helper in `coyote/services/api_client/`.
3. Add the Flask route under the correct blueprint package.
4. Render or update templates.
5. Add tests in `tests/ui/`.
6. Update the user or developer docs if the page or workflow changed.

## How To Keep Dependency Direction Clean

Use this rule set:

- UI may call the API, but may not reach into backend persistence internals.
- routers may call services and repositories, but should not build raw Mongo queries.
- repositories may coordinate Mongo handlers, but should not take over route concerns.
- shared helpers should stay small and framework-neutral.

## Maintenance Notes For Mongo Snapshot Workflows

Keep these rules intact when touching the snapshot or restore scripts:

- do not hardcode collection lists in the script when they already exist in `config/coyote3_collections.toml`
- preserve the `samples` special case as latest-per-assay, not latest-global
- preserve `SAMPLE_ID`-based linked extraction for dependent collections
- keep restore-to-dev behavior aligned with `coyote_dev_3`
- if restored document shapes require identity repair, keep that repair in the restore workflow so the restored DB is usable immediately

## How To Review A Change

Before merging, check:

1. Does the code sit in the correct layer?
2. Did the change introduce hardcoded cross-layer dependencies?
3. Are contracts explicit?
4. Are auth and permission checks still local and obvious at the route boundary?
5. Did tests move with the behavior?
6. Did documentation stay current?
