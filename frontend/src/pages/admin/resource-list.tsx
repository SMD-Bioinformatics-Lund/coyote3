/* eslint-disable react/only-export-components -- shared admin renderers and value helpers are intentionally colocated */
import { TableBadge } from "@/components/ui/table-badge"
import { cn } from "@/lib/utils"
import { accentColor, configuredValueDescription, valueBadgeClass } from "@/lib/badge-colors"
import { fullDateTime, humanRelativeDate, shortCount } from "@/lib/detail-formatters"
import type { AdminResourceSpec, FormField, FormSpec, AdminFormMode } from "@/pages/admin/resource-specs"

export function valueLabel(value: unknown) {
  if (Array.isArray(value)) return value.join(", ")
  if (typeof value === "boolean") return value ? "yes" : "no"
  if (value && typeof value === "object") return JSON.stringify(value)
  return String(value ?? "")
}

export function titleize(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase())
}

export function compactList(value: unknown, max = 3) {
  const values = normalizeList(value)
  if (!values.length) return "-"
  const visible = values.slice(0, max).join(", ")
  return values.length > max ? `${visible} +${values.length - max}` : visible
}

export function activeLabel(value: unknown) {
  return value === false ? "inactive" : "active"
}

export function ValueBadge({
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
      <TableBadge
        title={title || configuredValueDescription(value) || value}
        style={{
          borderColor: `color-mix(in srgb, ${displayColor} 45%, transparent)`,
          backgroundColor: `color-mix(in srgb, ${displayColor} 14%, var(--background))`,
          color: "var(--foreground)",
        }}
      >
        {value}
      </TableBadge>
    )
  }
  return (
    <TableBadge className={valueBadgeClass(value, kind)} title={title || configuredValueDescription(value) || value}>
      {value}
    </TableBadge>
  )
}

export function StatusBadge({ value }: { value: unknown }) {
  const active = value !== false
  return (
    <TableBadge className={cn(
      "rounded-full font-black uppercase",
      active
        ? "border-pass/40 bg-pass/10 text-pass"
        : "border-muted-foreground/30 bg-muted text-muted-foreground"
    )}>
      {active ? "Active" : "Inactive"}
    </TableBadge>
  )
}

export function MiniBadges({ values, max = 4, kind, roleColors }: { values: unknown; max?: number; kind?: string; roleColors?: Record<string, string> }) {
  const items = normalizeList(values)
  if (!items.length) return <span className="text-muted-foreground">-</span>
  return (
    <div className="flex max-w-[22rem] flex-wrap gap-1">
      {items.slice(0, max).map((item) => (
        <ValueBadge key={item} value={item} kind={kind} color={kind === "role" ? roleColors?.[item] : undefined} />
      ))}
      {items.length > max && (
        <TableBadge className="rounded-full border-primary/20 bg-primary/10 text-primary">
          +{items.length - max}
        </TableBadge>
      )}
    </div>
  )
}

export function rowId(row: any, spec: AdminResourceSpec) {
  for (const key of spec.idKeys) {
    if (row?.[key]) return String(row[key])
  }
  return String(row?._id ?? "")
}

export function rowDisplayName(row: any, spec: AdminResourceSpec) {
  const displayKeys = [
    "name",
    "username",
    "email",
    "label",
    "display_name",
    "role_id",
    "permission_id",
    "asp_id",
    "aspc_id",
    "isgl_id",
  ]
  for (const key of displayKeys) {
    if (row?.[key]) return String(row[key])
  }
  return rowId(row, spec) || spec.title
}

export function mutationDisplayName(result: any, fallback: string) {
  const data = result?.data || result || {}
  return String(data?.meta?.sample_name || data?.meta?.resource_name || data?.resource_name || fallback)
}

export function mutationResourceId(result: any, fallback: string) {
  const data = result?.data || result || {}
  return String(data?.meta?.sample_oid || data?.resource_id || fallback)
}

export function resourceDocFromContext(context: any, spec: AdminResourceSpec) {
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

export function defaultForField(field: FormField) {
  if (field.default !== undefined) return field.default
  if (field.display_type === "checkbox") return false
  if (field.display_type === "checkbox-group" || field.display_type === "multi-select") return []
  if (field.display_type?.includes("structured")) return {}
  if (field.data_type === "json") return {}
  if (field.data_type === "list") return []
  return ""
}

export function formStateFromSpec(form: FormSpec | undefined, doc: any) {
  const state: Record<string, any> = {}
  Object.entries(form?.fields || {}).forEach(([key, field]) => {
    state[key] = doc?.[key] !== undefined ? doc[key] : defaultForField(field)
  })
  return state
}

export function normalizeList(value: any) {
  if (Array.isArray(value)) return value.map(optionValue).filter(Boolean)
  if (typeof value === "string") {
    return value
      .split(/\n|,/)
      .map((item) => item.trim())
      .filter(Boolean)
  }
  return []
}

type ResourceListFilter = {
  field: string
  label: string
  allLabel: string
}

export function resourceListFilters(resourceKey: string): ResourceListFilter[] {
  const filters: Record<string, ResourceListFilter[]> = {
    users: [
      { field: "roles", label: "Role", allLabel: "All roles" },
      { field: "auth_type", label: "Authentication", allLabel: "All authentication types" },
      { field: "is_active", label: "Status", allLabel: "All statuses" },
    ],
    permissions: [
      { field: "category", label: "Category", allLabel: "All categories" },
    ],
    asp: [
      { field: "asp_category", label: "ASP category", allLabel: "All ASP categories" },
      { field: "asp_group", label: "Assay group", allLabel: "All assay groups" },
    ],
    aspc: [
      { field: "asp_category", label: "ASP category", allLabel: "All ASP categories" },
      { field: "asp_group", label: "Assay group", allLabel: "All assay groups" },
      { field: "asp_id", label: "Assay panel", allLabel: "All assay panels" },
    ],
    genelists: [
      { field: "asp_groups", label: "Assay group", allLabel: "All assay groups" },
      { field: "asp_ids", label: "Assay panel", allLabel: "All assay panels" },
    ],
    samples: [
      { field: "asp_group", label: "Assay group", allLabel: "All assay groups" },
      { field: "asp_id", label: "Assay", allLabel: "All assays" },
    ],
  }
  return filters[resourceKey] || []
}

export function resourceFilterValues(row: any, field: string) {
  if (field === "is_active") return [row?.is_active === false ? "false" : "true"]
  const value = row?.[field]
  const values = Array.isArray(value) ? value : [value]
  return values.map((item) => String(item ?? "").trim()).filter(Boolean)
}

export function resourceFilterOptionLabel(field: string, value: string) {
  if (field === "is_active") return value === "false" ? "Inactive" : "Active"
  if (field === "auth_type") return titleize(value)
  return value
}

export function rowMatchesResourceFilters(
  row: any,
  definitions: ResourceListFilter[],
  selections: Record<string, string>
) {
  return definitions.every(({ field }) => {
    const selected = selections[field]
    return !selected || resourceFilterValues(row, field).includes(selected)
  })
}

export function optionValue(option: any) {
  if (option && typeof option === "object") {
    return String(option.value ?? option.id ?? option.key ?? option.permission_id ?? option.role_id ?? option.name ?? "")
  }
  return String(option ?? "")
}

export function optionLabel(option: any) {
  if (option && typeof option === "object") {
    return String(option.label ?? option.name ?? option.permission_id ?? option.role_id ?? option.value ?? "")
  }
  return String(option ?? "")
}

export function optionDescription(option: any) {
  if (!option || typeof option !== "object") return ""
  return String(option.description ?? option.category ?? "")
}

export function optionsForDependency(field: FormField, formValues?: Record<string, any>) {
  const dependency = field.options_by_field
  if (!dependency) return null
  const selectedDependencies = normalizeList(formValues?.[dependency.field])
  const options = selectedDependencies.flatMap((value) => dependency.values[value.toLowerCase()] || [])
  const seen = new Set<string>()
  return options.filter((option) => {
    const value = optionValue(option)
    if (!value || seen.has(value)) return false
    seen.add(value)
    return true
  })
}

export function coerceFieldValue(field: FormField, value: any) {
  if (field.readonly && value === "") return undefined
  if (field.display_type === "checkbox") return Boolean(value)
  if (field.display_type === "checkbox-group" || field.display_type === "multi-select" || field.data_type === "list") return normalizeList(value)
  if (field.data_type === "int") return value === "" || value === null || value === undefined ? undefined : Number.parseInt(String(value), 10)
  if (field.data_type === "float") return value === "" || value === null || value === undefined ? undefined : Number.parseFloat(String(value))
  return value
}

export function submitPayload(form: FormSpec | undefined, values: Record<string, any>, mode: Exclude<AdminFormMode, "view">) {
  const payload: Record<string, any> = {}
  Object.entries(form?.fields || {}).forEach(([key, field]) => {
    if (field.readonly || field.readonly_mode?.includes(mode)) return
    if (field.display_type === "password" && !values[key]) return
    const value = coerceFieldValue(field, values[key])
    if (value !== undefined) payload[key] = value
  })
  return payload
}

export function fieldLabel(key: string, field?: FormField) {
  return field?.label || titleize(key)
}

export function parseCellValue(value: string) {
  const trimmed = value.trim()
  if (!trimmed) return ""
  if (trimmed === "true") return true
  if (trimmed === "false") return false
  if (!Number.isNaN(Number(trimmed)) && /^-?\d+(\.\d+)?$/.test(trimmed)) return Number(trimmed)
  return trimmed
}

export function defaultAdminFields(resourceKey: string) {
  const fields: Record<string, string[]> = {
    users: ["username", "fullname", "email", "roles", "auth_type", "is_active", "last_login", "updated_on"],
    roles: ["role_id", "label", "level", "permissions", "is_active", "version", "updated_on"],
    permissions: ["permission_id", "label", "category", "description", "tags", "system_managed", "is_active", "version", "updated_on"],
    asp: ["asp_id", "display_name", "asp_category", "asp_group", "asp_family", "platform", "is_active", "version", "updated_on"],
    aspc: ["aspc_id", "asp_id", "subpanel_id", "environment", "asp_category", "analysis_types", "is_active", "version", "updated_on"],
    genelists: ["isgl_id", "name", "list_type", "diagnosis", "asp_ids", "asp_groups", "is_public", "is_active", "version", "updated_on"],
    samples: [
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
    ],
    generic: ["name", "username", "email", "role_id", "permission_id", "asp_id", "aspc_id", "is_active", "updated_on"],
  }
  return fields[resourceKey] || fields.generic
}

export function adminFields(resourceKey: string, rows: any[]) {
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

export function adminCell(
  field: string,
  row: any,
  context?: { roleColors?: Record<string, string>; primaryIdentifier?: boolean },
) {
  const value = row?.[field]
  if (["created_on", "updated_on", "last_login", "time_added", "created_at", "updated_at"].includes(field)) {
    return (
      <span className="text-sm font-normal" title={fullDateTime(value, "")}>
        {humanRelativeDate(value)}
      </span>
    )
  }
  if (field === "is_active") return <StatusBadge value={value} />
  if (field === "system_managed") {
    return (
      <ValueBadge
        value={value ? "System" : "Custom"}
        kind={value ? "status" : "neutral"}
        title={
          value
            ? "Bundled application permission. Assign it through roles; its definition is read-only."
            : "Center-created permission policy."
        }
      />
    )
  }
  if (field === "paired") {
    return <ValueBadge value={value ? "Paired" : "Unpaired"} kind={value ? "status" : "warning"} />
  }
  if (field === "reported") {
    return <ValueBadge value={value ? "Reported" : "Unreported"} kind={value ? "status" : "warning"} />
  }
  if (field === "data_counts") {
    const counts = value && typeof value === "object" && !Array.isArray(value) ? value : {}
    const numericLabels: Record<string, string> = {
      snvs: "SNV",
      cnvs: "CNV",
      fusions: "Fusion",
      translocations: "Transloc",
    }
    const booleanLabels: Record<string, string> = {
      cov: "Cov",
      coverage: "Coverage",
      biomarkers: "Biomarkers",
      expression: "Expression",
      classification: "Classification",
      qc: "QC",
      rna_expr: "Expr",
      rna_expression: "Expr",
      rna_class: "Class",
      rna_classification: "Class",
      rna_qc: "QC",
      pgx: "PGx",
    }
    const badges = [
      ...Object.entries(numericLabels)
        .filter(([key]) => Number(counts[key] || 0) > 0)
        .map(([key, label]) => `${label} ${shortCount(Number(counts[key]))}`),
      ...Object.entries(booleanLabels)
        .filter(([key]) => counts[key] === true)
        .map(([, label]) => label),
    ]
    return <MiniBadges values={badges} max={6} />
  }
  if (field === "email") {
    const email = String(value || "")
    if (!email) return <span className="text-muted-foreground">-</span>
    return (
      <a className="link-text text-sm font-semibold" href={`mailto:${email}`} title={`Email ${email}`}>
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
  if (field === "list_type") {
    return <MiniBadges values={value} kind="list_type" max={5} />
  }
  if (["asp_category", "asp_group", "asp_family", "platform", "environment", "profile", "subpanel_id", "omics_layer", "ingest_status"].includes(field)) {
    const label = String(value || "")
    return label ? <ValueBadge value={label} /> : <span className="text-muted-foreground">-</span>
  }
  if (["permissions", "tags", "asp_ids", "asp_groups", "analysis_types", "analysis_intents"].includes(field)) {
    const kind = field === "asp_groups" ? "assay_group" : ["analysis_types", "analysis_intents"].includes(field) ? "analysis" : undefined
    return <MiniBadges values={value} max={field === "permissions" ? 5 : 4} kind={kind} />
  }
  if (typeof value === "boolean") return <StatusBadge value={value} />
  if (value && typeof value === "object") return <span className="text-sm text-muted-foreground">{Array.isArray(value) ? compactList(value) : "Configured"}</span>
  return (
    <span
      className={cn(
        "block max-w-[24rem] truncate text-sm",
        context?.primaryIdentifier ? "font-semibold text-foreground" : "font-normal",
      )}
      title={valueLabel(value)}
    >
      {valueLabel(value) || "-"}
    </span>
  )
}

export function adminExportValue(field: string, row: any) {
  const value = row?.[field]
  if (["created_on", "updated_on", "last_login", "time_added", "created_at", "updated_at"].includes(field)) return fullDateTime(value)
  if (field === "is_active") return activeLabel(value)
  if (Array.isArray(value)) return value.join("; ")
  if (value && typeof value === "object") return JSON.stringify(value)
  return valueLabel(value)
}
