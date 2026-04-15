# Request Lifecycle Architecture

This document describes how a request moves through the web application, API, and persistence layers.

## Flow Diagram

The diagram below shows the main request path:

![Request lifecycle](../assets/diagrams/request_lifecycle.svg)

## Web Request Path

For a request that starts in the web UI:

1. The browser sends a request to a Flask blueprint route in `coyote/blueprints/...`.
2. The web layer prepares credentials and calls the matching backend API route.
3. The targeted backend endpoints validate strictly aligned data models.
4. Services and core logic perform the requested work.
5. Database handlers translate that work into Mongo queries and writes.
6. The API returns JSON success or error payloads.
7. The web layer renders the returned data into Jinja templates or shows an error page.

## Direct API Request Path

For requests that go directly to the API:

1. FastAPI routes receive the HTTP request.
2. Dependencies resolve authentication, permissions, and scope.
3. Pydantic models validate input payloads.
4. Services call the relevant domain logic.
5. Core modules perform calculations or transformations.
6. Database handlers perform reads or writes.
7. FastAPI serializes the response payload.

## Error Handling

The request path follows a consistent error model:

- Validation and permission failures are rejected at the boundary.
- Application faults should raise specific exceptions instead of hiding the underlying problem.
- API errors are returned in a structured JSON format.
- Logs should carry enough diagnostic context without leaking sensitive values.

See also:

- [HTTP Layers and Boundaries](http_layers.md) for a layered map of inbound web HTTP, inbound API HTTP, and outbound `httpx` client flows.
- [error_contract.md](error_contract.md) for the standard API/web error payload shape, categories, and user-facing mapping rules.
