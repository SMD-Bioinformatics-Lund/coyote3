# API Concepts And Layering

## Purpose
This guide explains the Coyote3 API from first principles. It is written for developers who may not already know FastAPI, layered backend architecture, or the terminology used in this repository.

If you only remember one rule, remember this:

`router -> service -> repository -> mongo handler -> MongoDB`

Each layer exists to solve a different problem. Keeping those problems separated is what makes the codebase maintainable.

## What The API Is

The code under `api/` is the authoritative backend application.

It owns:

- authentication
- authorization
- request validation
- business workflows
- persistence
- audit and request logging
- OpenAPI documentation

The Flask UI under `coyote/` is a client of the API. It is not a second backend.

## The Main Layers

### Routers

Routers live in `api/routers/`.

Routers are the HTTP entrypoint layer. A router should:

- declare the path and HTTP method
- parse path, query, and body inputs
- bind dependencies with `Depends(...)`
- enforce authorization with `require_access(...)`
- call a service or repository
- return the final response

Routers should not:

- build raw Mongo queries
- coordinate large workflows
- normalize large domain payloads inline

Think of routers as transport adapters.

### Contracts

Contracts live in `api/contracts/`.

A contract is the typed request or response shape at the API boundary. In practice, a contract is usually a Pydantic model or a transport DTO-style object that tells clients:

- what fields they can send
- which fields are required
- what shape the API returns
- what types are valid

Contracts should:

- be explicit
- be typed
- be stable
- describe transport shapes clearly

Contracts should not:

- access the database
- own business orchestration
- make HTTP calls
- modify persistent state

When someone asks, "what does this endpoint accept?" or "what does it return?", the answer should usually come from the contracts first.

### Services

Services live in `api/services/`.

Services own application workflow. This is the place for:

- orchestration across multiple repositories
- business-rule branching
- normalization of inputs and outputs
- shared mutation logic
- cross-resource logic such as classifications, annotations, or report composition

Services should be easy to unit-test with fake repositories.

Services should not:

- own raw HTTP parsing
- build low-level Mongo queries directly

### Repositories

Repositories live in `api/repositories/`.

Repositories are the persistence-facing seam used by services and, in simple cases, directly by routers.

Repositories should:

- expose application-level data operations
- hide Mongo implementation details
- compose lower-level Mongo handler calls

Repositories should not:

- parse HTTP requests
- shape Flask or FastAPI responses
- duplicate authorization logic

### Mongo Handlers And Database Runtime

Mongo-specific logic lives in:

- `api/db/mongo/`
- `api/infra/db/`

This layer owns:

- client creation
- collection binding
- index creation
- raw queries
- collection-specific helpers

This layer should not own:

- HTTP transport
- UI logic
- business workflows

## A Full Request Example

Example flow for a mutation:

1. A client calls an API endpoint.
2. Middleware attaches request context and auth state.
3. A router receives the request.
4. The router validates the payload using contracts.
5. The router enforces access with `require_access(...)`.
6. The router calls a service.
7. The service decides how the workflow should run.
8. The service calls one or more repositories.
9. Repositories call Mongo handlers.
10. Mongo handlers read or write MongoDB.
11. The service returns a result.
12. The router returns a response contract.

This is why layering matters: each step can evolve without forcing unrelated changes in the others.

## Validation

Validation happens in more than one place.

### Contract validation

This is transport validation:

- missing required fields
- wrong types
- invalid enum values
- malformed request bodies

### Service validation

This is business validation:

- invalid state transitions
- unsupported combinations
- illegal workflow operations

### Repository validation

This is persistence validation:

- resource not found
- duplicate conflict
- index-backed invariants

Do not force every validation problem into one layer.

## Authentication And Authorization

Authentication answers:

- who is the caller?

Authorization answers:

- is the caller allowed to do this?

In this repository:

- authentication is session-based
- authorization is enforced in API routers with `require_access(...)`
- UI visibility helpers are convenience only

The API is the final authority.

## Resource-Oriented Design

The active API uses resource-oriented routes.

Examples:

- `/api/v1/samples/{sample_id}/small-variants`
- `/api/v1/samples/{sample_id}/cnvs`
- `/api/v1/samples/{sample_id}/translocations`
- `/api/v1/samples/{sample_id}/fusions`
- `/api/v1/samples/{sample_id}/classifications`
- `/api/v1/samples/{sample_id}/annotations`
- `/api/v1/samples/{sample_id}/reports/{report_type}`

This is preferred because it is easier for clients to learn and easier to extend consistently.

## Versioning

The API is versioned under `/api/v1`.

Versioning is part of the public transport contract. New endpoints should stay within the versioned surface unless there is a strong architectural reason not to.

## Error Handling

Errors should be:

- consistent
- explicit
- machine-readable
- centrally shaped where possible

Routers should not invent one-off error payloads unless there is a very strong reason.

## What To Put Where

Put code in `api/contracts/` if:

- it defines request or response structure
- it validates transport fields
- it belongs in OpenAPI

Put code in `api/routers/` if:

- it is HTTP-specific
- it enforces route access
- it binds dependencies
- it returns the final response

Put code in `api/services/` if:

- it coordinates a workflow
- it contains business branching
- it applies cross-resource rules

Put code in `api/repositories/` if:

- it is persistence-oriented
- it should hide Mongo details from upper layers

Put code in `api/db/mongo/` or `api/infra/db/` if:

- it is a raw query
- it is collection bootstrap or index logic
- it is a low-level Mongo helper

## Common Mistakes

Avoid these:

- putting Mongo queries in routers
- putting workflow orchestration in contracts
- returning ad-hoc transport shapes without explicit contracts
- making services depend on Flask or browser concerns
- assuming UI visibility is enough to enforce permissions

## How To Add A New Endpoint

1. Choose the resource and canonical path.
2. Define request and response contracts.
3. Add the router.
4. Enforce access with `require_access(...)`.
5. Add or extend a service if workflow logic is non-trivial.
6. Add or extend repository methods.
7. Add or extend Mongo handlers.
8. Add tests for success, validation, and authorization.
9. Update the docs.

## How To Review An Endpoint

Ask these questions:

- Is the path resource-oriented?
- Is the method semantically correct?
- Is the contract explicit?
- Is access enforced at the router boundary?
- Is business logic in a service instead of the router?
- Is persistence hidden behind a repository?
- Are tests covering success, validation, and authorization?

## Related Documentation

- [reference.md](reference.md)
- [endpoint-catalog.md](endpoint-catalog.md)
- [../architecture/API_ARCHITECTURE.md](../architecture/API_ARCHITECTURE.md)
- [../development/developer-guide.md](../development/developer-guide.md)
