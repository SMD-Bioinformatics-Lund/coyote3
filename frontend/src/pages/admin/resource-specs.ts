export type AdminFormMode = "create" | "edit" | "view"

export type AdminResourceSpec = {
  key: string
  title: string
  description: string
  endpoint: string
  listKey: string
  idKeys: string[]
  searchParam?: string
  canToggle?: boolean
  canDelete?: boolean
  permissions: {
    list: string
    view: string
    create: string
    edit: string
    delete: string
  }
}

export type FormField = {
  label?: string
  data_type?: string
  display_type?: string
  required?: boolean
  readonly?: boolean
  readonly_mode?: string[]
  hidden_mode?: string[]
  placeholder?: string
  help?: string
  options?: any[]
  options_by_field?: {
    field: string
    values: Record<string, any[]>
  }
  conditional_options?: {
    field: string
    truthy?: any[]
    falsy?: any[]
  }
  default?: any
  groups?: Array<{
    title: string
    requires_analysis?: string[]
    requires_intent?: string[]
    fields: Array<FormField & {
      key: string
      type?: string
      requires_analysis?: string[]
      requires_intent?: string[]
    }>
  }>
}

export type FormSpec = {
  fields: Record<string, FormField>
  sections?: Record<string, string[]>
}

export const specs: Record<string, AdminResourceSpec> = {
  users: {
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
  },
  roles: {
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
  },
  permissions: {
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
  },
  asp: {
    key: "asp",
    title: "Assay Panels",
    description: "Manage assay panel definitions and panel-level metadata.",
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
  },
  aspc: {
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
  },
  genelists: {
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
  },
  samples: {
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
  },
}

export const actionLabels = {
  toggle: "status updated",
  delete: "deleted",
  invite: "invite sent",
} as const
