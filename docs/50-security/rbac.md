# RBAC (Roles & Permissions)

- **Roles** (in `roles` collection) carry a **priority level** and default permissions.
- **Permissions** (in `permissions` collection) are fine‑grained keys (e.g., `config:edit`).
- **User** documents can have additional allowed/denied permissions.

**In code**
- Decorator usage: `@require("permission", min_role="manager", min_level=99)`
- Sample‑scoped access: `@require_sample_access("sample_id")`
- Admin‑only: `@admin_required`

See:
- `coyote/db/roles.py`, `coyote/db/permissions.py`, `coyote/db/users.py`
- `coyote/util/decorators/access.py`
- `coyote/services/auth/decorators.py`
