# Provisioning Users & Roles

- Create users in **Admin → Users**.
- Assign a **role** (grants a base access level) and optional **additional permissions**.
- Assay access is defined via the user's `assays` and `assay_groups` fields; sample access checks compare these with the sample's `assay`.

**Modules**
- Roles: `coyote/db/roles.py`
- Permissions: `coyote/db/permissions.py`
- Users: `coyote/db/users.py`
- Access decorators: `coyote/util/decorators/access.py` and `services/auth/decorators.py`
