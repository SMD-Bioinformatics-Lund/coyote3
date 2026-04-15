# HTTP Layers and Boundaries

This page maps where HTTP enters the system, where it leaves the system, and which components own each boundary.

The key rule is simple:

- Inbound HTTP is handled by server frameworks and runtimes.
- Outbound HTTP is handled by `httpx`.

## Top-Level Map

```text
                                   TOP-LEVEL HTTP MAP

  [A] Inbound web traffic                         [B] Inbound API traffic
  Browser                                         Browser / script / service
     |                                                     |
     v                                                     v
  Gunicorn (WSGI)                                      Uvicorn (ASGI)
     |                                                     |
     v                                                     v
  Flask app (`coyote/`)                                FastAPI app (`api/`)
     |                                                     |
     |---- render templates / redirects                    |---- validate / authorize / return JSON
     |
     |  [C] Outbound app-to-app HTTP
     |  via `httpx`
     v
  Web API client (`coyote/services/api_client/`)
     |
     v
  `httpx.Client`
     |
     v
  FastAPI routes (`api/routers/`)
     |
     v
  Services / core / Mongo handlers / Redis
```

The rest of this page expands `A`, `B`, and `C`.

## A. Web UI Inbound HTTP

This is the path for a browser request that targets the Flask UI.

```text
Browser
  |
  v
Gunicorn
  |
  v
Flask app (`coyote/__init__.py`)
  |
  v
Blueprint route (`coyote/blueprints/.../views.py`)
  |
  +--> render Jinja template
  |
  +--> redirect / flash / return web error page
  |
  +--> call web API client for backend data
```

Concise ownership summary:

- `Gunicorn` accepts inbound web HTTP and runs the WSGI app.
- `Flask` owns web routing, sessions, template rendering, and page responses.
- Flask views may call the backend API, but they do not implement backend business logic directly.

## B. API Inbound HTTP

This is the path for direct requests into the FastAPI backend.

```text
Browser / script / internal caller
  |
  v
Uvicorn
  |
  v
FastAPI app (`api/main.py`)
  |
  v
Middleware (`api/middleware.py`)
  |
  v
Router (`api/routers/...`)
  |
  +--> dependency resolution
  |      - auth
  |      - permission checks
  |      - scope checks
  |
  +--> request model validation
  |
  v
Service / core workflow
  |
  v
Mongo handlers / Redis / other infra
  |
  v
JSON response
```

Concise ownership summary:

- `Uvicorn` accepts inbound API HTTP and runs the ASGI app.
- `FastAPI` owns API routing, dependency injection, validation, and JSON response serialization.
- API services own domain workflows and persistence coordination.

## C. Web-To-API Outbound HTTP

This is the internal HTTP client path used when the Flask UI needs backend data from FastAPI.

```text
Flask blueprint/view
  |
  v
Web API facade (`get_web_api_client`)
  |
  v
Shared transport (`BaseApiClient`)
  |
  v
`httpx.Client`
  |
  v
FastAPI endpoint
```

Code anchors:

- Client facade: `coyote/services/api_client/api_client.py`
- Shared transport: `coyote/services/api_client/base.py`
- API auth helpers for external callers: `api/client/auth.py`

Concise ownership summary:

- `httpx` is the outbound HTTP layer.
- Flask does not talk to Mongo directly for backend workflows; it goes through the API over HTTP.
- The web API client centralizes headers, cookies, auth forwarding, timeouts, and error translation.

## D. External Automation And Script Path

This is the path for scripts or automation that call the API directly.

```text
Automation script / CLI / service
  |
  +--> use `api/client/auth.py`
  |         or direct `httpx`
  |
  v
`httpx`
  |
  v
FastAPI endpoint
  |
  v
API services / persistence
```

Concise ownership summary:

- External callers are also outbound HTTP clients.
- They should use `httpx` when calling the API.
- They enter the same FastAPI inbound stack described above.

## Responsibility Matrix

```text
Inbound web HTTP     -> Gunicorn + Flask
Inbound API HTTP     -> Uvicorn + FastAPI
Outbound HTTP        -> httpx
Template rendering   -> Flask + Jinja
JSON API contract    -> FastAPI + Pydantic
Persistence access   -> API services + Mongo handlers
```

## Practical Reading Guide

If you are trying to understand one request end to end, read the layers in this order:

1. Start at the inbound entrypoint: Flask route or FastAPI route.
2. Identify whether the path stays inside that app or crosses the internal HTTP boundary.
3. If Flask needs backend data, follow the `httpx` client path into the FastAPI route.
4. From the FastAPI route, follow dependencies, service logic, and Mongo handlers.
5. Then trace the response path back to JSON or template rendering.

See also:

- [System Architecture](system_overview.md)
- [System Relationships](system_relationships.md)
- [Request Lifecycle Architecture](request_lifecycle.md)
- [Codebase Map](codebase_map.md)
