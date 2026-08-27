# Permissions and access control

Coyote3 permissions are exact, data-backed authorization identifiers. Permission definitions are stored in MongoDB, roles grant permissions, and users receive one or more roles. The API makes the authorization decision; the frontend uses the same identifiers to hide actions that the current user cannot perform.

## Permission identifier format

An identifier uses `resource:action[:scope]`.

| Segment | Meaning | Examples |
| --- | --- | --- |
| `resource` | Resource or workflow being protected. Nested resources use a dot. | `sample`, `variant.comment`, `assay.config` |
| `action` | Operation that may be performed. | `view`, `list`, `create`, `edit`, `delete`, `manage` |
| `scope` | Optional ownership or visibility boundary. | `own`, `global` |

Examples:

| Permission | Meaning |
| --- | --- |
| `sample:view` | Open a sample visible within the user's assigned scope. |
| `sample:delete` | Delete a sample and its dependent clinical records. |
| `variant.comment:add:own` | Add a sample-specific variant comment. |
| `variant.comment:add:global` | Add an annotation shared across samples. |
| `assay.config:edit` | Edit an ASPC definition. |

Identifiers are lowercase and matched exactly. There is no wildcard expansion: `sample:*` does not grant `sample:view`. This keeps route behavior and audit records unambiguous.

## Storage and ownership

| Collection | Responsibility |
| --- | --- |
| `permissions` | Defines the available permission identifiers, labels, categories, descriptions, tags, and active state. |
| `roles` | Groups permission identifiers into assignable access profiles. |
| `users` | Assigns roles and assay, assay-group, and environment scope to an account. |

The bootstrap catalog contains every permission required by the shipped API and frontend. It also contains the standard roles used by a new installation. `scripts/bootstrap_database.py` loads these records only when the destination collections are empty. `scripts/sync_rbac_catalog.py` adds newly shipped definitions to an existing installation without replacing center-created roles or removing locally added role grants.

The `system_managed` field records ownership:

| Record | Edit definition | Activate or deactivate | Delete |
| --- | ---: | ---: | ---: |
| System permission | No | Yes | No |
| System role | Yes | Yes | No |
| Center-created permission | Yes | Yes | Yes |
| Center-created role | Yes | Yes | Yes |

Deactivating a system permission makes it unavailable to authorization checks. Do this only after verifying the affected routes in the UI route audit. System records remain protected from deletion so an upgrade can reliably refer to their business identifiers.

The complete shipped inventory is listed in the [system permission catalog](permission_catalog.md).

## Enforcement path

Protected FastAPI routes declare an exact permission through `require_access`:

```python
@router.post("/api/v1/coverage/blacklist/entries")
def create_coverage_blacklist_entry(
    user: ApiUser = Depends(
        require_access(permission="coverage.blacklist:manage")
    ),
):
    ...
```

Authorization follows this order:

1. Resolve the authenticated user's active roles.
2. Resolve active permissions granted by those roles.
3. Require an exact match for the route permission.
4. Apply assay, assay-group, and environment scope when the resource supplies that context.
5. Record protected administrative and clinical mutations in the audit log.

The `superuser` role bypasses ordinary permission and resource-scope checks. Authentication, input validation, and audit recording still apply.

Frontend checks improve navigation and prevent unavailable controls from being presented, but they are not a security boundary. A caller cannot gain access by constructing a request manually because the API repeats the authorization check.

## UI route audit

`frontend/src/lib/routes/ui-route-registry.ts` describes each React route, its application area, API dependencies, consumed fields, and expected empty and error states. The Administration > UI route audit page displays that registry.

Automated contract tests verify that:

- every route declared in `frontend/src/App.tsx` has a registry entry;
- registry paths are unique and include page-level metadata;
- concrete API dependencies named by the registry resolve to FastAPI routes.

The registry documents and tests the frontend contract. It does not grant access; each route and endpoint still uses its assigned permission.

## Adding a permission

1. Choose a stable identifier that follows `resource:action[:scope]`.
2. Add it to `api/config/bootstrap/rbac/permissions.seed.ndjson` with a clear label, category, description, and search tags.
3. Require the exact identifier in the API route or application service that owns the operation.
4. Add the identifier to the relevant system role definitions in `roles.seed.ndjson`.
5. Add or update frontend gating for the corresponding route and controls.
6. Update the UI route registry when a page or API dependency changes.
7. Regenerate the permission reference and run RBAC, route-contract, and frontend tests.

A permission inserted only into MongoDB has no effect until application code requires that identifier. Conversely, code must not require an identifier that is absent from the shipped catalog.

Generate the reference after changing the catalog:

```bash
.venv/bin/python scripts/export_permissions_reference.py
```
