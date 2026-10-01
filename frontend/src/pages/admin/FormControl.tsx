import { UserUiSettingsControls } from "@/components/users/UserUiSettingsControls"
import { accentColor } from "@/lib/badge-colors"
import { cn } from "@/lib/utils"
import { AssayIgvFields } from "@/pages/admin/AssayIgvFields"
import {
  coerceFieldValue,
  defaultForField,
  fieldLabel,
  normalizeList,
  optionLabel,
  optionValue,
  optionsForDependency
} from "@/pages/admin/resource-list"
import type { AdminFormMode, FormField } from "@/pages/admin/resource-specs"
import { CheckboxGroup } from "./CheckboxGroup"
import { ObjectFieldEditor } from "./ObjectFieldEditor"
import { readFormPath, writeFormPath } from "./form-paths"

export function StructuredObjectField({
  field,
  value,
  onChange,
  disabled,
  formValues,
}: {
  field: FormField
  value: any
  onChange: (next: Record<string, any>) => void
  disabled?: boolean
  formValues?: Record<string, any>
}) {
  const objectValue = value && typeof value === "object" && !Array.isArray(value) ? value : {}
  const selectedAnalyses = new Set(normalizeList(formValues?.analysis_types).map((item) => item.toUpperCase()))
  const selectedIntents = new Set(normalizeList(formValues?.analysis_intents || ["somatic"]).map((item) => item.toLowerCase()))
  const isFilter = field.display_type === "filters-structured"
  const visibleGroups = (field.groups || []).filter((group: any) => (
    (!group.requires_analysis || normalizeList(group.requires_analysis).some((item) => selectedAnalyses.has(item.toUpperCase())))
    && (!group.requires_intent || normalizeList(group.requires_intent).some((item) => selectedIntents.has(item.toLowerCase())))
  ))
  const groupedFilters = new Map<string, NonNullable<FormField["groups"]>[number]>()
  if (isFilter) {
    for (const group of visibleGroups) {
      const category = group.category || group.title
      const existing = groupedFilters.get(category)
      if (existing) existing.fields.push(...group.fields)
      else groupedFilters.set(category, { title: category, fields: [...group.fields] })
    }
  }
  const displayGroups = isFilter ? [...groupedFilters.values()] : visibleGroups
  return (
    <div className={isFilter ? "min-w-0 space-y-4" : "space-y-3 rounded-lg border border-border bg-background/60 p-3"}>
      {isFilter && !visibleGroups.length && <p role="status" className="p-4 type-body text-muted-foreground">No filter groups apply to the selected analyses and intents.</p>}
      {displayGroups.map((group) => (
        <fieldset key={group.title} aria-label={group.title} className={isFilter ? "min-w-0 overflow-hidden rounded-lg border border-border bg-background shadow-sm" : "min-w-0 space-y-2"}>
          <h4 className={isFilter ? "border-l-4 border-primary bg-muted px-3 py-2 type-label font-semibold text-foreground" : "text-xs font-semibold uppercase text-muted-foreground"}>{group.title}</h4>
          <div className={isFilter ? "grid gap-4 p-4 md:grid-cols-2 xl:grid-cols-6" : "grid gap-3 md:grid-cols-2 xl:grid-cols-3"}>
            {group.fields.filter((nested: any) => (
              (!nested.requires_analysis || normalizeList(nested.requires_analysis).some((item) => selectedAnalyses.has(item.toUpperCase())))
              && (!nested.requires_intent || normalizeList(nested.requires_intent).some((item) => selectedIntents.has(item.toLowerCase())))
            )).map((nested) => {
              const nestedField: FormField = {
                ...nested,
                display_type:
                  nested.type === "checkbox-group"
                    ? "checkbox-group"
                    : nested.type === "checkbox"
                      ? "checkbox"
                      : nested.type === "select"
                        ? "select"
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
                <div key={nested.key} className={isFilter ? (nested.type === "checkbox-group" ? "min-w-0 xl:col-span-3" : "min-w-0 xl:col-span-2") : "min-w-0"}>
                <FormControl
                  key={nested.key}
                  name={nested.key}
                  field={nestedField}
                  value={readFormPath(objectValue, nested.key) ?? nested.default ?? defaultForField(nestedField)}
                  mode="edit"
                  onChange={(nextValue) => {
                    const coerced = coerceFieldValue(nestedField, nextValue)
                    onChange(writeFormPath(
                      objectValue,
                      nested.key,
                      coerced === undefined && nextValue === "" ? "" : coerced,
                    ))
                  }}
                  disabled={disabled}
                  compact
                  formValues={formValues}
                />
                </div>
              )
            })}
          </div>
        </fieldset>
      ))}
    </div>
  )
}

export function FormControl({
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
  const readOnly = disabled || mode === "view" || field.readonly || Boolean(field.derive_from) || field.readonly_mode?.includes(mode)
  if (mode === "create" && field.derive_from) {
    const parts = field.derive_from.map((key) =>
      String(formValues?.[key] || (key === "subpanel_id" ? "base" : "")).trim().toLowerCase(),
    )
    value = parts.every(Boolean) ? parts.join("_") : ""
  }
  const label = fieldLabel(name, field)
  const newIdentifier = mode === "create" && !readOnly && !field.options && (!field.display_type || field.display_type === "input") && ["asp_id", "isgl_id"].includes(name)
  const identifierError = newIdentifier && Boolean(value) && !/^[a-z0-9]+(?:_[a-z0-9]+)*$/.test(String(value))
  const commonClass = "w-full rounded-lg border border-input bg-background px-2 py-1.5 text-sm outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-60"

  if (field.display_type === "user-settings") {
    return (
      <div className={cn("space-y-1", compact ? "text-xs" : "text-sm")}>
        <span className="flex items-center gap-1 font-semibold uppercase tracking-wide text-muted-foreground">
          {label}
        </span>
        <UserUiSettingsControls value={value} onChange={onChange} disabled={readOnly} />
        {field.help && <span className="block text-xs font-normal normal-case tracking-normal text-muted-foreground">{field.help}</span>}
      </div>
    )
  }

  if (field.display_type === "igv-config") {
    return <fieldset className="space-y-2">
      <legend className="type-label">{label}</legend>
      <AssayIgvFields value={value} onChange={onChange} disabled={readOnly} />
    </fieldset>
  }

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
    const dependentOptions = optionsForDependency(field, formValues)
    const options = dependentOptions ?? field.options ?? []
    control = (
      <select value={String(value ?? "")} disabled={readOnly || (field.options_by_field !== undefined && !options.length)} onChange={(event) => onChange(event.target.value)} className={commonClass}>
        <option value="">{field.options_by_field && !options.length ? "Not applicable" : "Select..."}</option>
        {options.map((option) => {
          const value = optionValue(option)
          return <option key={value} value={value}>{optionLabel(option) || value}</option>
        })}
      </select>
    )
  } else if (field.display_type === "checkbox-group" || field.display_type === "multi-select") {
    control = <CheckboxGroup field={field} value={value} onChange={onChange} disabled={readOnly} formValues={formValues} />
  } else if (field.display_type === "filters-structured" || field.display_type === "reporting-structured" || field.display_type === "catalog-structured") {
    control = <StructuredObjectField field={field} value={value} onChange={onChange} disabled={readOnly} formValues={formValues} />
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
  } else if (field.display_type === "color") {
    const textValue = String(value ?? "")
    const pickerValue = /^#[0-9a-f]{6}$/i.test(textValue) ? textValue : "#64748b"
    control = (
      <div className="flex min-h-9 items-center gap-2 rounded-lg border border-input bg-background px-2 py-1 focus-within:ring-2 focus-within:ring-primary/30">
        <input
          type="color"
          aria-label={`${label} picker`}
          value={pickerValue}
          onChange={(event) => onChange(event.target.value.toLowerCase())}
          disabled={readOnly}
          className="h-7 w-10 cursor-pointer rounded-md border border-border bg-transparent p-0.5 disabled:cursor-not-allowed disabled:opacity-60"
        />
        <input
          type="text"
          aria-label={`${label} hex value`}
          value={textValue}
          onChange={(event) => onChange(event.target.value)}
          disabled={readOnly}
          placeholder={field.placeholder || "#4f46e5"}
          pattern="#[0-9A-Fa-f]{6}"
          className="min-w-0 flex-1 border-0 bg-transparent px-1 py-1 text-sm outline-none disabled:opacity-60"
        />
        <span
          aria-hidden="true"
          className="h-5 w-5 rounded-full border border-border"
          style={{ backgroundColor: accentColor(textValue || pickerValue) }}
        />
      </div>
    )
  } else {
    control = readOnly && name === "email" && value ? (
      <a href={`mailto:${String(value)}`} className="link-text block rounded-lg border border-input bg-background px-2 py-1.5 text-sm font-semibold">
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
        pattern={newIdentifier ? "[a-z0-9]+(?:_[a-z0-9]+)*" : undefined}
        aria-label={newIdentifier ? label : undefined}
        aria-invalid={identifierError || undefined}
        className={cn(commonClass, identifierError && "border-destructive")}
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
      {newIdentifier && <span className={cn("block text-xs font-normal normal-case tracking-normal", identifierError ? "text-destructive" : "text-muted-foreground")}>Use lowercase letters and digits with single underscores between words.</span>}
      {field.help && <span className="block text-xs font-normal normal-case tracking-normal text-muted-foreground">{field.help}</span>}
    </label>
  )
}
