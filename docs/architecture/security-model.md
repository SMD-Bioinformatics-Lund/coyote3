# Security Model

## Layers

1. Authentication (session/login)
2. Authorization (role + permission checks)
3. Internal token gate for system-to-system routes
4. Environment secret hardening (prod/dev strict behavior)

## User permissions

Permission checks are enforced in API route/service flow for data-mutating operations.

## Internal routes

`/api/v1/internal/*` routes require internal token and must not be exposed publicly without network/policy controls.

## Secrets and credentials

Do not commit real secrets.

Required secrets include:

- `SECRET_KEY`
- `INTERNAL_API_TOKEN`
- `COYOTE3_FERNET_KEY`
- Mongo credentials (`MONGO_ROOT_*`, `MONGO_APP_*`)

## Mongo security

- Use dedicated app user with least required role (`readWrite` on target DB)
- Use separate Mongo instances per environment for strict isolation
- Never rely on unauthenticated DB in shared/non-local environments
