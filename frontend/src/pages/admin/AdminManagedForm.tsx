import { cn } from "@/lib/utils"
import {
  normalizeList,
  optionValue,
  optionsForDependency
} from "@/pages/admin/resource-list"
import type { AdminFormMode, AdminResourceSpec, FormSpec } from "@/pages/admin/resource-specs"
import { Activity, Save } from "lucide-react"
import { readFormPath, writeFormPath } from "./form-paths"
import { FormControl } from "./FormControl"

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
    const changed = new Set([name])
    const pending = [name]
    while (pending.length) {
      const changedName = pending.shift()
      Object.entries(form.fields || {}).forEach(([dependentName, dependentField]) => {
        const dependency = dependentField.options_by_field
        if (!dependency || dependency.field !== changedName || changed.has(dependentName)) return
        const allowedOptions = optionsForDependency(dependentField, updated) || []
        const allowed = new Set(allowedOptions.map(optionValue))
        if (["checkbox-group", "multi-select"].includes(dependentField.display_type || "")) {
          updated[dependentName] = normalizeList(updated[dependentName]).filter((item) => allowed.has(item))
        } else {
          const current = String(updated[dependentName] ?? "")
          const defaultValue = String(dependentField.default ?? "")
          updated[dependentName] = allowed.has(current) ? current : allowed.has(defaultValue) ? defaultValue : ""
        }
        changed.add(dependentName)
        pending.push(dependentName)
      })
    }
    Object.entries(form.fields || {}).forEach(([parentName, parentField]) => {
      for (const group of parentField.groups || []) {
        for (const nestedField of group.fields || []) {
          const dependency = nestedField.options_by_field
          if (!dependency || !changed.has(dependency.field)) continue
          const available = optionsForDependency(nestedField, updated) || []
          const parentValue = updated[parentName] && typeof updated[parentName] === "object" ? updated[parentName] : {}
          const currentValue = readFormPath(parentValue, nestedField.key)
          if (["checkbox-group", "multi-select"].includes(nestedField.type || nestedField.display_type || "")) {
            const allowed = new Set(available.map(optionValue))
            updated[parentName] = writeFormPath(parentValue, nestedField.key,
              normalizeList(currentValue).filter((item) => allowed.has(item)))
            continue
          }
          const current = String(currentValue ?? "")
          const selected = available.find((option) => optionValue(option) === current)
            || available.find((option) => optionValue(option) === String(nestedField.default ?? ""))
          updated[parentName] = writeFormPath(parentValue, nestedField.key, selected ? optionValue(selected) : "")
        }
      }
    })
    setValues(updated)
  }
  return (
    <section className="surface-panel p-4">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">{mode === "create" ? "Create" : mode === "view" ? "View" : "Edit"} {spec.title}</h2>
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
              className="inline-flex items-center gap-2 rounded-lg bg-pass px-3 py-2 text-sm font-semibold text-background disabled:opacity-50"
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
          const sectionFields = names.filter((name) => (
            form.fields?.[name] && !form.fields[name].hidden_mode?.includes(mode)
          ))
          if (!sectionFields.length) return null
          return (
            <div key={sectionName} className="rounded-xl border border-border bg-card/70 p-3">
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-foreground">{sectionName.replaceAll("_", " ")}</h3>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {sectionFields.map((name) => {
                  const field = form.fields[name]
                  const wide = ["textarea", "checkbox-group", "jsoneditor", "jsoneditor-or-upload", "filters-structured", "reporting-structured", "catalog-structured", "user-settings"].includes(field.display_type || "") || field.data_type === "json"
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
