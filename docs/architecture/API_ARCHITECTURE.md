# API Architecture

This document explains how the FastAPI backend is structured, why the layers exist, and how requests move through the system.

## System Role

The backend in `api/` is the authoritative server-side application for Coyote3.

It owns:

- authentication
- authorization
- request validation
- business workflows
- persistence
- audit and request logging
- OpenAPI documentation

The Flask UI is a client of this backend. The UI does not replace backend policy enforcement.

## Entry Points

- [main.py](/home/ram/dev/projects/coyote3/api/main.py) is the authoritative ASGI application module.
- `uvicorn api.main:app` is the canonical local startup command.
- [lifecycle.py](/home/ram/dev/projects/coyote3/api/lifecycle.py) owns startup and shutdown behavior.
- [config.py](/home/ram/dev/projects/coyote3/api/config.py) assembles runtime configuration.

## Runtime Flow

```text
HTTP request
  -> middleware
  -> router
  -> auth dependency
  -> service
  -> repository
  -> mongo handler
  -> MongoDB
  -> response contract
  -> HTTP response
```

Each layer has a different responsibility. New code should follow the same model.

## Package Responsibilities

### `api/routers/`

The HTTP transport layer.

Routers should:

- declare paths and methods
- parse request input
- bind dependencies
- enforce access with `require_access(...)`
- call services or repositories
- return response contracts

Routers should not:

- build raw Mongo queries
- own large workflow branching

### `api/contracts/`

The transport contract layer.

Contracts define:

- request bodies
- response bodies
- nested API payloads
- validation rules for transport data

If the term `contract` is unfamiliar, read [../api/concepts-and-layering.md](../api/concepts-and-layering.md). In short: a contract is the typed agreement between the API and its clients.

### `api/services/`

The application workflow layer.

Services own:

- orchestration
- normalization
- multi-step mutation logic
- cross-resource workflows

### `api/repositories/`

The persistence-facing abstraction layer.

Repositories hide Mongo-specific persistence details from services and routers.

### `api/db/mongo/`

The Mongo runtime layer.

This layer owns:

- client creation
- database setup
- collection access setup
- indexes

### `api/infra/db/`

The low-level collection handler layer.

This layer owns:

- raw collection queries
- collection-specific persistence helpers

### `api/deps/`

Dependency factories for:

- auth
- repositories
- services

### `api/security/`

Authentication and authorization helpers.

### `api/audit/`

Request and mutation audit support.

## Dependency Direction

The intended dependency direction is:

`router -> service -> repository -> api/infra/db and api/db/mongo -> MongoDB`

Important rules:

- routers must not access Mongo directly
- services must not build raw Mongo queries
- UI code must not import backend persistence internals

## Authorization Model

The API is the authoritative enforcement point for access control.

Access is enforced at the router boundary with `require_access(...)`, usually with one or more of:

- `permission`
- `min_role`
- `min_level`

This keeps authorization local and easy to review.

## Versioning

The API is versioned under `/api/v1`.

New public API behavior should remain inside the versioned namespace.

## Resource-Oriented Design

The API is organized around resources rather than legacy assay buckets.

Canonical examples:

- `/api/v1/samples/{sample_id}/small-variants`
- `/api/v1/samples/{sample_id}/cnvs`
- `/api/v1/samples/{sample_id}/translocations`
- `/api/v1/samples/{sample_id}/fusions`
- `/api/v1/samples/{sample_id}/biomarkers`
- `/api/v1/samples/{sample_id}/classifications`
- `/api/v1/samples/{sample_id}/annotations`
- `/api/v1/samples/{sample_id}/reports/{report_type}`

## Validation And Error Handling

Design expectations:

- request bodies use explicit contracts
- access failures are explicit
- centralized error handling keeps response behavior consistent
- route handlers should not invent ad-hoc error shapes

## Testing Expectations

Each layer should be tested at the correct level:

- router tests for auth, validation, and response shape
- service tests for workflow branching
- integration tests for layer boundaries

## How To Add A New Endpoint

1. Choose the resource and canonical path.
2. Define request and response contracts.
3. Add or extend the router.
4. Enforce access with `require_access(...)`.
5. Add or extend a service if needed.
6. Add or extend repository methods.
7. Add or extend Mongo handlers.
8. Add tests.
9. Update docs.

## Related Documentation

- [../api/concepts-and-layering.md](../api/concepts-and-layering.md)
- [../api/reference.md](../api/reference.md)
- [../api/endpoint-catalog.md](../api/endpoint-catalog.md)
- [repository-structure.md](repository-structure.md)
