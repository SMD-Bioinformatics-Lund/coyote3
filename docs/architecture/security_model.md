# Security Model

## Security Flow Diagram

```text
Incoming request
  |
  v
Identify auth mechanism
  |
  +--> session cookie
  +--> bearer token
  +--> internal token
  |
  v
Resolve user / principal
  |
  v
Apply access rules
  |
  +--> role gate
  +--> permission gate
  +--> assay / scope visibility
  |
  v
Allow request or return structured denial
```

## Layers

1. Authentication (session/login)
2. Authorization (role + permission checks)
3. Internal token gate for selected system-to-system routes
4. Environment secret hardening (prod/dev strict behavior)

Roles, permissions, environments, assay groups, assays, and `superuser`
visibility are resolved in the API security layer before request handlers run.

## Package boundaries

Coyote3 keeps security code in two deliberately separate packages:

- `api/security` contains policy and application security behavior. It resolves
  users from sessions or tokens, evaluates route permissions through
  `require_access`, constructs the Casbin-backed RBAC/ABAC policy, issues and
  verifies password-action tokens, and emits security/audit events.
- `api/infra/security` contains storage and runtime infrastructure for security
  concerns. It owns Mongo-backed API session persistence and security index
  creation. It must not contain route permissions, role semantics, or clinical
  authorization decisions.

Route modules should depend on `api.security.access.require_access` or the
thin dependency re-export in `api.app.deps.auth`. They should not query role or
permission collections directly and should not implement local minimum-role
checks. The API remains the authorization source of truth; UI visibility is only
an ergonomic reflection of the session payload.

!!! info
    Keep policy decisions close to `api/security` and persistence details close
    to `api/infra/security`. This makes authorization auditable and keeps
    storage changes from silently changing access behavior.

!!! warning
    Do not add user-level allow/deny overrides or ad-hoc role gates in route
    handlers. A route should declare the required permission id and let the
    Casbin-backed policy decide whether the current user satisfies it.

## Role permissions

Permission checks use the `resource:action[:scope]` naming convention (see
`docs/developer/permissions_naming.md` for the full inventory and naming rules).
User documents do not carry allow/deny permission overrides. Effective
permissions are derived from the assigned roles only.

Role and permission policy edits update the existing document in place. Each
edit increments `version`, appends `version_history`, updates mutation metadata,
and emits an audit event through the normal mutation/audit path. Runtime
authorization resolves the single current role or permission document by
`role_id` or `permission_id`. MongoDB enforces one document per `role_id` and
one document per `permission_id`.

Role documents may carry a `color` value for UI display. This color is not part
of authorization. It is rendered as a visual accent only; readable foreground
text is controlled by the UI theme so role badges stay accessible in both light
and dark mode.

Clinical configuration resources use a different model: ASP, ASPC, and ISGL
edits rotate active versions so report and interpretation snapshots can be
reconstructed against the exact clinical configuration in force at the time.
That append-only model is intentionally not used for roles and permissions,
because access governance must remain simple to migrate, hydrate into policy,
and query deterministically.

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

### Policy Enforcement

Authorization uses `require_access` with Casbin-backed RBAC and ABAC checks.
Routes declare permission ids, not minimum role or level gates. The assigned
roles decide which permissions a user receives, and optional resource context
applies assay, environment/profile, and assay-group scope. Superusers bypass all
checks via an early return.

```python
@router.patch("/.../flags/false-positive")
def mark_false_variant(
    user: ApiUser = Depends(require_access(permission="snv:manage")),
):
    # Authorized if an assigned active role grants "snv:manage"
```

- `superuser` is the only unrestricted runtime role and bypasses permission and assay-scope checks.
- `admin` is not unrestricted; it remains subject to assigned permissions and normal scope handling.

## Bootstrap superuser rule

- First-time deployment creates a single bootstrap `superuser`.
- `scripts/bootstrap_local_admin.py` refuses to create another `superuser` if one already exists.
- Additional superusers must be created by an authenticated existing superuser through the normal management flow.

## Authentication providers

- User documents carry `auth_type` as a provider list, for example `["ldap"]` or `["local", "ldap"]`.
- Login flow resolves the provider from the submitted identifier: email login uses LDAP, username login uses local password auth.
- Human center users default to `["ldap"]`. A user may be explicitly configured as `["local", "ldap"]` when the center wants both LDAP login by email and local password login by username.
- Coyote service accounts (`coyote3.admin` and `coyote3.*`) default to `["local"]` and are kept separate from LDAP-only center users.
- Local users (`local`) can use Coyote3-managed password flows:
  - authenticated password change
  - reset/set-password one-time token flows
  - admin invite flow for new local users
  - when SMTP is unavailable, invite/reset still issue one-time setup links and API/UI return warnings so admins can share links manually
- LDAP users authenticate against LDAP and should normally change passwords in the identity provider.

### Auth and password lifecycle flow

```text
login(identifier, password)
  -> identifier contains "@": load by email and require auth_type contains ldap
  -> otherwise: load by username and require auth_type contains local
     -> local: verify local password hash
     -> ldap:  verify via LDAP bind/auth using email
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

## API session transport

The login endpoint `POST /api/v1/auth/sessions` creates an opaque API session
token and stores it in the configured `api_sessions` collection. The response
sets that token as an HTTP-only cookie named by `API_SESSION_COOKIE_NAME`.
The request authentication layer accepts the same token through either:

- the configured API session cookie (`ApiSessionCookie` in OpenAPI), or
- `Authorization: Bearer <token>` (`BearerAuth` in OpenAPI).

This keeps browser sessions and API-only clients on the same audited session
model. See [API Authentication](../api/authentication.md) for command examples
and Swagger behavior.

### Access semantics diagram

```text
API route access (`require_access`)
  -> superuser bypass
   OR all configured checks pass:
      permission match
      assay/environment/group scope

UI visibility
  -> derived from session permissions and resource context
  -> API remains authoritative for all mutations and protected reads
```

### Planned hardening items

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
- Mongo credentials (`MONGO_ROOT_*`, `MONGO_APP_*`)

## Mongo security

- Use dedicated app user with least required role (`readWrite` on target DB)
- Use separate Mongo instances per environment for strict isolation
- Never rely on unauthenticated DB in multi-user or non-local environments

See also:

- [System Relationships](system_relationships.md)
