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

### 4.3 Remaining architectural debt
Some areas still require deeper migration from "route orchestration" to dedicated use-case services and richer repository contracts:
- high-churn DNA/RNA/admin route workflows
- business-key-first contracts (collection-by-collection)
- stronger service-level regression tests per bounded context

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

## 8. Decision record summary
This architecture intentionally accepts some adapter boilerplate in exchange for:
- predictable boundaries
- reduced hidden coupling
- future backend portability
- better long-term maintainability in regulated clinical workflows

For Coyote3, this tradeoff is favorable and required for safe evolution.
