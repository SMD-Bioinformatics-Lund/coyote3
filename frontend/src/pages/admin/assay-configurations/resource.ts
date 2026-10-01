import type { ResourceListFilter } from "../resource-list"
import type { AdminResourceSpec } from "../resource-specs"

export const resource: AdminResourceSpec = {
  key: "aspc",
  title: "Assay Configurations",
  description: "Manage environment-specific assay configs, defaults, and filters.",
  endpoint: "/resources/aspc",
  listKey: "assay_configs",
  idKeys: ["aspc_id", "assay_id", "_id"],
  canToggle: true,
  canDelete: true,
  permissions: {
    list: "assay.config:list",
    view: "assay.config:view",
    create: "assay.config:create",
    edit: "assay.config:edit",
    delete: "assay.config:delete",
  },
}

export const columns = ["aspc_id", "asp_id", "subpanel_id", "environment", "asp_category", "analysis_types", "is_active", "version", "updated_on"]

export const filters: ResourceListFilter[] = [
  { field: "asp_category", label: "Assay category", allLabel: "All assay categories" },
  { field: "asp_group", label: "Assay group", allLabel: "All assay groups" },
  { field: "asp_id", label: "Assay", allLabel: "All assays" },
]
