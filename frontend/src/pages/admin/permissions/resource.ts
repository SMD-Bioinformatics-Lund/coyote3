import type { ResourceListFilter } from "../resource-list"
import type { AdminResourceSpec } from "../resource-specs"

export const resource: AdminResourceSpec = {
  key: "permissions",
  title: "Permission Policies",
  description: "Manage named permission policies used by role-based access checks.",
  endpoint: "/permissions",
  listKey: "permission_policies",
  idKeys: ["permission_id", "permission_name", "_id"],
  canToggle: true,
  canDelete: true,
  permissions: {
    list: "permission.policy:list",
    view: "permission.policy:view",
    create: "permission.policy:create",
    edit: "permission.policy:edit",
    delete: "permission.policy:delete",
  },
}

export const columns = ["permission_id", "label", "category", "description", "tags", "is_active", "version", "updated_on"]

export const filters: ResourceListFilter[] = [
  { field: "category", label: "Category", allLabel: "All categories" },
]
