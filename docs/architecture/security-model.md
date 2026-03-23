# Security Model

## Layers

1. Authentication (session/login)
2. Authorization (role + permission checks)
3. Internal token gate for selected system-to-system routes
4. Environment secret hardening (prod/dev strict behavior)

## User permissions

Permission checks are enforced in API route/service flow for data-mutating operations.

### Canonical role levels

Default role hierarchy used across API access checks:

- `external` -> `1`
- `viewer` -> `5`
- `intern` -> `7`
- `user` -> `9`
- `manager` -> `99`
- `developer` -> `9999`
- `admin` -> `99999`

Notes:

- Admin-only APIs and global destructive operations are guarded at `99999`.
- Bootstrap/seed role documents should use the same values to avoid unexpected authorization failures.

## Authentication providers

- User documents carry `auth_type` (for example `coyote3` local vs `ldap`).
- Login flow resolves the user first, then executes provider-specific authentication.
- Local users (`coyote3`) can use Coyote3-managed password flows:
  - authenticated password change
  - reset/set-password one-time token flows
  - admin invite flow for new local users
  - when SMTP is unavailable, invite/reset still issue one-time setup links and API/UI return warnings so admins can share links manually
- LDAP users authenticate against LDAP and should normally change passwords in the identity provider.

### Auth and password lifecycle flow

```text
login(identifier, password)
  -> load user document by username/email/id
  -> read user.auth_type
     -> coyote3: verify local password hash
     -> ldap:    verify via LDAP bind/auth
  -> on success: issue session (includes auth_type, must_change_password)

admin creates local user
  -> issue one-time invite token
  -> try SMTP delivery
     -> success: user receives setup link
     -> fail/no SMTP: API returns warning + setup_url for manual share

forgot password (local user)
  -> issue one-time reset token
  -> same SMTP/fallback behavior as invite
```

TODO:
- Add LDAP/IdP-native self-service password change integration endpoint/UI where supported by center policy.
- Harden email delivery with center-approved SMTP/API provider configuration and monitoring.

## Internal routes

- Ingest routes under `/api/v1/internal/ingest/*` use authenticated user session + RBAC (admin-level for collection/bootstrap operations).
- Selected infrastructure/internal metadata routes still use internal token gate.
- All internal routes should remain network-restricted.

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
