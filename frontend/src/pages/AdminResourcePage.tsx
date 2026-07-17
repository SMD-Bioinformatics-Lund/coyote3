import { useEffect, useMemo, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Activity, AlertTriangle, Edit, Eye, FileUp, MailPlus, Plus, Power, Save, Search, ShieldCheck, Trash2, X } from "lucide-react"
import { api } from "@/lib/api"
import { DataTable } from "@/components/data-table/DataTable"
import { PageShell } from "@/components/layout/PageShell"
import { ColumnDef } from "@tanstack/react-table"
import { cn } from "@/lib/utils"
import { notifyActionError, notifySuccess } from "@/lib/notifications"

type AdminFormMode = "create" | "edit" | "view"

type AdminResourceSpec = {
  key: string
  title: string
  description: string
  endpoint: string
  listKey: string
  idKeys: string[]
  searchParam?: string
  canToggle?: boolean
  canDelete?: boolean
}

type FormField = {
  label?: string
  data_type?: string
  display_type?: string
  required?: boolean
  readonly?: boolean
  readonly_mode?: string[]
  placeholder?: string
  options?: any[]
  conditional_options?: {
    field: string
    truthy?: any[]
    falsy?: any[]
  }
  default?: any
  groups?: Array<{ title: string; fields: Array<FormField & { key: string; type?: string }> }>
}

type FormSpec = {
  fields: Record<string, FormField>
  sections?: Record<string, string[]>
}

const specs: Record<string, AdminResourceSpec> = {
  users: {
    key: "users",
    title: "Users",
    description: "Manage user accounts, roles, status, invites, and access scoping.",
    endpoint: "/users",
    listKey: "users",
    idKeys: ["username", "user_id", "_id"],
    canToggle: true,
    canDelete: true,
  },
  roles: {
    key: "roles",
    title: "Roles",
    description: "Manage role levels and permission allow/deny policies.",
    endpoint: "/roles",
    listKey: "roles",
    idKeys: ["role_id", "_id", "name"],
    canToggle: true,
    canDelete: true,
  },
  permissions: {
    key: "permissions",
    title: "Permission Policies",
    description: "Manage named permission policies used by role and user access checks.",
    endpoint: "/permissions",
    listKey: "permission_policies",
    idKeys: ["permission_id", "permission_name", "_id"],
    canToggle: true,
    canDelete: true,
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
  },
}

const actionLabels = {
  toggle: "status updated",
  delete: "deleted",
  invite: "invite sent",
} as const

function valueLabel(value: unknown) {
  if (Array.isArray(value)) return value.join(", ")
  if (typeof value === "boolean") return value ? "yes" : "no"
  if (value && typeof value === "object") return JSON.stringify(value)
  return String(value ?? "")
}

function titleize(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase())
}

function formatHumanDate(value: unknown) {
  if (!value) return "-"
  const date = new Date(String(value))
  if (Number.isNaN(date.getTime())) return String(value)
  const now = Date.now()
  const diffMs = now - date.getTime()
  const absMs = Math.abs(diffMs)
  const minute = 60 * 1000
  const hour = 60 * minute
  const day = 24 * hour
  const month = 30 * day
  const year = 365 * day
  const suffix = diffMs >= 0 ? "ago" : "from now"
  if (absMs < minute) return "just now"
  if (absMs < hour) return `${Math.round(absMs / minute)} min ${suffix}`
  if (absMs < day) return `${Math.round(absMs / hour)} h ${suffix}`
  if (absMs < month) return `${Math.round(absMs / day)} d ${suffix}`
  if (absMs < year) return `${Math.round(absMs / month)} mo ${suffix}`
  return `${Math.round(absMs / year)} yr ${suffix}`
}

function compactList(value: unknown, max = 3) {
  const values = normalizeList(value)
  if (!values.length) return "-"
  const visible = values.slice(0, max).join(", ")
  return values.length > max ? `${visible} +${values.length - max}` : visible
}

function activeLabel(value: unknown) {
  return value === false ? "inactive" : "active"
}

const configuredValueClasses: Record<string, string> = {
  local: "border-amber-300 bg-amber-100 text-amber-800 dark:border-amber-500/50 dark:bg-amber-500/15 dark:text-amber-200",
  ldap: "border-sky-300 bg-sky-100 text-sky-800 dark:border-sky-500/50 dark:bg-sky-500/15 dark:text-sky-200",
  dna: "border-indigo-300 bg-indigo-100 text-indigo-800 dark:border-indigo-500/50 dark:bg-indigo-500/15 dark:text-indigo-200",
  rna: "border-rose-300 bg-rose-100 text-rose-800 dark:border-rose-500/50 dark:bg-rose-500/15 dark:text-rose-200",
  production: "border-emerald-300 bg-emerald-100 text-emerald-800 dark:border-emerald-500/50 dark:bg-emerald-500/15 dark:text-emerald-200",
  development: "border-blue-300 bg-blue-100 text-blue-800 dark:border-blue-500/50 dark:bg-blue-500/15 dark:text-blue-200",
  testing: "border-violet-300 bg-violet-100 text-violet-800 dark:border-violet-500/50 dark:bg-violet-500/15 dark:text-violet-200",
  validation: "border-cyan-300 bg-cyan-100 text-cyan-800 dark:border-cyan-500/50 dark:bg-cyan-500/15 dark:text-cyan-200",
  hematology: "border-red-300 bg-red-100 text-red-800 dark:border-red-500/50 dark:bg-red-500/15 dark:text-red-200",
  solid: "border-orange-300 bg-orange-100 text-orange-800 dark:border-orange-500/50 dark:bg-orange-500/15 dark:text-orange-200",
  pgx: "border-fuchsia-300 bg-fuchsia-100 text-fuchsia-800 dark:border-fuchsia-500/50 dark:bg-fuchsia-500/15 dark:text-fuchsia-200",
  tumwgs: "border-purple-300 bg-purple-100 text-purple-800 dark:border-purple-500/50 dark:bg-purple-500/15 dark:text-purple-200",
  wts: "border-pink-300 bg-pink-100 text-pink-800 dark:border-pink-500/50 dark:bg-pink-500/15 dark:text-pink-200",
  myeloid: "border-red-300 bg-red-50 text-red-700 dark:border-red-500/50 dark:bg-red-500/10 dark:text-red-200",
  lymphoid: "border-teal-300 bg-teal-100 text-teal-800 dark:border-teal-500/50 dark:bg-teal-500/15 dark:text-teal-200",
  "panel-dna": "border-indigo-300 bg-indigo-100 text-indigo-800 dark:border-indigo-500/50 dark:bg-indigo-500/15 dark:text-indigo-200",
  "panel-rna": "border-rose-300 bg-rose-100 text-rose-800 dark:border-rose-500/50 dark:bg-rose-500/15 dark:text-rose-200",
  wgs: "border-purple-300 bg-purple-100 text-purple-800 dark:border-purple-500/50 dark:bg-purple-500/15 dark:text-purple-200",
  illumina: "border-blue-300 bg-blue-100 text-blue-800 dark:border-blue-500/50 dark:bg-blue-500/15 dark:text-blue-200",
  pacbio: "border-lime-300 bg-lime-100 text-lime-800 dark:border-lime-500/50 dark:bg-lime-500/15 dark:text-lime-200",
  nanopore: "border-neutral-300 bg-neutral-100 text-neutral-800 dark:border-neutral-500/50 dark:bg-neutral-500/15 dark:text-neutral-200",
  iontorrent: "border-yellow-300 bg-yellow-100 text-yellow-800 dark:border-yellow-500/50 dark:bg-yellow-500/15 dark:text-yellow-200",
  snv: "border-indigo-300 bg-indigo-100 text-indigo-800 dark:border-indigo-500/50 dark:bg-indigo-500/15 dark:text-indigo-200",
  cnv: "border-orange-300 bg-orange-100 text-orange-800 dark:border-orange-500/50 dark:bg-orange-500/15 dark:text-orange-200",
  fusion: "border-rose-300 bg-rose-100 text-rose-800 dark:border-rose-500/50 dark:bg-rose-500/15 dark:text-rose-200",
  expression: "border-pink-300 bg-pink-100 text-pink-800 dark:border-pink-500/50 dark:bg-pink-500/15 dark:text-pink-200",
  adhoc_snv: "border-indigo-300 bg-indigo-50 text-indigo-700 dark:border-indigo-500/50 dark:bg-indigo-500/10 dark:text-indigo-200",
  adhoc_cnv: "border-orange-300 bg-orange-50 text-orange-700 dark:border-orange-500/50 dark:bg-orange-500/10 dark:text-orange-200",
  adhoc_fusion: "border-rose-300 bg-rose-50 text-rose-700 dark:border-rose-500/50 dark:bg-rose-500/10 dark:text-rose-200",
  adhoc_expression: "border-pink-300 bg-pink-50 text-pink-700 dark:border-pink-500/50 dark:bg-pink-500/10 dark:text-pink-200",
  adhoc_pgx: "border-fuchsia-300 bg-fuchsia-50 text-fuchsia-700 dark:border-fuchsia-500/50 dark:bg-fuchsia-500/10 dark:text-fuchsia-200",
  SNV: "border-indigo-300 bg-indigo-100 text-indigo-800 dark:border-indigo-500/50 dark:bg-indigo-500/15 dark:text-indigo-200",
  CNV: "border-orange-300 bg-orange-100 text-orange-800 dark:border-orange-500/50 dark:bg-orange-500/15 dark:text-orange-200",
  TRANSLOCATION: "border-cyan-300 bg-cyan-100 text-cyan-800 dark:border-cyan-500/50 dark:bg-cyan-500/15 dark:text-cyan-200",
  BIOMARKER: "border-emerald-300 bg-emerald-100 text-emerald-800 dark:border-emerald-500/50 dark:bg-emerald-500/15 dark:text-emerald-200",
  CNV_PROFILE: "border-amber-300 bg-amber-100 text-amber-800 dark:border-amber-500/50 dark:bg-amber-500/15 dark:text-amber-200",
  FUSION: "border-rose-300 bg-rose-100 text-rose-800 dark:border-rose-500/50 dark:bg-rose-500/15 dark:text-rose-200",
  TMB: "border-violet-300 bg-violet-100 text-violet-800 dark:border-violet-500/50 dark:bg-violet-500/15 dark:text-violet-200",
  PGX: "border-fuchsia-300 bg-fuchsia-100 text-fuchsia-800 dark:border-fuchsia-500/50 dark:bg-fuchsia-500/15 dark:text-fuchsia-200",
  EXPRESSION: "border-pink-300 bg-pink-100 text-pink-800 dark:border-pink-500/50 dark:bg-pink-500/15 dark:text-pink-200",
  CLASSIFICATION: "border-teal-300 bg-teal-100 text-teal-800 dark:border-teal-500/50 dark:bg-teal-500/15 dark:text-teal-200",
  QC: "border-slate-300 bg-slate-100 text-slate-800 dark:border-slate-500/50 dark:bg-slate-500/15 dark:text-slate-200",
}

const roleFallbackClasses: Record<string, string> = {
  superuser: "border-purple-300 bg-purple-100 text-purple-800 dark:border-purple-500/50 dark:bg-purple-500/15 dark:text-purple-200",
  admin: "border-red-300 bg-red-100 text-red-800 dark:border-red-500/50 dark:bg-red-500/15 dark:text-red-200",
  developer: "border-blue-300 bg-blue-100 text-blue-800 dark:border-blue-500/50 dark:bg-blue-500/15 dark:text-blue-200",
  tester: "border-cyan-300 bg-cyan-100 text-cyan-800 dark:border-cyan-500/50 dark:bg-cyan-500/15 dark:text-cyan-200",
  manager: "border-amber-300 bg-amber-100 text-amber-800 dark:border-amber-500/50 dark:bg-amber-500/15 dark:text-amber-200",
  user: "border-emerald-300 bg-emerald-100 text-emerald-800 dark:border-emerald-500/50 dark:bg-emerald-500/15 dark:text-emerald-200",
  viewer: "border-slate-300 bg-slate-100 text-slate-800 dark:border-slate-500/50 dark:bg-slate-500/15 dark:text-slate-200",
}

const namedAccentColors: Record<string, string> = {
  red: "#dc2626",
  blue: "#2563eb",
  yellow: "#d97706",
  indigo: "#4f46e5",
  green: "#059669",
  purple: "#7c3aed",
  brown: "#92400e",
  gray: "#64748b",
  grey: "#64748b",
}

function accentColor(value: string) {
  return namedAccentColors[value.toLowerCase()] || value
}

function valueBadgeClass(value: string, kind?: string) {
  const exact = configuredValueClasses[value] || configuredValueClasses[value.toLowerCase()] || configuredValueClasses[value.toUpperCase()]
  if (exact) return exact
  if (kind === "role") return roleFallbackClasses[value.toLowerCase()] || "border-primary/20 bg-primary/10 text-primary"
  return "border-border bg-muted/70 text-foreground"
}

function ValueBadge({
  value,
  kind,
  color,
  title,
}: {
  value: string
  kind?: string
  color?: string
  title?: string
}) {
  if (color) {
    const displayColor = accentColor(color)
    return (
      <span
        className="inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-semibold leading-4"
        title={title || value}
        style={{
          borderColor: `color-mix(in srgb, ${displayColor} 45%, transparent)`,
          backgroundColor: `color-mix(in srgb, ${displayColor} 14%, hsl(var(--background)))`,
          color: "hsl(var(--foreground))",
        }}
      >
        <span
          className="h-1.5 w-1.5 rounded-full"
          style={{ backgroundColor: displayColor, boxShadow: `0 0 0 2px color-mix(in srgb, ${displayColor} 18%, transparent)` }}
          aria-hidden="true"
        />
        {value}
      </span>
    )
  }
  return (
    <span className={cn("inline-flex items-center rounded-md border px-2 py-1 text-xs font-semibold leading-4", valueBadgeClass(value, kind))} title={title || value}>
      {value}
    </span>
  )
}

function StatusBadge({ value }: { value: unknown }) {
  const active = value !== false
  return (
    <span className={cn(
      "inline-flex rounded-full border px-2 py-0.5 text-[0.72rem] font-black uppercase leading-5",
      active
        ? "border-pass/40 bg-pass/10 text-pass"
        : "border-muted-foreground/30 bg-muted text-muted-foreground"
    )}>
      {active ? "Active" : "Inactive"}
    </span>
  )
}

function MiniBadges({ values, max = 4, kind, roleColors }: { values: unknown; max?: number; kind?: string; roleColors?: Record<string, string> }) {
  const items = normalizeList(values)
  if (!items.length) return <span className="text-muted-foreground">-</span>
  return (
    <div className="flex max-w-[22rem] flex-wrap gap-1">
      {items.slice(0, max).map((item) => (
        <ValueBadge key={item} value={item} kind={kind} color={kind === "role" ? roleColors?.[item] : undefined} />
      ))}
      {items.length > max && (
        <span className="rounded-full border border-primary/20 bg-primary/10 px-2 py-0.5 text-[0.72rem] font-bold leading-5 text-primary">
          +{items.length - max}
        </span>
      )}
    </div>
  )
}

function rowId(row: any, spec: AdminResourceSpec) {
  for (const key of spec.idKeys) {
    if (row?.[key]) return String(row[key])
  }
  return String(row?._id ?? "")
}

function resourceDocFromContext(context: any, spec: AdminResourceSpec) {
  const keys = {
    users: "user_doc",
    roles: "role",
    permissions: "permission",
    asp: "panel",
    aspc: "assay_config",
    genelists: "genelist",
    samples: "sample",
  } as Record<string, string>
  return context?.[keys[spec.key]] || null
}

function defaultForField(field: FormField) {
  if (field.default !== undefined) return field.default
  if (field.display_type === "checkbox") return false
  if (field.display_type === "checkbox-group" || field.display_type === "multi-select") return []
  if (field.display_type?.includes("structured")) return {}
  if (field.data_type === "json") return {}
  if (field.data_type === "list") return []
  return ""
}

function formStateFromSpec(form: FormSpec | undefined, doc: any) {
  const state: Record<string, any> = {}
  Object.entries(form?.fields || {}).forEach(([key, field]) => {
    state[key] = doc?.[key] !== undefined ? doc[key] : defaultForField(field)
  })
  return state
}

function normalizeList(value: any) {
  if (Array.isArray(value)) return value.map(optionValue).filter(Boolean)
  if (typeof value === "string") {
    return value
      .split(/\n|,/)
      .map((item) => item.trim())
      .filter(Boolean)
  }
  return []
}

function optionValue(option: any) {
  if (option && typeof option === "object") {
    return String(option.value ?? option.id ?? option.key ?? option.permission_id ?? option.role_id ?? option.name ?? "")
  }
  return String(option ?? "")
}

function optionLabel(option: any) {
  if (option && typeof option === "object") {
    return String(option.label ?? option.name ?? option.permission_id ?? option.role_id ?? option.value ?? "")
  }
  return String(option ?? "")
}

function optionDescription(option: any) {
  if (!option || typeof option !== "object") return ""
  return String(option.description ?? option.category ?? "")
}

function coerceFieldValue(field: FormField, value: any) {
  if (field.readonly && value === "") return undefined
  if (field.display_type === "checkbox") return Boolean(value)
  if (field.display_type === "checkbox-group" || field.display_type === "multi-select" || field.data_type === "list") return normalizeList(value)
  if (field.data_type === "int") return value === "" || value === null || value === undefined ? undefined : Number.parseInt(String(value), 10)
  if (field.data_type === "float") return value === "" || value === null || value === undefined ? undefined : Number.parseFloat(String(value))
  return value
}

function submitPayload(form: FormSpec | undefined, values: Record<string, any>, mode: Exclude<AdminFormMode, "view">) {
  const payload: Record<string, any> = {}
  Object.entries(form?.fields || {}).forEach(([key, field]) => {
    if (field.readonly || field.readonly_mode?.includes(mode)) return
    if (field.display_type === "password" && !values[key]) return
    const value = coerceFieldValue(field, values[key])
    if (value !== undefined) payload[key] = value
  })
  return payload
}

function fieldLabel(key: string, field?: FormField) {
  return field?.label || titleize(key)
}

function parseCellValue(value: string) {
  const trimmed = value.trim()
  if (!trimmed) return ""
  if (trimmed === "true") return true
  if (trimmed === "false") return false
  if (!Number.isNaN(Number(trimmed)) && /^-?\d+(\.\d+)?$/.test(trimmed)) return Number(trimmed)
  return trimmed
}

function defaultAdminFields(resourceKey: string) {
  const fields: Record<string, string[]> = {
    users: ["username", "fullname", "email", "roles", "auth_type", "is_active", "last_login", "updated_on"],
    roles: ["role_id", "label", "level", "permissions", "is_active", "version", "updated_on"],
    permissions: ["permission_id", "label", "category", "description", "tags", "is_active", "version", "updated_on"],
    asp: ["asp_id", "display_name", "asp_category", "asp_group", "asp_family", "platform", "is_active", "version", "updated_on"],
    aspc: ["aspc_id", "asp_id", "subpanel_id", "environment", "asp_category", "analysis_types", "is_active", "version", "updated_on"],
    genelists: ["isgl_id", "name", "list_type", "diagnosis", "assays", "assay_groups", "is_public", "is_active", "version", "updated_on"],
    samples: ["name", "case_id", "control_id", "assay", "subpanel", "profile", "ingest_status", "time_added"],
    generic: ["name", "username", "email", "role_id", "permission_id", "asp_id", "aspc_id", "is_active", "updated_on"],
  }
  return fields[resourceKey] || fields.generic
}

function adminFields(resourceKey: string, rows: any[]) {
  const preferred = defaultAdminFields(resourceKey)
  const seen = new Set<string>()
  const hidden = new Set(["_id", "id", "version_history"])
  const rowHas = (key: string) => rows.some((row) => row?.[key] !== undefined)
  const selected = preferred.filter((key) => rowHas(key) && !seen.has(key) && seen.add(key))
  if (selected.length >= 5) return selected
  for (const key of rows.flatMap((row) => Object.keys(row || {}))) {
    if (selected.length >= 8) break
    if (seen.has(key) || hidden.has(key) || key.startsWith("_rev")) continue
    if (rowHas(key)) {
      seen.add(key)
      selected.push(key)
    }
  }
  return selected
}

function adminCell(field: string, row: any, context?: { roleColors?: Record<string, string> }) {
  const value = row?.[field]
  if (["created_on", "updated_on", "last_login", "time_added", "created_at", "updated_at"].includes(field)) {
    return (
      <span className="text-sm font-medium" title={value ? new Date(String(value)).toLocaleString() : ""}>
        {formatHumanDate(value)}
      </span>
    )
  }
  if (field === "is_active") return <StatusBadge value={value} />
  if (field === "email") {
    const email = String(value || "")
    if (!email) return <span className="text-muted-foreground">-</span>
    return (
      <a className="text-sm font-semibold text-primary hover:underline" href={`mailto:${email}`} title={`Email ${email}`}>
        {email}
      </a>
    )
  }
  if (["role_id", "primary_role"].includes(field)) {
    const role = String(value || "")
    return role ? <ValueBadge value={role} kind="role" color={context?.roleColors?.[role] || row?.color} /> : <span className="text-muted-foreground">-</span>
  }
  if (field === "auth_type") {
    return <MiniBadges values={value} kind="auth" max={3} />
  }
  if (field === "roles") {
    return <MiniBadges values={value} kind="role" roleColors={context?.roleColors} max={4} />
  }
  if (["asp_category", "asp_group", "asp_family", "platform", "environment", "profile", "list_type", "subpanel_id"].includes(field)) {
    const label = String(value || "")
    return label ? <ValueBadge value={label} /> : <span className="text-muted-foreground">-</span>
  }
  if (["permissions", "tags", "assays", "assay_groups", "analysis_types"].includes(field)) {
    const kind = field === "assay_groups" ? "assay_group" : field === "analysis_types" ? "analysis" : undefined
    return <MiniBadges values={value} max={field === "permissions" ? 5 : 4} kind={kind} />
  }
  if (typeof value === "boolean") return <StatusBadge value={value} />
  if (value && typeof value === "object") return <span className="text-sm text-muted-foreground">{Array.isArray(value) ? compactList(value) : "Configured"}</span>
  return (
    <span className="block max-w-[24rem] truncate text-sm font-medium" title={valueLabel(value)}>
      {valueLabel(value) || "-"}
    </span>
  )
}

function adminExportValue(field: string, row: any) {
  const value = row?.[field]
  if (["created_on", "updated_on", "last_login", "time_added", "created_at", "updated_at"].includes(field)) return formatHumanDate(value)
  if (field === "is_active") return activeLabel(value)
  if (Array.isArray(value)) return value.join("; ")
  if (value && typeof value === "object") return JSON.stringify(value)
  return valueLabel(value)
}

function CheckboxGroup({
  field,
  value,
  onChange,
  disabled,
  formValues,
}: {
  field: FormField
  value: any
  onChange: (next: any[]) => void
  disabled?: boolean
  formValues?: Record<string, any>
}) {
  const selected = new Set(normalizeList(value))
  const conditional = field.conditional_options
  const conditionalValue = conditional ? Boolean(formValues?.[conditional.field]) : false
  const options = conditional
    ? (conditionalValue ? conditional.truthy || [] : conditional.falsy || [])
    : field.options || []
  const allowed = new Set(options.map(optionValue).filter(Boolean))
  const visibleSelected = new Set([...selected].filter((item) => allowed.has(item)))
  if (!options.length) {
    return (
      <textarea
        value={normalizeList(value).join("\n")}
        onChange={(event) => onChange(normalizeList(event.target.value))}
        disabled={disabled}
        placeholder="One value per line"
        className="min-h-24 w-full rounded-lg border border-input bg-background p-2 text-xs outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-60"
      />
    )
  }
  const groupedOptions = options.reduce((acc, option) => {
    const category = optionDescription(option) || "Options"
    acc[category] = [...(acc[category] || []), option]
    return acc
  }, {} as Record<string, any[]>)
  const hasCategories = Object.keys(groupedOptions).length > 1 || options.some((option) => option && typeof option === "object" && option.category)
  if (hasCategories) {
    return (
      <div className="space-y-3 rounded-xl border border-border bg-background/60 p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-xs font-bold uppercase text-muted-foreground">{visibleSelected.size} selected</span>
          <button
            type="button"
            disabled={disabled || visibleSelected.size === 0}
            onClick={() => onChange([])}
            className="rounded-md border border-border px-2 py-1 text-xs font-semibold hover:bg-muted disabled:opacity-50"
          >
            Clear
          </button>
        </div>
        {(Object.entries(groupedOptions) as Array<[string, any[]]>).map(([category, categoryOptions]) => (
          <section key={category} className="rounded-lg border border-border bg-card/75 p-3">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h4 className="text-xs font-black uppercase tracking-wide text-foreground">{category}</h4>
              <span className="rounded-full bg-muted px-2 py-0.5 text-[0.72rem] font-bold leading-5 text-muted-foreground">
                {categoryOptions.filter((option) => visibleSelected.has(optionValue(option))).length}/{categoryOptions.length}
              </span>
            </div>
            <div className="grid gap-x-4 gap-y-1 sm:grid-cols-2 xl:grid-cols-3">
              {categoryOptions.map((option) => {
                const value = optionValue(option)
                const label = optionLabel(option) || value
                return (
                  <label key={value} className="flex min-w-0 items-center gap-2 rounded px-1.5 py-1 text-xs hover:bg-muted/50" title={value}>
                    <input
                      type="checkbox"
                      checked={visibleSelected.has(value)}
                      disabled={disabled}
                      onChange={(event) => {
                        const next = new Set(visibleSelected)
                        if (event.target.checked) next.add(value)
                        else next.delete(value)
                        onChange([...next])
                      }}
                    />
                    <span className="min-w-0 flex-1 truncate font-semibold">
                      {label}
                    </span>
                  </label>
                )
              })}
            </div>
          </section>
        ))}
      </div>
    )
  }
  return (
    <div className="max-h-56 overflow-auto rounded-lg border border-border bg-background/60 p-2">
      <div className="grid gap-1 sm:grid-cols-2 xl:grid-cols-3">
        {options.map((option) => {
          const value = optionValue(option)
          const label = optionLabel(option) || value
          const description = optionDescription(option)
          return (
            <label key={value} className="flex items-start gap-2 rounded-md px-2 py-1 text-xs hover:bg-muted/60">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={visibleSelected.has(value)}
                disabled={disabled}
                onChange={(event) => {
                  const next = new Set(visibleSelected)
                  if (event.target.checked) next.add(value)
                  else next.delete(value)
                  onChange([...next])
                }}
              />
              <span className="min-w-0">
                <span className="block truncate font-semibold" title={label}>{label}</span>
                {description && <span className="block truncate text-[10px] text-muted-foreground" title={description}>{description}</span>}
              </span>
            </label>
          )
        })}
      </div>
    </div>
  )
}

function ObjectFieldEditor({
  value,
  onChange,
  disabled,
}: {
  value: any
  onChange: (next: Record<string, any>) => void
  disabled?: boolean
}) {
  const objectValue = value && typeof value === "object" && !Array.isArray(value) ? value : {}
  const rows = Object.entries(objectValue)

  const updateKey = (oldKey: string, newKey: string) => {
    const next: Record<string, any> = {}
    rows.forEach(([key, rowValue]) => {
      next[key === oldKey ? newKey : key] = rowValue
    })
    onChange(next)
  }

  return (
    <div className="space-y-2 rounded-lg border border-border bg-background/60 p-2">
      {rows.length === 0 && <p className="text-xs text-muted-foreground">No entries configured.</p>}
      {rows.map(([key, rowValue]) => (
        <div key={key} className="grid gap-2 md:grid-cols-[minmax(0,0.7fr)_minmax(0,1fr)_auto]">
          <input
            value={key}
            disabled={disabled}
            onChange={(event) => updateKey(key, event.target.value)}
            className="rounded-md border border-input bg-background px-2 py-1.5 text-xs outline-none focus:ring-2 focus:ring-primary/30"
            placeholder="Key"
          />
          <input
            value={typeof rowValue === "object" ? JSON.stringify(rowValue) : String(rowValue ?? "")}
            disabled={disabled}
            onChange={(event) => onChange({ ...objectValue, [key]: parseCellValue(event.target.value) })}
            className="rounded-md border border-input bg-background px-2 py-1.5 text-xs outline-none focus:ring-2 focus:ring-primary/30"
            placeholder="Value"
          />
          <button
            type="button"
            disabled={disabled}
            onClick={() => {
              const next = { ...objectValue }
              delete next[key]
              onChange(next)
            }}
            className="rounded-md border border-border p-1.5 text-destructive hover:bg-destructive/10 disabled:opacity-50"
            title="Remove entry"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
      <button
        type="button"
        disabled={disabled}
        onClick={() => onChange({ ...objectValue, [`key_${rows.length + 1}`]: "" })}
        className="rounded-md border border-border px-2 py-1 text-xs font-semibold hover:bg-muted disabled:opacity-50"
      >
        Add entry
      </button>
    </div>
  )
}

function StructuredObjectField({
  field,
  value,
  onChange,
  disabled,
}: {
  field: FormField
  value: any
  onChange: (next: Record<string, any>) => void
  disabled?: boolean
}) {
  const objectValue = value && typeof value === "object" && !Array.isArray(value) ? value : {}
  return (
    <div className="space-y-3 rounded-lg border border-border bg-background/60 p-3">
      {(field.groups || []).map((group) => (
        <div key={group.title} className="space-y-2">
          <h4 className="text-xs font-bold uppercase text-muted-foreground">{group.title}</h4>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {group.fields.map((nested) => {
              const nestedField: FormField = {
                ...nested,
                display_type:
                  nested.type === "checkbox-group"
                    ? "checkbox-group"
                    : nested.type === "checkbox"
                      ? "checkbox"
                      : nested.type === "textarea" || nested.type === "list"
                        ? "textarea"
                        : "input",
                data_type:
                  nested.type === "int"
                    ? "int"
                    : nested.type === "float"
                      ? "float"
                      : nested.type === "checkbox"
                        ? "bool"
                        : nested.type === "list"
                          ? "list"
                          : nested.type,
              }
              return (
                <FormControl
                  key={nested.key}
                  name={nested.key}
                  field={nestedField}
                  value={objectValue[nested.key] ?? nested.default ?? defaultForField(nestedField)}
                  mode="edit"
                  onChange={(nextValue) => onChange({ ...objectValue, [nested.key]: nextValue })}
                  disabled={disabled}
                  compact
                />
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}

function FormControl({
  name,
  field,
  value,
  mode,
  onChange,
  disabled,
  compact = false,
  formValues,
}: {
  name: string
  field: FormField
  value: any
  mode: AdminFormMode
  onChange: (next: any) => void
  disabled?: boolean
  compact?: boolean
  formValues?: Record<string, any>
}) {
  const readOnly = disabled || mode === "view" || field.readonly || field.readonly_mode?.includes(mode)
  const label = fieldLabel(name, field)
  const commonClass = "w-full rounded-lg border border-input bg-background px-2 py-1.5 text-sm outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-60"

  let control
  if (field.display_type === "checkbox") {
    const checked = Boolean(value)
    control = (
      <label className="flex min-h-9 items-center gap-2 rounded-lg border border-border bg-background/60 px-2 py-1.5 text-sm">
        <input type="checkbox" checked={checked} disabled={readOnly} onChange={(event) => onChange(event.target.checked)} />
        <span>{checked ? "Enabled" : "Disabled"}</span>
      </label>
    )
  } else if (field.display_type === "select") {
    control = (
      <select value={String(value ?? "")} disabled={readOnly} onChange={(event) => onChange(event.target.value)} className={commonClass}>
        <option value="">Select...</option>
        {(field.options || []).map((option) => {
          const value = optionValue(option)
          return <option key={value} value={value}>{optionLabel(option) || value}</option>
        })}
      </select>
    )
  } else if (field.display_type === "checkbox-group" || field.display_type === "multi-select") {
    control = <CheckboxGroup field={field} value={value} onChange={onChange} disabled={readOnly} formValues={formValues} />
  } else if (field.display_type === "filters-structured" || field.display_type === "reporting-structured" || field.display_type === "catalog-structured") {
    control = <StructuredObjectField field={field} value={value} onChange={onChange} disabled={readOnly} />
  } else if (field.display_type === "jsoneditor" || field.display_type === "jsoneditor-or-upload" || field.data_type === "json") {
    control = Array.isArray(value) ? (
      <textarea
        value={normalizeList(value).join("\n")}
        onChange={(event) => onChange(normalizeList(event.target.value))}
        disabled={readOnly}
        placeholder="One value per line"
        className="min-h-24 w-full rounded-lg border border-input bg-background p-2 text-xs outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-60"
      />
    ) : (
      <ObjectFieldEditor value={value} onChange={onChange} disabled={readOnly} />
    )
  } else if (field.display_type === "textarea" || field.data_type === "list") {
    control = (
      <textarea
        value={Array.isArray(value) ? value.join("\n") : String(value ?? "")}
        onChange={(event) => onChange(field.data_type === "list" ? normalizeList(event.target.value) : event.target.value)}
        disabled={readOnly}
        placeholder={field.placeholder}
        className={cn(commonClass, "min-h-24")}
      />
    )
  } else {
    control = readOnly && name === "email" && value ? (
      <a href={`mailto:${String(value)}`} className="block rounded-lg border border-input bg-background px-2 py-1.5 text-sm font-semibold text-primary hover:underline">
        {String(value)}
      </a>
    ) : (
      <input
        type={field.display_type === "password" ? "password" : field.data_type === "int" || field.data_type === "float" ? "number" : "text"}
        step={field.data_type === "float" ? "any" : undefined}
        value={String(value ?? "")}
        onChange={(event) => onChange(event.target.value)}
        disabled={readOnly}
        placeholder={field.placeholder}
        className={commonClass}
      />
    )
  }

  return (
    <label className={cn("block space-y-1", compact ? "text-xs" : "text-sm")}>
      <span className="flex items-center gap-1 font-bold uppercase tracking-wide text-muted-foreground">
        {label}
        {field.required && !readOnly && <span className="text-destructive">*</span>}
      </span>
      {control}
    </label>
  )
}

function AdminManagedForm({
  mode,
  spec,
  form,
  values,
  setValues,
  onSave,
  onCancel,
  isSaving,
  error,
}: {
  mode: AdminFormMode
  spec: AdminResourceSpec
  form: FormSpec
  values: Record<string, any>
  setValues: (next: Record<string, any>) => void
  onSave: () => void
  onCancel: () => void
  isSaving: boolean
  error: string
}) {
  const sections = form.sections && Object.keys(form.sections).length ? form.sections : { general: Object.keys(form.fields || {}) }
  return (
    <section className="surface-panel p-4">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-bold">{mode === "create" ? "Create" : mode === "view" ? "View" : "Edit"} {spec.title}</h2>
          <p className="text-sm text-muted-foreground">
            {mode === "view" ? "Read-only view generated from the backend-managed schema contract." : "Form generated from the backend-managed schema contract."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={onCancel} className="rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted">
            Cancel
          </button>
          {mode !== "view" && (
            <button
              type="button"
              onClick={onSave}
              disabled={isSaving}
              className="inline-flex items-center gap-2 rounded-lg bg-pass px-3 py-2 text-sm font-bold text-white disabled:opacity-50"
            >
              {isSaving ? <Activity className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              Save
            </button>
          )}
        </div>
      </div>
      {error && <p className="mb-3 rounded-lg border border-destructive/30 bg-destructive/10 p-2 text-sm text-destructive">{error}</p>}
      <div className="space-y-4">
        {Object.entries(sections).map(([sectionName, names]) => {
          const sectionFields = names.filter((name) => form.fields?.[name])
          if (!sectionFields.length) return null
          return (
            <div key={sectionName} className="rounded-xl border border-border bg-card/70 p-3">
              <h3 className="mb-3 text-sm font-black uppercase tracking-wide text-foreground">{sectionName.replaceAll("_", " ")}</h3>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {sectionFields.map((name) => {
                  const field = form.fields[name]
                  const wide = ["textarea", "checkbox-group", "jsoneditor", "jsoneditor-or-upload", "filters-structured", "reporting-structured", "catalog-structured"].includes(field.display_type || "") || field.data_type === "json"
                  return (
                    <div key={name} className={cn(wide && "md:col-span-2 xl:col-span-3")}>
                      <FormControl
                        name={name}
                        field={field}
                        value={values[name]}
                        mode={mode}
                        onChange={(next) => setValues({ ...values, [name]: next })}
                        formValues={values}
                      />
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}

function PermissionCategoryOverview({ rows }: { rows: any[] }) {
  if (!rows.length) return null
  const grouped = rows.reduce((acc, row) => {
    const category = String(row?.category || "Uncategorized")
    acc[category] = [...(acc[category] || []), row]
    return acc
  }, {} as Record<string, any[]>)
  return (
    <section className="rounded-xl border border-border bg-card p-4 shadow-sm">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-base font-black">Permission Categories</h2>
          <p className="text-sm text-muted-foreground">All loaded policies grouped by category for quick review.</p>
        </div>
        <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-bold text-primary">
          {rows.length} policies
        </span>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        {(Object.entries(grouped) as Array<[string, any[]]>).map(([category, items]) => (
          <section key={category} className="rounded-lg border border-border bg-background/70 p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <h3 className="text-xs font-black uppercase tracking-wide">{category}</h3>
              <span className="rounded-full bg-muted px-2 py-0.5 text-[0.72rem] font-bold leading-5 text-muted-foreground">{items.length}</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {items.map((item) => (
                <Link
                  key={String(item.permission_id || item._id)}
                  to={`/admin/permissions/${encodeURIComponent(String(item.permission_id || item._id))}/edit`}
                  className="rounded-full border border-border bg-card px-2 py-1 text-xs font-semibold leading-4 text-foreground hover:border-primary/40 hover:text-primary"
                  title={item.description || item.label || item.permission_id}
                >
                  {item.permission_id}
                </Link>
              ))}
            </div>
          </section>
        ))}
      </div>
    </section>
  )
}

export function AdminHub() {
  const utilityModules = [
    {
      title: "Audit",
      description: "Review administrative and workflow audit events.",
      href: "/admin/audit",
      icon: ShieldCheck,
    },
    {
      title: "Ingest Workspace",
      description: "Queue validated sample-bundle ingestion and inspect worker task state.",
      href: "/admin/ingest",
      icon: FileUp,
    },
    {
      title: "UI Route Audit",
      description: "Review frontend routes, API dependencies, and consumed payload fields.",
      href: "/admin/ui-routes",
      icon: ShieldCheck,
    },
  ]

  return (
    <PageShell
      eyebrow="Admin"
      title="Admin Settings"
      description="Govern identity, assays, configurations, ingestion, audit events, and platform contracts."
    >
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {Object.values(specs).map((spec) => (
          <Link
            key={spec.key}
            to={`/admin/${spec.key}`}
            className="rounded-xl border border-border bg-card p-4 shadow-sm transition-colors hover:bg-muted/40"
          >
            <h2 className="font-bold">{spec.title}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{spec.description}</p>
          </Link>
        ))}
        {utilityModules.map((module) => (
          <Link
            key={module.href}
            to={module.href}
            className="rounded-xl border border-border bg-card p-4 shadow-sm transition-colors hover:bg-muted/40"
          >
            <div className="mb-2 inline-flex rounded-lg bg-primary/10 p-2 text-primary">
              <module.icon className="h-4 w-4" />
            </div>
            <h2 className="font-bold">{module.title}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{module.description}</p>
          </Link>
        ))}
      </div>
    </PageShell>
  )
}

export function AdminResourcePage() {
  const { resource = "users" } = useParams()
  const spec = specs[resource] ?? specs.users
  const queryClient = useQueryClient()
  const [q, setQ] = useState("")
  const [pendingAction, setPendingAction] = useState<{ action: "toggle" | "delete" | "invite"; id: string } | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-resource", spec.key, q],
    queryFn: () => {
      const params = new URLSearchParams()
      if (q) params.set(spec.searchParam ?? "q", q)
      params.set("per_page", "100")
      return api.get(`${spec.endpoint}?${params.toString()}`).then((res) => res.data)
    },
  })

  const mutate = useMutation({
    mutationFn: ({ action, id }: { action: "toggle" | "delete" | "invite"; id: string }) => {
      if (action === "invite") return api.post(`${spec.endpoint}/${id}/invite`, {})
      if (action === "toggle") return api.patch(`${spec.endpoint}/${id}/status`, {})
      return api.delete(`${spec.endpoint}/${id}`)
    },
    onSuccess: (_result, variables) => {
      queryClient.invalidateQueries({ queryKey: ["admin-resource", spec.key] })
      setPendingAction(null)
      notifySuccess(
        `${spec.title} ${actionLabels[variables.action]}`,
        `${variables.id} was ${actionLabels[variables.action]}.`,
        `Admin ${spec.key}`,
        { type: spec.key, id: variables.id, name: variables.id }
      )
    },
    onError: (error, variables) => {
      notifyActionError(
        `Unable to ${variables.action} ${spec.title.toLowerCase()}`,
        error,
        `Admin ${spec.key}`,
        { type: spec.key, id: variables.id, name: variables.id }
      )
    },
  })

  const rows = useMemo(() => (data?.[spec.listKey] || []) as any[], [data, spec.listKey])
  const fields = useMemo(() => adminFields(spec.key, rows), [spec.key, rows])
  const columns: ColumnDef<any, any>[] = [
    ...fields.map((field): ColumnDef<any, any> => ({
      id: field,
      header: titleize(field),
      accessorFn: (row) => adminExportValue(field, row),
      cell: ({ row }) => adminCell(field, row.original, { roleColors: data?.roles || {} }),
      meta: {
        exportValue: (row: any) => adminExportValue(field, row),
        cellClassName: field === "permissions" ? "min-w-64" : undefined,
      },
    })),
    {
      id: "actions",
      header: "Actions",
      cell: ({ row }) => {
        const id = rowId(row.original, spec)
        return (
          <div className="flex items-center gap-1">
            <Link
              to={`/admin/${spec.key}/${encodeURIComponent(id)}/view`}
              className="rounded-md p-1.5 text-primary hover:bg-primary/10"
              title="View"
            >
              <Eye className="h-4 w-4" />
            </Link>
            <Link
              to={`/admin/${spec.key}/${encodeURIComponent(id)}/edit`}
              className="rounded-md p-1.5 text-panel hover:bg-panel/10"
              title="Edit"
            >
              <Edit className="h-4 w-4" />
            </Link>
            {spec.canToggle && (
              <button
                onClick={() => setPendingAction({ action: "toggle", id })}
                disabled={mutate.isPending}
                className="rounded-md p-1.5 text-validation hover:bg-validation/10"
                title="Toggle active"
              >
                <Power className="h-4 w-4" />
              </button>
            )}
            {spec.key === "users" && (
              <button
                onClick={() => setPendingAction({ action: "invite", id })}
                disabled={mutate.isPending}
                className="rounded-md p-1.5 text-rna hover:bg-rna/10"
                title="Invite user"
              >
                <MailPlus className="h-4 w-4" />
              </button>
            )}
            {spec.canDelete && (
              <button
                onClick={() => setPendingAction({ action: "delete", id })}
                disabled={mutate.isPending}
                className="rounded-md p-1.5 text-destructive hover:bg-destructive/10"
                title="Delete"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            )}
          </div>
        )
      },
    },
  ]

  return (
    <PageShell
      eyebrow="Admin"
      title={spec.title}
      description={spec.description}
      actions={
        <>
          <Link
            to={`/admin/${spec.key}/create`}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-bold text-primary-foreground shadow-sm"
          >
            <Plus className="h-4 w-4" />
            Create
          </Link>
          <Link to="/admin" className="rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted">
            Admin home
          </Link>
        </>
      }
    >
      <div className="rounded-xl border border-border bg-card p-3 shadow-sm">
        <div className="mb-3 flex items-center gap-2">
          <div className="relative w-full max-w-sm">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              value={q}
              onChange={(event) => setQ(event.target.value)}
              placeholder={`Search ${spec.title.toLowerCase()}...`}
              className="w-full rounded-lg border border-input bg-background py-2 pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-primary/40"
            />
          </div>
          <span className="text-xs font-semibold text-muted-foreground">{rows.length} loaded</span>
        </div>

        {isLoading ? (
          <div className="flex justify-center p-10"><Activity className="animate-spin text-muted-foreground" /></div>
        ) : error ? (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
            {error instanceof Error ? error.message : "Unable to load resource"}
          </div>
        ) : (
          <DataTable columns={columns} data={rows} filename={`${spec.key}.csv`} hideSearch />
        )}
      </div>

      {spec.key === "permissions" && <PermissionCategoryOverview rows={rows} />}

      {pendingAction && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-background/80 p-4">
          <section className="w-full max-w-md rounded-2xl border border-border bg-card p-4 shadow-lg">
            <div className="flex items-start gap-3">
              <div className={cn(
                "rounded-xl border p-2",
                pendingAction.action === "delete"
                  ? "border-destructive/30 bg-destructive/10 text-destructive"
                  : "border-primary/30 bg-primary/10 text-primary"
              )}>
                <AlertTriangle className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <h2 className="text-base font-black">Confirm {pendingAction.action}</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  {pendingAction.action === "delete"
                    ? `Delete ${spec.title.toLowerCase()} ${pendingAction.id}? This removes the active resource from the admin workflow.`
                    : `Apply ${pendingAction.action} to ${spec.title.toLowerCase()} ${pendingAction.id}?`}
                </p>
                <div className="mt-4 flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setPendingAction(null)}
                    className="rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    disabled={mutate.isPending}
                    onClick={() => mutate.mutate(pendingAction)}
                    className={cn(
                      "inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-bold text-white disabled:opacity-50",
                      pendingAction.action === "delete" ? "bg-destructive" : "bg-primary"
                    )}
                  >
                    {mutate.isPending ? <Activity className="h-4 w-4 animate-spin" /> : null}
                    Confirm
                  </button>
                </div>
              </div>
            </div>
          </section>
        </div>
      )}
    </PageShell>
  )
}

export function AdminResourceEditorPage({ mode }: { mode: AdminFormMode }) {
  const { resource = "users", id = "" } = useParams()
  const spec = specs[resource] ?? specs.users
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [values, setValues] = useState<Record<string, any>>({})
  const [editorError, setEditorError] = useState("")
  const [aspcCategory, setAspcCategory] = useState<"DNA" | "RNA">("DNA")

  const isSamples = spec.key === "samples"
  const contextQuery = useQuery({
    queryKey: ["admin-resource-context", spec.key, mode, id, aspcCategory],
    enabled: !isSamples,
    retry: false,
    queryFn: () => {
      if (mode === "create") {
        const params = spec.key === "aspc" ? `?category=${aspcCategory}` : ""
        return api.get(`${spec.endpoint}/create_context${params}`).then((res) => res.data)
      }
      return api.get(`${spec.endpoint}/${encodeURIComponent(id)}/context`).then((res) => res.data)
    },
  })

  const form = contextQuery.data?.form as FormSpec | undefined
  const doc = resourceDocFromContext(contextQuery.data, spec)

  useEffect(() => {
    if (!form) return
    setValues(formStateFromSpec(form, mode === "edit" || mode === "view" ? doc : null))
  }, [form, doc, mode])

  const saveMutation = useMutation({
    mutationFn: (payload: any) => {
      const bodyKey = ["asp", "aspc", "genelists"].includes(spec.key) ? "config" : "form_data"
      const body = { [bodyKey]: payload }
      if (mode === "create") return api.post(spec.endpoint, body)
      return api.put(`${spec.endpoint}/${encodeURIComponent(id)}`, body)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-resource", spec.key] })
      const resourceName = String(values.name || values.username || values.email || values.role_id || values.permission_id || values.asp_id || values.aspc_id || values.isgl_id || id || spec.title)
      notifySuccess(
        `${spec.title} ${mode === "create" ? "created" : "updated"}`,
        `${resourceName} was ${mode === "create" ? "created" : "updated"} successfully.`,
        `Admin ${spec.key}`,
        { type: spec.key, id: id || resourceName, name: resourceName }
      )
      navigate(`/admin/${spec.key}`)
    },
    onError: (error) => {
      setEditorError(error instanceof Error ? error.message : "Unable to save resource.")
      notifyActionError(`Unable to save ${spec.title.toLowerCase()}`, error, `Admin ${spec.key}`, {
        type: spec.key,
        id,
        name: String(values.name || values.username || values.email || id || spec.title),
      })
    },
  })

  const title = `${mode === "create" ? "Create" : mode === "view" ? "View" : "Edit"} ${spec.title}`

  return (
    <PageShell
      eyebrow="Admin"
      title={title}
      description={spec.description}
      actions={
        <div className="flex items-center gap-2">
          {mode === "view" && (
            <Link
              to={`/admin/${spec.key}/${encodeURIComponent(id)}/edit`}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-bold text-primary-foreground shadow-sm"
            >
              <Edit className="h-4 w-4" />
              Edit
            </Link>
          )}
          <Link to={`/admin/${spec.key}`} className="rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted">
            Back to list
          </Link>
        </div>
      }
    >
      {isSamples ? (
        <section className="surface-panel p-4">
          <h2 className="text-lg font-bold">Sample Admin Editing</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Sample edits use dedicated sample workflows. This generic admin area supports sample view and delete only.
          </p>
        </section>
      ) : contextQuery.isLoading ? (
        <section className="surface-panel flex justify-center p-10">
          <Activity className="animate-spin text-muted-foreground" />
        </section>
      ) : contextQuery.error || !form ? (
        <section className="surface-panel p-4">
          <h2 className="text-lg font-bold">Unable to load form</h2>
          <p className="mt-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {contextQuery.error instanceof Error ? contextQuery.error.message : "The form schema was not returned by the backend."}
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            A 403 means the backend denied access to this workflow. A 404 means the requested record was not found; for users, reopen edit from the Users table so the username business key is used.
          </p>
        </section>
      ) : (
        <>
          {spec.key === "aspc" && mode === "create" && (
            <div className="surface-panel flex items-center justify-between gap-3 p-3">
              <div>
                <h2 className="text-sm font-bold uppercase">Assay Configuration Type</h2>
                <p className="text-xs text-muted-foreground">Choose the schema before filling the create form.</p>
              </div>
              <div className="inline-flex rounded-lg border border-border bg-background p-1">
                {(["DNA", "RNA"] as const).map((category) => (
                  <button
                    key={category}
                    type="button"
                    onClick={() => setAspcCategory(category)}
                    className={cn("rounded-md px-3 py-1.5 text-sm font-bold", aspcCategory === category ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted")}
                  >
                    {category}
                  </button>
                ))}
              </div>
            </div>
          )}
          <AdminManagedForm
            mode={mode}
            spec={spec}
            form={form}
            values={values}
            setValues={setValues}
            isSaving={saveMutation.isPending}
            error={editorError}
            onCancel={() => navigate(`/admin/${spec.key}`)}
            onSave={() => {
              if (mode === "view") return
              setEditorError("")
              saveMutation.mutate(submitPayload(form, values, mode))
            }}
          />
        </>
      )}
    </PageShell>
  )
}
