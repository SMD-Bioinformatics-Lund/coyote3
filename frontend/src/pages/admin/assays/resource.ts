import type { ResourceListFilter } from "../resource-list";
import type { AdminResourceSpec } from "../resource-specs";

export const resource: AdminResourceSpec = {
  key: "asp",
  title: "Assays",
  description: "Manage assay definitions and metadata.",
  endpoint: "/resources/asp",
  listKey: "panels",
  idKeys: ["asp_id", "assay_name", "_id"],
  canToggle: true,
  canDelete: true,
  permissions: {
    list: "assay.panel:list",
    view: "assay.panel:view",
    create: "assay.panel:create",
    edit: "assay.panel:edit",
    delete: "assay.panel:delete",
  },
};

export const columns = [
  "asp_id",
  "display_name",
  "asp_category",
  "asp_group",
  "asp_family",
  "platform",
  "covered_genes_count",
  "is_active",
  "version",
  "updated_on",
];

export const filters: ResourceListFilter[] = [
  { field: "asp_category", label: "Assay category", allLabel: "All assay categories" },
  { field: "asp_group", label: "Assay group", allLabel: "All assay groups" },
];
