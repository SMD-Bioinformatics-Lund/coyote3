import type { ResourceListFilter } from "../resource-list"
import type { AdminResourceSpec } from "../resource-specs"

export const resource: AdminResourceSpec = {
  key: "roles",
  title: "Roles",
  description: "Manage role levels and permission policies.",
  endpoint: "/roles",
  listKey: "roles",
  idKeys: ["role_id", "_id", "name"],
  canToggle: true,
  canDelete: true,
  permissions: {
    list: "role:list",
    view: "role:view",
    create: "role:create",
    edit: "role:edit",
    delete: "role:delete",
  },
}

export const columns = ["role_id", "label", "level", "permissions", "is_active", "version", "updated_on"]

export const filters: ResourceListFilter[] = []
