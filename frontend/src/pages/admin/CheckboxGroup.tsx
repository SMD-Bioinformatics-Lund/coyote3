import {
  normalizeList,
  optionDescription,
  optionLabel,
  optionValue,
  optionsForDependency
} from "@/pages/admin/resource-list"
import type { FormField } from "@/pages/admin/resource-specs"
import { useEffect, useMemo } from "react"


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
  const availableOptions = useMemo(
    () => field.options_from_field
      ? normalizeList(formValues?.[field.options_from_field])
      : dependentOptions
      ? dependentOptions
      : conditional
        ? (conditionalValue ? conditional.truthy || [] : conditional.falsy || [])
        : field.options || [],
    [conditional, conditionalValue, dependentOptions, field.options, field.options_from_field, formValues],
  )
  const options = field.show_unavailable_options ? field.options || availableOptions : availableOptions
  const allowed = useMemo(
    () => new Set(availableOptions.map(optionValue).filter(Boolean)),
    [availableOptions],
  )
  const visibleSelected = new Set([...selected].filter((item) => allowed.has(item)))
  const hasDependentValue = dependent
    ? normalizeList(formValues?.[dependent.field]).length > 0
    : false

  useEffect(() => {
    if (disabled || (!dependent && !field.options_from_field)) return
    const current = normalizeList(value)
    const next = current.filter((item) => allowed.has(item))
    if (next.length !== current.length) onChange(next)
  }, [allowed, dependent, disabled, field.options_from_field, formValues, onChange, value])
  if (!options.length) {
    if (dependent) {
      return (
        <div className="rounded-lg border border-border bg-muted/40 p-3 text-sm text-muted-foreground">
          {hasDependentValue
            ? "No active options are available for the selected assay."
            : "Select the assay to see the available options."}
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
          <span className="text-xs font-semibold uppercase text-muted-foreground">{visibleSelected.size} selected</span>
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
              <h4 className="text-xs font-semibold uppercase tracking-wide text-foreground">{category}</h4>
              <span className="rounded-full bg-muted px-2 py-0.5 type-meta font-bold leading-5 text-muted-foreground">
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
                      disabled={disabled || !allowed.has(value)}
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
                disabled={disabled || !allowed.has(value)}
                onChange={(event) => {
                  const next = new Set(visibleSelected)
                  if (event.target.checked) next.add(value)
                  else next.delete(value)
                  onChange([...next])
                }}
              />
              <span className="min-w-0">
                <span className="block truncate font-semibold" title={label}>{label}</span>
                {description && <span className="block truncate type-label text-muted-foreground" title={description}>{description}</span>}
              </span>
            </label>
          )
        })}
      </div>
    </div>
  )
}
