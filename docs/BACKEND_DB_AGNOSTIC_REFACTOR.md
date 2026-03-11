# Backend DB-Agnostic Refactor and Ports Guide

## 1. Why this refactor exists
Coyote3 started with route/core logic calling Mongo handlers (`store.*`) directly. That worked for feature velocity, but it created architectural risk:
- business logic became coupled to one persistence implementation
- route modules owned query orchestration details
- changes in one storage concern had broad blast radius
- tests validated outputs, but boundaries were weak

The refactor goal is to make persistence a replaceable implementation detail while keeping runtime Mongo behavior stable.

## 2. Ports and adapters pattern in Coyote3
The refactor uses a strict `Port -> Adapter` split:
- `Port`: protocol/interface in `api/core/**/ports.py` describing required data operations in domain language
- `Adapter`: Mongo implementation in `api/infra/repositories/*_mongo.py`
- `Route/Core`: depends only on ports, never directly on database handlers or driver imports

This is an anti-corruption layer between business rules and storage-specific query mechanics.

## 3. What this gives us technically
### 3.1 Lower coupling
Core and route logic no longer import `store` directly. A backend change (Mongo shape/index/query details) is isolated in repository adapters.

### 3.2 Better testability
Service logic can be tested with fake adapters implementing the same protocol. This reduces integration-heavy testing for pure behavior checks.

### 3.3 Safer migrations
When changing database engine or collection schema, we can implement a new adapter while preserving route/service contracts.

### 3.4 Clear ownership boundaries
- `api/routes`: request/response + access checks + service orchestration
- `api/core`: domain/use-case behavior
- `api/infra/repositories`: persistence details

## 4. Current implementation status
### 4.1 Boundary enforcement
- Contract guardrail: `tests/contract/test_backend_db_boundary_guardrails.py`
- Baseline generator: `scripts/refresh_backend_db_boundary_baseline.py`
- Current baseline target achieved:
  - `store_usage_total=0`
  - `mongo_leak_usage_total=0`

### 4.2 Ported contexts implemented
Examples already migrated to explicit ports/adapters:
- security/auth
- public catalog
- admin sample deletion
- RNA workflow
- DNA reporting
- coverage processing
- dashboard route read model
- home route read/mutation flows
- common route read/search flows
- samples mutation flows
- coverage route read flows
- internal utility routes

### 4.3 Strict mode status
Business-key migration and strict adapter wiring are complete for active backend collections.

Key outcomes:
- business key fields are now canonical in handler lookup/update paths
- `_id` compatibility read-fallbacks removed for string-id bounded contexts
- dynamic shim repositories (`__getattr__` forwarding to `store`) replaced with explicit adapter surfaces
- collection migration is automated through one script: `scripts/backfill_business_keys.py`

## 5. Route/core dependency rules
### 5.1 Allowed
- `api/routes/*` imports `api/core/*` and port-backed adapter wiring helpers
- `api/core/*` imports protocol ports and domain models
- `api/infra/*` imports Mongo/store/driver code

### 5.2 Forbidden
- `api/routes/*` importing `store`, Mongo client, or handler internals
- `api/core/*` importing `store`, `pymongo`, `bson`, `motor`, or Flask-PyMongo

## 6. How to add a new use-case correctly
1. Define protocol in `api/core/<context>/ports.py`.
2. Implement Mongo adapter in `api/infra/repositories/<context>_mongo.py`.
3. Inject adapter once in route/service wiring.
4. Keep route logic free of query details.
5. Add/refresh boundary baseline and tests.

## 7. Pattern examples in this repository
- Dashboard route using explicit port:
  - `api/core/dashboard/ports.py`
  - `api/infra/repositories/dashboard_mongo.py`
  - `api/routes/dashboard.py`
- Home route using explicit port:
  - `api/core/home/ports.py`
  - `api/infra/repositories/home_mongo.py`
  - `api/routes/home.py`

## 8. Final strict-mode implementation (what changed)
### 8.1 Shim cleanup
Removed dynamic passthrough shims by making repository surfaces explicit:
- `api/infra/repositories/admin_route_mongo.py`
- `api/infra/repositories/dna_route_mongo.py`
- `api/infra/repositories/rna_route_mongo.py`
- `api/infra/repositories/core_store_mongo.py`

Why:
- explicit attributes make coupling visible in review and static analysis
- removing `__getattr__` prevents accidental handler reach-through and hidden dependency growth

### 8.2 Business-key strictness
Collection handlers now enforce canonical business keys for read/update operations in string-id contexts:
- users: `user_id`
- roles: `role_id`
- permissions: `permission_id`
- schemas: `schema_id`
- asp: `asp_id`
- asp_configs: `aspc_id`
- isgl: `isgl_id`

ObjectId-dominant collections also receive explicit business key fields + unique indexes for provider portability:
- samples, variants, cnvs, translocations, fusions
- annotation, reported_variants, group_coverage, blacklist
- optional collections when present: biomarkers, rna_expression, rna_classification, rna_qc

### 8.3 Route-side canonical writes
Admin create/update flows now set canonical key fields explicitly before persistence (for example `permission_id`, `role_id`, `user_id`, `aspc_id`, `schema_id`).

Why:
- removes implicit ID derivation logic from handler fallback branches
- ensures future non-Mongo adapters receive stable identity fields

## 9. Migration runbook (how to apply)
1. Restore snapshot.
2. Run business-key backfill and index enforcement:

```bash
/home/ram/.virtualenvs/coyote3/bin/python scripts/backfill_business_keys.py \
  --mongo-uri mongodb://localhost:37017 \
  --db coyote_dev_3 \
  --db coyote3
```

3. Validate a representative sample:

```bash
/home/ram/.virtualenvs/coyote3/bin/python - <<'PY'
from pymongo import MongoClient
c = MongoClient("mongodb://localhost:37017")
for dbn in ("coyote_dev_3", "coyote3"):
    db = c[dbn]
    print(dbn, {
        "users_user_id": db["users"].count_documents({"user_id": {"$exists": True, "$type": "string"}}),
        "roles_role_id": db["roles"].count_documents({"role_id": {"$exists": True, "$type": "string"}}),
        "variants_variant_id": db["variants"].count_documents({"variant_id": {"$exists": True, "$type": "string"}}),
    })
PY
```

## 10. Decision record summary
This architecture intentionally accepts some adapter boilerplate in exchange for:
- predictable boundaries
- reduced hidden coupling
- future backend portability
- better long-term maintainability in regulated clinical workflows

For Coyote3, this tradeoff is favorable and required for safe evolution.

## 11. Why ports are mandatory for DB swap simplicity
If route/core code talks to Mongo directly, a provider swap requires editing business code everywhere. Ports prevent that.

With ports:
1. Business code calls a stable interface (for example `SecurityRepository.get_user_by_id`).
2. Mongo-specific query details stay in one adapter (`*_mongo.py`).
3. A new provider only needs a new adapter implementation for the same port.
4. Wiring selects provider at bootstrap; route/core logic stays unchanged.

Result:
- provider change becomes an infrastructure replacement task, not an application rewrite task.
- migration risk is limited to adapter tests and data-mapping validation.
