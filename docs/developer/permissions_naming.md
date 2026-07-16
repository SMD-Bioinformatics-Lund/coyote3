# Permissions Naming and Access Control

Coyote3 utilizes a structured, resource-oriented permission system for all API and UI access control. This model ensures granular security, parseable audit logs, and consistent cross-domain enforcement.

## Structure: `resource:action[:scope]`

Permissions are defined as colon-separated segments following the `resource:action[:scope]` standard.

### Segments

1.  **resource**: The singular, lowercase identifier for the target object. Sub-resources use dot-nesting (e.g., `variant.comment`).
2.  **action**: A standardized verb indicating the requested operation.
3.  **scope** (Optional): The visibility or ownership boundary. Omitted when scope is not applicable.

### Standard Actions (Verbs)

| Action | Professional Definition |
| :--- | :--- |
| `view` | Read-only access to specific resource instances. |
| `list` | Access to collection-level indices and summaries. |
| `create` | Authority to initialize new resource instances. |
| `edit` | Authority to mutate existing resource attributes. |
| `delete` | Authority to permanently remove resource instances. |
| `download` | Access to raw data exports (CSV, VCF, etc.). |
| `manage` | Administrative oversight including flag overrides and state changes. |
| `add` / `remove` | Relationship management (e.g., adding a comment to a variant). |
| `hide` / `unhide` | Visibility control for shared annotations. |

### Standard Scopes

*   **global**: Permission applies to all instances of the resource across the platform.
*   **own**: Permission applies only to instances owned by or associated with the authenticated user.

## Enforcement Logic

Access control is enforced with one route-level model:

### API Layer (`require_access`)

The FastAPI `require_access` dependency accepts a route permission id and checks
it through the Casbin-backed policy generated from active role and permission
documents. Superusers bypass checks via an early return.

Authorization is granted only when the configured checks pass:

1.  **Permission Match**: At least one assigned active role grants the exact permission required by the route.
2.  **Attribute Scope**: When route/resource context is provided, assay, assay group, and environment scope must match the user's assignments.
3.  **Superuser Bypass**: `superuser` bypasses permission and scope checks.

Routes declare permission ids only. Role hierarchy belongs in the role documents
by assigning the appropriate permission set to each role.

```python
@router.post("/api/v1/coverage/blacklist/entries")
def create_coverage_blacklist_entry(
    user: ApiUser = Depends(require_access(permission="coverage.blacklist:manage")),
):
    # Authorized if one assigned active role grants coverage.blacklist:manage.
    # Resource handlers may apply ABAC context for assay/profile/group scope.
```

### UI Layer

React UI components should use the session payload and route/resource metadata to
hide unavailable actions, but the API remains authoritative. UI gating must never
replace route-level enforcement.

## Inventory Requirements

*   **Case Sensitivity**: All permission strings are enforced in lowercase.
*   **dot-nesting**: Sub-resources must use dots, never underscores (e.g., `sample.comment:add:global`).
*   **Persistence**: Permissions are managed in the `permissions` collection and mapped to users via the `roles` collection.
*   **No user overrides**: User documents do not carry permission allow/deny override fields. Assign or update roles instead.
*   **Versioning**: Editing a role or permission updates that document in place, increments `version`, appends `version_history`, and writes an audit event. Active-version rotation is reserved for clinical configuration resources such as ASP, ASPC, and ISGL.

## Wildcard Support (Future)

The `resource:action[:scope]` structure is designed to support wildcard resolution (e.g., `sample:*` or `sample:view:*`). New integrations must adhere to the structured naming so policy-based enforcement (ABAC) remains predictable.
