# Auth, RBAC, and Request Lifecycle

This chapter defines how authentication and authorization are enforced in Coyote3.

## Authentication model

Authentication is handled through login routes in the login blueprint and Flask-Login session management.

Key elements:

- LDAP-backed identity integration in production environments
- session user model maintained by Flask-Login
- per-request user context refresh

## Request lifecycle enforcement

Two core checks happen before business logic executes:

1. Session/user refresh check.
2. Access check for route-level authorization constraints.

If either check fails, execution is redirected or blocked before domain logic runs.

## Authorization model

Coyote3 uses layered authorization:

- route permission checks via `@require(...)`
- sample-level access checks via sample-access decorator
- UI-level visibility helpers for conditional controls

UI helpers improve usability, but route decorators are the source of truth.

## Access helper functions in templates

Injected helper functions include:

- `can(...)`
- `min_level(...)`
- `min_role(...)`
- `has_access(...)`

These should never replace backend route protection.

## Audit logging behavior

Selected actions are logged through audit decorators.

Route handlers can attach contextual metadata in request context (`g.audit_metadata`) to enrich audit trails.
