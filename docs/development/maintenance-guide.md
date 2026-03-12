# Maintenance Guide

This guide defines how the repository should be maintained over time. It is not a cleanup memo. It is the operating standard for keeping the system coherent as more engineers change it.

## What Is Stable

These parts of the repository should be treated as stable architectural decisions:

- `api/main.py` is the only FastAPI app entrypoint
- `api/routers/` is the active backend HTTP layer
- `api/contracts/` is the contract layer
- `api/db/mongo/` is the shared Mongo runtime layer
- `coyote/services/api_client/` is the UI-to-API transport layer
- tests are split into `api`, `ui`, `integration`, `unit`, and `fixtures`

If one of these decisions must change, treat that as an architectural change, not a routine implementation edit. Update the architecture docs, deployment docs, and relevant tests in the same change set.

## What To Check Regularly

### Runtime health

Regularly verify:

- API health endpoint responds
- UI loads and can reach the API
- Docker dev stack starts cleanly
- Docker portable stack starts cleanly

### Dependency direction

Regularly verify:

- UI still does not import backend persistence internals
- direct Mongo usage has not spread into routers or blueprints
- API client helpers remain centralized

### Documentation drift

Regularly verify:

- startup commands still match reality
- Compose file names and ports are correct in docs
- test directory names in docs match the repository
- extension instructions still match the current layering

## Safe Maintenance Pattern

When touching a feature, use this sequence:

1. locate the owning layer
2. change only the owning layer first
3. run the narrowest useful tests
4. run the full suite before finishing
5. update docs if structure, runtime, or extension patterns changed

## Common Maintenance Tasks

### Add a route

- update `api/contracts/`
- update `api/routers/`
- update service or workflow logic
- update repository and Mongo handlers if persistence changes
- add backend tests
- add UI integration only after the API contract exists

### Add a new UI screen

- add or extend the correct blueprint
- add or extend the API client helper
- add templates
- add UI tests

### Change a Mongo query path

- keep query code in `api/repositories/`, `api/infra/db/`, or `api/db/mongo/`
- review indexes if the query becomes part of a hot path
- add route and integration tests for the changed behavior

### Change deployment behavior

- update Compose files
- verify container names, ports, and health endpoints
- update deployment docs

### Refresh dev Mongo from a curated snapshot

- use `scripts/create_mongo_micro_snapshot.py` to create the snapshot from the source Mongo environment
- keep collection selection driven by `config/coyote3_collections.toml`
- restore into dev Docker Mongo with `scripts/restore_mongo_micro_snapshot.py --target dev --drop-db --db-map coyote3=coyote_dev_3`
- verify the restore populated business-key fields such as `user_id`, `sample_id`, and `variant_id`
- verify login and sample-linked API routes before considering the refresh complete

## Anti-Patterns To Avoid

- adding a second route tree outside `api/routers/`
- reintroducing backend compatibility shims without a removal plan
- placing business logic directly in Flask views
- placing raw database queries in routers
- adding generic utility modules instead of extending the correct domain package
- removing tests because they are inconvenient instead of fixing the seam they expose

## Definition Of Healthy Maintenance

The repository is being maintained correctly when:

- new work follows the existing folder ownership
- tests still reflect the real architecture
- docs read like the system design, not a migration history
- startup and deployment paths remain unambiguous
- the UI remains a client of the API instead of a second backend
