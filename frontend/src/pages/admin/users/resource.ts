import type { ResourceListFilter } from "../resource-list"
import type { AdminResourceSpec } from "../resource-specs"

export const resource: AdminResourceSpec = {
  key: "users",
  title: "Users",
  description: "Manage user accounts, roles, status, invites, and access scoping.",
  endpoint: "/users",
  listKey: "users",
  idKeys: ["username", "user_id", "_id"],
  canToggle: true,
  canDelete: true,
  permissions: {
    list: "user:list",
    view: "user:view",
    create: "user:create",
    edit: "user:edit",
    delete: "user:delete",
  },
}

export const columns = ["username", "fullname", "email", "roles", "auth_type", "is_active", "last_login", "updated_on"]

export const filters: ResourceListFilter[] = [
  { field: "roles", label: "Role", allLabel: "All roles" },
  { field: "auth_type", label: "Authentication", allLabel: "All authentication types" },
  { field: "is_active", label: "Status", allLabel: "All statuses" },
]
