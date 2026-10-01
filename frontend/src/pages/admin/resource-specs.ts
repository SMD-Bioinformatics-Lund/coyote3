import { resource as aspc } from "./assay-configurations/resource"
import { resource as asp } from "./assays/resource"
import { resource as genelists } from "./gene-lists/resource"
import { resource as permissions } from "./permissions/resource"
import { resource as roles } from "./roles/resource"
import { resource as samples } from "./samples/resource"
import { resource as users } from "./users/resource"

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
  derive_from?: string[]
  readonly_mode?: string[]
  hidden_mode?: string[]
  placeholder?: string
  help?: string
  options?: any[]
  options_from_field?: string
  show_unavailable_options?: boolean
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
    category?: string
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
  asp,
  aspc,
  genelists,
  users,
  roles,
  permissions,
  samples,
}

export const actionLabels = {
  toggle: "status updated",
  delete: "deleted",
  invite: "invite sent",
} as const
