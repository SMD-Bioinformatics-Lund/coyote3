import type { ResourceListFilter } from "../resource-list"
import type { AdminResourceSpec } from "../resource-specs"

export const resource: AdminResourceSpec = {
  key: "samples",
  title: "Admin Samples",
  description: "Developer-level sample resource management and deletion workflows.",
  endpoint: "/resources/samples",
  listKey: "samples",
  idKeys: ["_id", "name", "sample_id"],
  searchParam: "search",
  canDelete: true,
  permissions: {
    list: "sample:list:global",
    view: "sample:view:global",
    create: "internal.ingest:manage",
    edit: "sample:edit:global",
    delete: "sample:delete:global",
  },
}

export const columns = [
  "name",
  "case_id",
  "case_clarity_id",
  "control_id",
  "control_clarity_id",
  "asp_group",
  "asp_id",
  "subpanel_id",
  "environment",
  "omics_layer",
  "paired",
  "ingest_status",
  "reported",
  "time_added",
]

export const filters: ResourceListFilter[] = [
  { field: "asp_group", label: "Assay group", allLabel: "All assay groups" },
  { field: "asp_id", label: "Assay", allLabel: "All assays" },
]
