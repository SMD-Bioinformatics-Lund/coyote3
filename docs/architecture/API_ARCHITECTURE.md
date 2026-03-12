## API Architecture

The Coyote3 backend is an independent FastAPI application rooted in `api/`.

### Entry points

- `api.main` is the authoritative ASGI application module.
- `uvicorn api.main:app` is the canonical local startup command.
- `api.app` remains only as a compatibility shim for legacy imports.

### Package responsibilities

- `api/routers/`: canonical resource-oriented API module paths.
- `api/services/`: application services coordinating resource behavior.
- `api/repositories/`: resource repositories used by services.
- `api/db/mongo/`: Mongo adapter entrypoint, settings, collections, and index bootstrap helpers.
- `api/contracts/`: API request/response contracts.
- `api/deps/`: dependency factories for auth, services, and repositories.
- `api/security/`: authentication and access control.
- `api/audit/`: request and mutation audit emission.

### Dependency direction

The intended dependency flow is:

`router -> service -> repository -> api/db/mongo -> MongoDB`

Direct Mongo access belongs in repository and `api/db/mongo` code only.

### Runtime bootstrap

- `api.lifecycle` owns runtime initialization.
- `api.config` exposes API-specific runtime and Mongo configuration helpers.
- `api.extensions` owns long-lived extension singletons used by the API runtime.
