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

Access control is enforced at two layers with different semantics:

### API Layer (`require_access` — disjunctive OR)

The FastAPI `require_access` dependency uses **OR** logic: the user is authorized if
**any** of the specified criteria are met.  Superusers bypass all checks via an
early return.

Authorization is granted if **ANY** of the following conditions are met:

1.  **Permission Match**: The user's active permission set includes the exact string required by the route.
2.  **Access Level Gate**: The user's `access_level` meets or exceeds the `min_level` required by the route.
3.  **Role Gate**: The user's `access_level` meets or exceeds the resolved level of the `min_role` required by the route.

```python
# Route: Mark Small Variant False Positive
@router.patch("/api/v1/samples/{sample_id}/small-variants/{var_id}/flags/false-positive")
def mark_false_variant(
    # ...
    user: ApiUser = Depends(require_access(permission="snv:manage", min_role="admin")),
):
    # Authorized if:
    # 1. User has "snv:manage" permission
    # OR
    # 2. User has 'admin' role (Level 99999)
```

### UI Layer (`has_access` — conjunctive AND)

The Jinja template helper `has_access()` uses **AND** logic: the user must satisfy
**all** specified criteria to see/access the UI element.

```jinja2
{# User must BOTH have the permission AND meet the role requirement #}
{% if has_access(permission="report:create", min_role="admin") %}
    <button>Create Report</button>
{% endif %}
```

## Inventory Requirements

*   **Case Sensitivity**: All permission strings are enforced in lowercase.
*   **dot-nesting**: Sub-resources must use dots, never underscores (e.g., `sample.comment:add:global`).
*   **Persistence**: Permissions are managed in the `permissions` collection and mapped to users via the `roles` collection.

## Wildcard Support (Future)

The `resource:action[:scope]` structure is designed to support wildcard resolution (e.g., `sample:*` or `sample:view:*`). While the current implementation requires explicit string matches, all new integrations must adhere to the structured naming to ensure compatibility with future policy-based enforcement (ABAC).
