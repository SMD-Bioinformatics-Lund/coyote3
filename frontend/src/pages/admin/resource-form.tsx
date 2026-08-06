import { Activity, Save, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { accentColor } from "@/lib/badge-colors"
import type { AdminFormMode, AdminResourceSpec, FormField, FormSpec } from "@/pages/admin/resource-specs"
import {
  coerceFieldValue,
  defaultForField,
  fieldLabel,
  normalizeList,
  optionDescription,
  optionLabel,
  optionValue,
  optionsForDependency,
  parseCellValue,
} from "@/pages/admin/resource-list"

export function CheckboxGroup({
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
  const dependent = field.options_by_field
  const dependentOptions = optionsForDependency(field, formValues)
  const options = dependentOptions
    ? dependentOptions
    : conditional
      ? (conditionalValue ? conditional.truthy || [] : conditional.falsy || [])
      : field.options || []
  const allowed = new Set(options.map(optionValue).filter(Boolean))
  const visibleSelected = new Set([...selected].filter((item) => allowed.has(item)))
  if (!options.length) {
    if (dependent) {
      return (
        <div className="rounded-lg border border-border bg-muted/40 p-3 text-sm text-muted-foreground">
          Select the controlling field to see the available options.
        </div>
      )
    }
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

export function ObjectFieldEditor({
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
  const valueAtPath = (source: Record<string, any>, path: string) => path.split(".").reduce<any>((current, key) => (
    current && typeof current === "object" ? current[key] : undefined
  ), source)
  const setAtPath = (source: Record<string, any>, path: string, nextValue: any) => {
    const keys = path.split(".")
    const next = structuredClone(source)
    let target: Record<string, any> = next
    keys.slice(0, -1).forEach((key) => {
      const current = target[key]
      target[key] = current && typeof current === "object" && !Array.isArray(current) ? { ...current } : {}
      target = target[key]
    })
    target[keys[keys.length - 1]] = nextValue
    return next
  }
  const selectedAnalyses = new Set(normalizeList(formValues?.analysis_types).map((item) => item.toUpperCase()))
  const selectedIntents = new Set(normalizeList(formValues?.analysis_intents || ["somatic"]).map((item) => item.toLowerCase()))
  return (
    <div className="space-y-3 rounded-lg border border-border bg-background/60 p-3">
      {(field.groups || []).filter((group: any) => (
        (!group.requires_analysis || normalizeList(group.requires_analysis).some((item) => selectedAnalyses.has(item.toUpperCase())))
        && (!group.requires_intent || normalizeList(group.requires_intent).some((item) => selectedIntents.has(item.toLowerCase())))
      )).map((group) => (
        <div key={group.title} className="space-y-2">
          <h4 className="text-xs font-bold uppercase text-muted-foreground">{group.title}</h4>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
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
                  value={valueAtPath(objectValue, nested.key) ?? nested.default ?? defaultForField(nestedField)}
                  mode="edit"
                  onChange={(nextValue) => {
                    const coerced = coerceFieldValue(nestedField, nextValue)
                    onChange(setAtPath(
                      objectValue,
                      nested.key,
                      coerced === undefined && nextValue === "" ? "" : coerced,
                    ))
                  }}
                  disabled={disabled}
                  compact
                  formValues={formValues}
                />
              )
            })}
          </div>
        </div>
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
      {field.help && <span className="block text-xs font-normal normal-case tracking-normal text-muted-foreground">{field.help}</span>}
    </label>
  )
}

export function AdminManagedForm({
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
  const updateField = (name: string, next: any) => {
    const updated = { ...values, [name]: next }
    Object.entries(form.fields || {}).forEach(([dependentName, dependentField]) => {
      const dependency = dependentField.options_by_field
      if (!dependency || dependency.field !== name) return
      const allowedOptions = optionsForDependency(dependentField, updated) || []
      const allowed = new Set(allowedOptions.map(optionValue))
      if (dependentField.display_type === "checkbox-group") {
        updated[dependentName] = normalizeList(updated[dependentName]).filter((item) => allowed.has(item))
        return
      }
      const current = String(updated[dependentName] ?? "")
      updated[dependentName] = allowed.has(current) ? current : ""
    })
    setValues(updated)
  }
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
                        onChange={(next) => updateField(name, next)}
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
