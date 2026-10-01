import type { ResourceListFilter } from "../resource-list"
import type { AdminResourceSpec } from "../resource-specs"

export const resource: AdminResourceSpec = {
  key: "genelists",
  title: "Gene Lists",
  description: "Manage in-silico gene lists and assay-specific gene selection.",
  endpoint: "/resources/genelists",
  listKey: "genelists",
  idKeys: ["isgl_id", "genelist_id", "_id", "name"],
  canToggle: true,
  canDelete: true,
  permissions: {
    list: "gene_list.insilico:list",
    view: "gene_list.insilico:view",
    create: "gene_list.insilico:create",
    edit: "gene_list.insilico:edit",
    delete: "gene_list.insilico:delete",
  },
}

export const columns = ["isgl_id", "name", "list_type", "diagnosis", "asp_ids", "asp_groups", "is_public", "is_active", "version", "updated_on"]

export const filters: ResourceListFilter[] = [
  { field: "asp_groups", label: "Assay group", allLabel: "All assay groups" },
  { field: "asp_ids", label: "Assay", allLabel: "All assays" },
]
