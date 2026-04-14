# Security Model

## Layers

1. Authentication (session/login)
2. Authorization (role + permission checks)
3. Internal token gate for selected system-to-system routes
4. Environment secret hardening (prod/dev strict behavior)

For the detailed runtime model of how roles, permissions, environments,
assay groups, assays, and `superuser` visibility work together, see
[user_scope_and_visibility.md](user_scope_and_visibility.md).

## User permissions

Permission checks use the `resource:action[:scope]` naming convention (see
`docs/developer/permissions_naming.md` for the full inventory and naming rules).

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

### Dual-layer enforcement

Authorization is enforced at two layers with **different** semantics:

#### API layer — disjunctive OR (`require_access`)

The FastAPI `require_access` dependency grants access if **any** criterion is met:
a permission match, an access-level gate, or a role gate. Superusers bypass all
checks via an early return.

```python
@router.patch("/.../flags/false-positive")
def mark_false_variant(
    user: ApiUser = Depends(require_access(permission="snv:manage", min_role="admin")),
):
    # Authorized if user has "snv:manage" OR has admin role
```

#### UI layer — conjunctive AND (`has_access`)

The Jinja `has_access()` helper requires **all** specified criteria to be satisfied
before showing a UI element:

```jinja2
{% if has_access(permission="report:create", min_role="admin") %}
    <button>Create Report</button>
{% endif %}
```

This means:
- API routes use OR so that permissions can grant access independently of role level.
- UI elements use AND so that a button only appears when the user has both the
  permission and the required role.
- `superuser` is the only unrestricted runtime role and bypasses permission and assay-scope checks.
- `admin` is not unrestricted; it remains subject to assigned permissions and normal scope handling.

## Bootstrap superuser rule

- First-time deployment creates a single bootstrap `superuser`.
- `scripts/bootstrap_local_admin.py` refuses to create another `superuser` if one already exists.
- Additional superusers must be created by an authenticated existing superuser through the normal management flow.

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
- Never rely on unauthenticated DB in shared/non-local environments
