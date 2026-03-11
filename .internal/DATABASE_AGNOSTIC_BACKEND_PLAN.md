# Database-Agnostic Backend Refactor Plan (Mongo Active Now)

## Objective
Make backend business/domain logic independent of the current database framework so future engine swaps (for example MongoDB -> PostgreSQL) are low-friction.

Important scope clarification:
- MongoDB remains the active runtime database now.
- We are refactoring architecture, not executing a DB switch in this plan.

This plan is complete-scope (all backend surfaces), not partial.

## Non-Negotiable Rules
1. Domain and use-case code must not depend on driver/ORM specifics.
2. Route layer must not orchestrate database query details.
3. Persistence dependencies are confined to infrastructure implementations.
4. Repository/service contracts become canonical integration points.
5. New code must follow these boundaries from day one.
6. MongoDB runtime remains containerized (Docker) as the supported local/dev path; no local DB installation requirement.
7. Collections must gradually move away from non-standard `_id` usage: keep `_id` for technical identity and add an explicit unique business key where applicable.

## Current State Summary
- Coupling to `MongoAdapter` singleton in routes/core.
- Mongo-specific types and semantics leak beyond infra in some modules.
- Query orchestration is distributed in routes and workflow services.

## Progress Snapshot (2026-03-11)
Completed:
1. Portable Docker-first Mongo runtime for local/dev with external-volume support and restore tooling.
2. Boundary guardrails in contract tests:
   - `tests/contract/test_backend_db_boundary_guardrails.py`
   - baseline refresh script: `scripts/refresh_backend_db_boundary_baseline.py`
3. Initial repository-port migrations:
   - Security/auth repository port + Mongo adapter
   - Public catalog repository port + Mongo adapter
   - Admin sample deletion repository port + Mongo adapter
   - RNA workflow repository port + Mongo adapter
   - DNA reporting repository port + Mongo adapter
   - Coverage processing repository port + Mongo adapter
   - Shared/admin/RNA/DNA route repository facades (remove direct `store.*` from route layer)
4. Core auth/public/admin/RNA/DNA-reporting/coverage workflows now run through repository services in targeted paths.
5. Route-layer boundary hardening complete for current API surface:
   - `api/routes/{admin,dna,rna,dashboard,home,common,samples,coverage,internal}.py` now use route repository facades instead of direct `store.*`.
6. Core boundary hardening complete for direct `store.*`:
   - `api/core/interpretation/annotation_enrichment.py`
   - `api/core/interpretation/report_summary.py`
   - `api/core/reporting/pipeline.py`
   now use a core repository facade instead of direct `store.*`.
7. Explicit route repository ports/adapters implemented for:
   - dashboard (`api/core/dashboard/ports.py`, `api/infra/repositories/dashboard_mongo.py`)
   - home (`api/core/home/ports.py`, `api/infra/repositories/home_mongo.py`)
   - common (`api/core/common/ports.py`, `api/infra/repositories/common_mongo.py`)
   - samples (`api/core/samples/ports.py`, `api/infra/repositories/samples_mongo.py`)
   - coverage-read (`api/core/coverage/route_ports.py`, `api/infra/repositories/coverage_route_mongo.py`)
   - internal utilities (`api/core/internal/ports.py`, `api/infra/repositories/internal_mongo.py`)
8. Shared route facade removed (`api/infra/repositories/route_store_mongo.py` deleted).
9. Collection business-key rollout started with first two collections completed:
   - `users`: canonical `user_id` path added in handler/auth/session flow
   - `roles`: canonical `role_id` path added in handler flows
   - partial unique indexes: `users.user_id`, `roles.role_id`
   - compatibility fallback to `_id` retained in adapter layer
   - backfill scripts added:
     - `scripts/backfill_users_user_id.py`
     - `scripts/backfill_roles_role_id.py`
10. Collection-wide business-key rollout completed for all planned collections:
   - handler-level business-key index definitions added in `api/infra/db/*`
   - strict business-key lookup enabled for string-id collections (`users`, `roles`, `permissions`, `schemas`, `asp`, `asp_configs`, `isgl`)
   - bulk migration tool added: `scripts/backfill_business_keys.py`
   - executed on both local DBs: `coyote_dev_3`, `coyote3`
   - alias collections also migrated: `*_beta2`, `cnvs_wgs`, `transloc`
11. Final shim/fallback cleanup completed:
   - removed dynamic `__getattr__` passthrough shims from admin/dna/rna/core repository adapters
   - admin mutation flows now write canonical key fields explicitly before persistence
   - `_id` compatibility read-fallbacks removed in strict business-key handlers

Latest baseline totals after refactor:
- `store_usage_total=0` (down from 322)
- `mongo_leak_usage_total=0` (down from 2)

## Target Architecture
- `api/domain`: pure business entities/value objects.
- `api/core`: use-case services depending on repository interfaces (ports).
- `api/infra/repositories/*`: concrete persistence adapters (Mongo now, others later).
- `api/routes`: request/response mapping + service invocation only.
- Runtime wiring selects one concrete adapter implementation (Mongo today).

## Data Identity Policy (Strict Runtime, Gradual Rollout Process)
Mongo remains active, but identity strategy is normalized now to be future-portable:

1. `_id` stays as technical primary identifier for existing collections.
2. Add explicit unique key fields for business identity in most collections (examples: `user_id`, `sample_id`, `variant_id`, `asp_id`, `isgl_id`).
3. New code must use business keys in domain/service contracts; `_id` is not used as business identity.
4. Rollout was gradual per collection/workstream; runtime policy is now strict business-key mode.
5. Every new business key must have a unique index and collision test coverage.

Notes:
- For legacy collections already using string `_id`, `*_id` business fields are now canonical for service/repository behavior.
- For ObjectId-backed collections, business keys are now present + indexed; `_id` remains technical identity for document storage internals.

## Mongo Runtime Policy (Docker First)
1. Use Docker Compose Mongo image as the default local/dev runtime.
2. Prefer latest free/community image tag policy approved by the team (pinned in compose for reproducibility).
3. No requirement to install Mongo locally outside Docker.
4. Keep initialization scripts and index bootstrap automation container-friendly.

## Execution Phases

### Phase 0: Governance and acceptance gates
Status: `in_progress`

Tasks:
1. Freeze new direct DB calls in routes/core.
2. Define quality gates:
   - API tests green
   - no behavior regression in dashboard, DNA, RNA, reporting, admin CRUD
3. Define code ownership of boundary refactors by workstream.

Exit criteria:
- approved architecture rules and gates

---

### Phase 1: Contract and model normalization
Status: `in_progress`

Tasks:
1. Normalize API/domain contracts so they are persistence-agnostic.
2. Remove assumptions tied to Mongo-only ID semantics from domain contracts.
3. Keep wire/API compatibility where required, but isolate representation mapping at boundaries.
4. Introduce/normalize business unique keys in contracts for each workstream.

Files expected:
- `api/contracts/*`
- `api/domain/models/*`
- shared serialization utilities

Exit criteria:
- domain contracts are DB-neutral
- business key contract strategy defined for all target collections

---

### Phase 2: Define repository ports for all bounded contexts
Status: `in_progress`

Tasks:
1. Define interfaces for:
   - users/roles/permissions
   - samples/reports
   - variants/cnv/transloc/fusions/annotations
   - asp/aspc/isgl/schemas
   - coverage/groupcoverage
2. Move query intent into repository methods (not route-specific DB expressions).

Exit criteria:
- complete port set for all backend workstreams

---

### Phase 3: Move business logic behind use-case services
Status: `in_progress`

Tasks:
1. Refactor `api/core` to consume ports only.
2. Remove `store.*` direct persistence calls from core workflows/services.
3. Keep behavior and output contracts unchanged.

Exit criteria:
- core/use-case layer has no direct infra DB dependency

---

### Phase 4: Route layer decoupling
Status: `in_progress`

Tasks:
1. Refactor routes to call use-case services only.
2. Remove route-level DB orchestration and multi-handler query composition.
3. Keep all response contracts stable.

Exit criteria:
- routes contain no persistence orchestration logic

---

### Phase 5: Infrastructure adapter cleanup and enforcement
Status: `in_progress`

Tasks:
1. Keep Mongo concrete adapter implementation in infra.
2. Align handlers/repositories with new port contracts.
3. Add architecture tests to enforce:
   - no direct infra DB imports in routes/core/domain
   - no new direct `store.*` usage in routes/core except approved wiring points
4. Add/verify unique indexes for business keys on migrated collections.

Exit criteria:
- architectural boundaries enforced by tests/CI
- migrated collections have both technical identity and validated unique business keys

---

### Phase 6: Optional future DB engine implementation path
Status: `planned`

Tasks (future, after phases 0-5 complete):
1. Implement new engine repositories (for example Postgres) against existing ports.
2. Add migration tooling and data migration scripts.
3. Perform planned cutover when business approves engine switch.

Exit criteria:
- alternate DB backend can be introduced without rewriting routes/core/domain

## Workstream Breakdown (all backend areas)
1. Auth and access control
2. Dashboard and home summaries
3. DNA workflows
4. RNA workflows
5. Reporting and reported variants
6. Admin CRUD and schema management
7. Coverage workflows
8. Public catalog endpoints
9. Utilities and shared helpers
10. Runtime/bootstrap/config wiring

## Collection-by-Collection Rollout Template
Use this template for each collection to ensure full-scope, non-partial progress:
1. Define business unique key and semantics.
2. Add unique index in Mongo.
3. Update repository methods to support business-key lookups.
4. Update service contracts to prefer business key.
5. Remove direct `_id` assumptions from route/core for that collection.
6. Add regression tests (CRUD + lookup + uniqueness violations).

## Test and Quality Plan
1. Contract tests for API payload stability.
2. Service-level tests for business behavior (DB-neutral).
3. Infrastructure integration tests for Mongo adapter against repository ports.
4. Architecture boundary tests (imports and forbidden direct DB usage).
5. E2E smoke tests for primary workflows.

## CI Policy During Refactor
1. Track and burn down direct `store.*` usage in routes/core.
2. Block new DB-driver-specific code outside infra.
3. Require tests for every boundary change.

## Delivery Cadence
- Execute phase-by-phase with hard exit criteria.
- No phase is complete without tests and docs updates.
- Continue until DB-agnostic architecture is complete across all workstreams.

## Next Up (Immediate)
1. Expand repository ports for remaining bounded contexts:
   - DNA/RNA entities, coverage, reporting, admin schemas/panels/users.
2. Continue replacing any remaining broad route orchestration with explicit repository-port contracts per module.
3. Validate collection-level business-key rollout in CI and promote to deployment runbook:
   - `.internal/COLLECTION_KEY_MIGRATION_MATRIX.md`
   - `scripts/backfill_business_keys.py`
4. Increase service-level regression test depth for route flows currently validated primarily by boundary tests.

## Active Collection Execution Order
This is the implementation order to make provider swap practical and low-risk:
1. `users` (done)
2. `roles` (done)
3. `permissions` (done)
4. `schemas` (done)
5. `asp` (done)
6. `asp_configs` (done)
7. `isgl` (done)
8. `samples` (done)
9. `variants` (done)
10. `cnvs` (done)
11. `translocations` (done)
12. `fusions` (done)
13. `annotation` (done)
14. `reported_variants` (done)
15. `group_coverage` (done)
16. `blacklist` (done)
17. `biomarkers` (done when collection exists)
18. `rna_expression` (done when collection exists)
19. `rna_classification` (done when collection exists)
20. `rna_qc` (done when collection exists)
