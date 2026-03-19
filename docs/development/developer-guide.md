# Coyote3 Developer Guide

This guide is the practical handbook for engineers changing the repository. It is written for developers who may be new to the codebase and need both the rules and the reasoning behind them.

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
- `api/lifecycle.py`: startup and shutdown behavior
- `api/contracts/`: typed request and response contracts
- `api/routers/`: HTTP endpoints
- `api/deps/`: dependency factories
- `api/core/` and `api/services/`: backend workflows and business logic
- `api/repositories/`: persistence-facing abstractions
- `api/db/mongo/`: Mongo runtime bootstrap and shared DB setup
- `api/openapi.py`: OpenAPI customization
- `api/infra/db/`: collection-specific Mongo handlers
- `api/security/`: authentication and authorization
- `api/audit/`: audit emission

### UI

- `coyote/blueprints/`: Flask routes and page orchestration
- `coyote/services/api_client/`: all UI-to-API communication
- `coyote/templates/`: HTML rendering
- `coyote/static/`: client assets

### Tests

- `tests/api/`: backend route and behavior tests
- `tests/ui/`: UI route and rendering tests
- `tests/integration/`: boundary and cross-layer tests
- `tests/unit/`: isolated logic tests
- `tests/fixtures/`: reusable fixtures and baseline data

## Beginner Layering Glossary

- `contract`: the typed request or response shape at the API boundary
- `router`: the HTTP entrypoint
- `service`: the workflow and orchestration layer
- `repository`: the application-facing persistence seam
- `Mongo handler`: the low-level query implementation

If these terms are new, read [../api/concepts-and-layering.md](../api/concepts-and-layering.md) before changing backend behavior.

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

Override ports/version/build metadata from command line when needed:

```bash
COYOTE3_VERSION=local \
GIT_COMMIT=$(git rev-parse --short HEAD) \
BUILD_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
COYOTE3_DEV_WEB_PORT=7817 \
COYOTE3_DEV_API_PORT=7816 \
docker compose -f deploy/compose/docker-compose.dev.yml up --build
```

### DB identity migration

Use the canonical DB migration script to normalize identity keys and variant identity fields:

```bash
/home/ram/.virtualenvs/coyote3/bin/python scripts/migrate_db_identity.py \
  --mongo-uri mongodb://localhost:37017 \
  --db coyote3_dev
```

Dry-run:

```bash
/home/ram/.virtualenvs/coyote3/bin/python scripts/migrate_db_identity.py \
  --mongo-uri mongodb://localhost:37017 \
  --db coyote3_dev \
  --dry-run
```

Performance implementation details and runtime behavior are defined in:

- [Performance Implementation Guide](performance-implementation.md)

### Historically Slow Routes and Current Fixes

These routes were the primary latency hotspots and are now covered by explicit query/index contracts:

1. `GET /api/v1/samples/{sample_id}/small-variants/{var_id}`
- Root cause: cross-sample lookup used `SAMPLE_ID != current` with identity predicates, which could trigger broad scans.
- Current rule: query by exact identity (`simple_id_hash`, `simple_id`) and exclude current sample after bounded fetch.
- Required indexes: `ix_simple_id_hash_simple_id_lookup`, `simple_id_hash_1_simple_id_1_sample_id_1`.

2. `GET /api/v1/common/reported_variants/variant/{variant_id}/{tier}`
- Root cause: N+1 enrichment reads (sample + annotation fetch per row).
- Current rule: batch sample and annotation fetches with `$in` and map in-memory.
- Required indexes: `ix_gene_simple_id_hash_simple_id`, `ix_time_created_desc`, plus annotation compound indexes.

3. Annotation timeline and classification lookups (`annotation` collection)
- Root cause: filter + sort on `time_created` without aligned compound indexes.
- Current rule: always support sorted lookup with compound indexes for gene/nomenclature/variant.
- Required indexes: `gene_nomenclature_variant_time_created`, `nomenclature_variant_time_created`, `variant_time_created_1`.

4. Structural variant sample filtering (CNV/Translocation/Fusion)
- Root cause: sample filter combined with classification flags (`interesting`, `fp`, `irrelevant`) without compound indexes.
- Current rule: keep sample+flag compound indexes in place for these collections.
- Required indexes:
  - `sample_id_1_interesting_1`
  - `sample_id_1_fp_1`
  - `sample_id_1_irrelevant_1`

### Create sample-focused snapshot

Mixed-assay automatic selection (default 60):

```bash
/home/ram/.virtualenvs/coyote3/bin/python scripts/create_mongo_snapshot.py \
  --mongo-uri mongodb://localhost:37017 \
  --db coyote3_dev \
  --sample-count 60 \
  --output-dir snapshots
```

Explicit sample selectors from file:

```bash
/home/ram/.virtualenvs/coyote3/bin/python scripts/create_mongo_snapshot.py \
  --mongo-uri mongodb://localhost:37017 \
  --db coyote3_dev \
  --sample-list-file /tmp/sample_selectors.txt
```

Explicit sample selectors inline:

```bash
/home/ram/.virtualenvs/coyote3/bin/python scripts/create_mongo_snapshot.py \
  --mongo-uri mongodb://localhost:37017 \
  --db coyote3_dev \
  --sample-name 26MD02863p \
  --sample-id 69b69570ff5cd3d440506337
```

### Snapshot + restore into dev DB

```bash
scripts/snapshot_restore_dev.sh \
  --source-uri mongodb://localhost:5818 \
  --source-db coyote3 \
  --target-uri mongodb://localhost:37017 \
  --target-db coyote3_dev \
  --sample-count 60
```

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
9. Prefer sample-centric resource endpoints for genomics behavior.
10. Treat the API session cookie as authoritative for login flows.

## How To Think About The Layers

Use these questions to decide where code belongs.

### Does this code define what the API accepts or returns?

Put it in `api/contracts/`.

### Does this code decide who is allowed to call an endpoint?

Put it at the router boundary with `require_access(...)`.

### Does this code coordinate a workflow?

Put it in `api/services/`.

### Does this code fetch or persist domain data?

Put it in `api/repositories/`.

### Does this code know raw Mongo collection details?

Put it in `api/infra/db/` or `api/db/mongo/`.

### Does this code render HTML or handle browser flow?

Put it in `coyote/blueprints/` and templates.

## Standard Backend Extension Pattern

For new or refactored API behavior, use this sequence:

1. Router validates input and enforces `require_access(...)`.
2. Router receives a service via `Depends(get_<domain>_service)`.
3. Service owns orchestration, normalization, and workflow branching.
4. Repository owns persistence-facing operations and handler composition.
5. Mongo handlers own raw collection queries.
6. New routes should use resource nouns and HTTP semantics.
7. For genomics workflows, prefer sample-centric resources over assay-bucket routers.

Practical rule: if a router needs to branch on domain state or coordinate multiple persistence calls, move that logic into a service.

Practical rule: if a service starts building Mongo query documents directly, move that work into the repository or handler layer.

Practical rule: if a contract starts looking like a database model or workflow object, it is probably in the wrong layer.

## How To Change Existing Behavior Safely

### Backend behavior change

1. Identify the owning router and contract.
2. Identify the owning workflow or service.
3. Identify the owning repository or Mongo handler.
4. Change only the layer that owns the behavior.
5. Update tests in `tests/api/`, `tests/unit/`, and `tests/integration/`.
6. Update docs if the contract, startup model, or extension pattern changed.

### UI behavior change

1. Update the blueprint handler.
2. Use or extend the API client helper.
3. Update the template.
4. Update `tests/ui/`.
5. If the UI needs new data, add the API capability first.

Auth and client rules:

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
3. Add or extend dependency factories in `api/deps/`.
4. Register the router in the central router registry if needed.
5. Implement workflow logic in `api/core/<domain>/` or `api/services/`.
6. Add repository support in `api/repositories/<domain>_repository.py`.
7. Add or extend Mongo handlers in `api/infra/db/`.
8. Add tests in `tests/api/`, `tests/unit/`, and `tests/integration/`.
9. Update API docs.

When designing a new contract:

- keep request and response contracts separate when their shapes differ
- avoid leaking raw database field names unless they are intentionally part of the public API
- prefer stable client-facing names over persistence-driven names

## How To Add A New UI Integration

Use this sequence:

1. Confirm the backend endpoint and contract already exist.
2. Add or extend the API client helper in `coyote/services/api_client/`.
3. Add the Flask route under the correct blueprint package.
4. Render or update templates.
5. Add tests in `tests/ui/`.
6. Update user or developer docs if the workflow changed.

When the UI needs permission-aware behavior:

- hide or disable actions in templates with `can`, `min_role`, `min_level`, or `has_access`
- still assume the API is the final authority
- test both visible behavior and backend denial behavior

## How To Keep Dependency Direction Clean

Use this rule set:

- UI may call the API, but may not reach into backend persistence internals
- routers may call services and repositories, but should not build raw Mongo queries
- repositories may coordinate Mongo handlers, but should not take over route concerns
- shared helpers should stay small and framework-neutral

## Documentation Standard

Documentation in this repository should be:

- current
- authoritative
- practical
- layered like the code

When updating docs:

- explain what a layer is for, not just where the folder lives
- document the canonical behavior, not migration history
- include examples when a pattern is not obvious
- update docs in the same change set as the code change

## Maintenance Notes For Mongo Snapshot Workflows

Keep these rules intact when touching the snapshot or restore scripts:

- do not hardcode collection lists in the script when they already exist in `config/coyote3_collections.toml`
- preserve the `samples` special case as latest-per-assay, not latest-global
- preserve `SAMPLE_ID`-based linked extraction for dependent collections
- keep restore-to-dev behavior aligned with `coyote3_dev`
- if restored document shapes require identity repair, keep that repair in the restore workflow so the restored DB is usable immediately
- use `scripts/create_mongo_snapshot.py` for curated snapshot exports
- use `scripts/snapshot_restore_dev.sh` for one-command snapshot+restore into dev DB

## How To Review A Change

Before merging, check:

1. Does the code sit in the correct layer?
2. Did the change introduce hardcoded cross-layer dependencies?
3. Are contracts explicit?
4. Are auth and permission checks still local and obvious at the route boundary?
5. Did tests move with the behavior?
6. Did documentation stay current?

## Recommended Reading Order For New Engineers

1. [../ARCHITECTURE_OVERVIEW.md](../ARCHITECTURE_OVERVIEW.md)
2. [../architecture/API_ARCHITECTURE.md](../architecture/API_ARCHITECTURE.md)
3. [../api/concepts-and-layering.md](../api/concepts-and-layering.md)
4. [code-style.md](code-style.md)
5. [route-implementation-guide.md](route-implementation-guide.md)
