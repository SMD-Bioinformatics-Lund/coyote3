// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { UserUiSettingsControls } from "@/components/users/UserUiSettingsControls"
import { AssayAccessEditor } from "@/components/users/AssayAccessEditor"
import { accentColor } from "@/lib/badge-colors"
import { resourceNameHint } from "@/lib/resource-names"
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
import { OrderedCheckboxGroup } from "./OrderedCheckboxGroup"
import { ObjectFieldEditor } from "./ObjectFieldEditor"
import { readFormPath, writeFormPath } from "./form-paths"
import { useId, useState, type ComponentProps } from "react"

/** Retain decimal text when the parent echoes its parsed numeric value. */
function NumericInput({ value, onChange, ...props }: ComponentProps<"input">) {
  const textValue = String(value ?? "")
  const canonical = textValue === "" ? "" : String(Number(textValue))
  const [draft, setDraft] = useState({ canonical, text: textValue })
  if (draft.canonical !== canonical) setDraft({ canonical, text: textValue })
  return <input {...props} value={draft.text} onChange={(event) => {
    const text = event.target.value
    setDraft({ canonical: text === "" ? "" : String(Number(text)), text })
    onChange?.(event)
  }} />
}

/** Keep typed separators visible while passing parsed lists to the form state. */
function ListTextarea({ value, onChange, ...props }: Omit<ComponentProps<"textarea">, "value" | "onChange"> & {
  value: unknown
  onChange: (values: string[]) => void
}) {
  const canonical = normalizeList(value).join("\n")
  const [draft, setDraft] = useState({ canonical, text: canonical })
  if (draft.canonical !== canonical) setDraft({ canonical, text: canonical })
  return <textarea {...props} value={draft.text} onChange={(event) => {
    const text = event.target.value
    const values = normalizeList(text)
    setDraft({ canonical: values.join("\n"), text })
    onChange(values)
  }} />
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
  const selectedAnalyses = new Set(normalizeList(formValues?.analysis_types).map((item) => item.toUpperCase()))
  const selectedIntents = new Set(normalizeList(formValues?.analysis_intents || ["somatic"]).map((item) => item.toLowerCase()))
  const isFilter = field.display_type === "filters-structured"
  const isReporting = field.display_type === "reporting-structured"
  const isCatalog = field.display_type === "catalog-structured"
  const groupId = useId()
  const reportSections = new Set(normalizeList(objectValue.report_sections
    ?? field.groups?.flatMap(group => group.fields).find(item => item.key === "report_sections")?.default))
  const visibleFields = (group: NonNullable<FormField["groups"]>[number]) => group.fields.filter(nested => (
    (!nested.requires_analysis || normalizeList(nested.requires_analysis).some(item => selectedAnalyses.has(item.toUpperCase())))
    && (!nested.requires_intent || normalizeList(nested.requires_intent).some(item => selectedIntents.has(item.toLowerCase())))
    && (!isReporting || !nested.key.startsWith("reportable_tiers.")
      || reportSections.has(nested.key.slice("reportable_tiers.".length)))
  ))
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
  const displayGroups = (isFilter ? [...groupedFilters.values()] : visibleGroups)
    .map(group => ({ ...group, fields: visibleFields(group) }))
    .filter(group => group.fields.length)
  const hasTiers = isReporting && displayGroups.some(group => group.fields.some(nested => nested.key.startsWith("reportable_tiers.")))
  return (
    <div className={isReporting ? "grid min-w-0 gap-2.5 @3xl/report:grid-cols-2" : "min-w-0 space-y-4"}>
      {isFilter && !visibleGroups.length && <p role="status" className="p-4 type-body text-muted-foreground">No filter groups apply to the selected analyses and intents.</p>}
      {displayGroups.map((group, index) => {
        const fields = group.fields
        const ordered = fields.some(nested => nested.display_type === "ordered-checkboxes")
        const panel = isReporting ? cn("min-w-0 rounded-lg border border-border bg-background/50 px-3 py-2.5",
          (ordered || (!hasTiers && fields.some(nested => nested.key === "report_sections"))) && "col-span-full") : undefined
        const controls = (
          <div className={cn(
            isFilter ? "grid gap-4 p-4 md:grid-cols-2 xl:grid-cols-6"
              : "grid grid-cols-[repeat(auto-fit,minmax(min(100%,13rem),1fr))] gap-x-3 gap-y-2",
            ordered && "grid-cols-1 @3xl/report:grid-cols-2",
          )}>
            {fields.map((nested) => {
              const type = nested.type || "text"
              const nestedField: FormField = {
                ...nested,
                display_type: nested.display_type ?? (
                  type === "list" ? "textarea" : ["checkbox-group", "checkbox", "select", "textarea"].includes(type) ? type : "input"
                ),
                data_type: type === "checkbox" ? "bool" : type,
              }
              return (
                <div key={nested.key} className={cn("min-w-0",
                  isFilter && (nested.type === "checkbox-group" ? "xl:col-span-3" : "xl:col-span-2"),
                  ordered && "not-first:border-t not-first:border-border not-first:pt-2 @3xl/report:not-first:border-l @3xl/report:not-first:border-t-0 @3xl/report:not-first:pt-0 @3xl/report:not-first:pl-3",
                )}>
                  <FormControl
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
                    inlineChoices={isReporting || isCatalog}
                    formValues={formValues}
                  />
                </div>
              )
            })}
          </div>
        )
        if (!group.help && fields.length === 1 && (isCatalog || (isReporting && fields[0].type === "checkbox-group"))) {
          return <div key={group.title} className={panel}>{controls}</div>
        }
        const showHelp = group.help && !(ordered && disabled)
        const descriptionId = showHelp ? `${groupId}-${index}` : undefined
        return <fieldset key={group.title} aria-label={group.title} aria-describedby={descriptionId} className={cn("min-w-0", panel, isFilter && "overflow-hidden rounded-lg border border-border bg-background shadow-sm")}>
          <h4 className={isFilter ? "border-l-4 border-primary bg-muted px-3 py-2 type-label font-semibold text-foreground" : "mb-1.5 text-sm font-semibold text-foreground"}>{group.title}</h4>
          {showHelp && <p id={descriptionId} className="mb-2 type-body-sm text-muted-foreground">{group.help}</p>}
          {controls}
        </fieldset>
      })}
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
  hideLabel = false,
  inlineChoices = false,
  formValues,
}: {
  name: string
  field: FormField
  value: any
  mode: AdminFormMode
  onChange: (next: any) => void
  disabled?: boolean
  compact?: boolean
  hideLabel?: boolean
  inlineChoices?: boolean
  formValues?: Record<string, any>
}) {
  const readOnly = disabled || mode === "view" || field.readonly || Boolean(field.derive_from) || field.readonly_mode?.includes(mode)
  const helpId = useId()
  if (mode === "create" && field.derive_from) {
    const parts = field.derive_from.map((key) =>
      String(formValues?.[key] || (key === "diagnosis_id" ? "base" : "")).trim().toLowerCase(),
    )
    value = parts.every(Boolean) ? parts.join(name === "aspc_id" ? "::" : "_") : ""
  }
  const label = fieldLabel(name, field)
  const help = field.help || resourceNameHint(name)
  const newIdentifier = mode === "create" && !readOnly && !field.options && (!field.display_type || field.display_type === "input") && ["asp_id", "isgl_id"].includes(name)
  const identifierError = newIdentifier && Boolean(value) && !/^[a-z0-9]+(?:[-_][a-z0-9]+)*$/.test(String(value))
  const commonClass = "form-control w-full rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-60"
  const structured = ["filters-structured", "reporting-structured", "catalog-structured"].includes(field.display_type || "")
  const jsonEditor = field.display_type === "jsoneditor" || field.display_type === "jsoneditor-or-upload" || field.data_type === "json"
  const grouped = structured || (jsonEditor && !Array.isArray(value)) || ["assay-access", "checkbox-group", "multi-select", "ordered-checkboxes", "color"].includes(field.display_type || "")
  const inlineCheckbox = inlineChoices && field.display_type === "checkbox"

  if (readOnly && inlineChoices && ["input", "select"].includes(field.display_type || "")) {
    const options = optionsForDependency(field, formValues) ?? field.options ?? []
    const option = options.find(item => optionValue(item) === String(value ?? ""))
    return <dl className="min-w-0">
      <dt className="type-meta text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 wrap-anywhere type-body-sm text-foreground">{(option ? optionLabel(option) : String(value ?? "")) || "—"}</dd>
    </dl>
  }

  if (field.display_type === "user-settings") {
    return (
      <div className={cn("space-y-1", compact ? "text-xs" : "text-sm")}>
        <span className="flex items-center gap-1 font-semibold uppercase tracking-wide text-muted-foreground">
          {label}
        </span>
        <UserUiSettingsControls value={value} onChange={onChange} disabled={readOnly} />
        {help && <span className="block text-xs font-normal normal-case tracking-normal text-muted-foreground">{help}</span>}
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
  if (field.display_type === "assay-access") {
    control = <AssayAccessEditor value={value} onChange={onChange} options={field.options}
      environments={field.environment_options || []} disabled={readOnly} />
  } else if (field.display_type === "checkbox") {
    const checked = Boolean(value)
    const checkbox = <input type="checkbox" checked={checked} disabled={readOnly} aria-describedby={help ? helpId : undefined} onChange={(event) => onChange(event.target.checked)} />
    control = inlineCheckbox ? checkbox : (
      <span className="flex min-h-9 items-center gap-2 rounded-lg border border-border bg-background/60 px-2 py-1.5 text-sm">
        {checkbox}
        <span>{checked ? "Enabled" : "Disabled"}</span>
      </span>
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
  } else if (field.display_type === "ordered-checkboxes") {
    control = <OrderedCheckboxGroup options={field.options} value={value} onChange={onChange} disabled={readOnly} />
  } else if (field.display_type === "checkbox-group" || field.display_type === "multi-select") {
    control = <CheckboxGroup field={field} label={label} value={value} onChange={onChange} disabled={readOnly} formValues={formValues} inline={inlineChoices} />
  } else if (structured) {
    control = <StructuredObjectField field={field} value={value} onChange={onChange} disabled={readOnly} formValues={formValues} />
  } else if (jsonEditor) {
    control = Array.isArray(value) ? (
      <ListTextarea
        value={value}
        onChange={onChange}
        disabled={readOnly}
        placeholder="One value per line"
        className="min-h-24 w-full rounded-lg border border-input bg-background p-2 text-xs outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-60"
      />
    ) : (
      <ObjectFieldEditor value={value} onChange={onChange} disabled={readOnly} />
    )
  } else if (field.display_type === "textarea" || field.data_type === "list") {
    control = field.data_type === "list" ? (
      <ListTextarea value={value} onChange={onChange} disabled={readOnly}
        placeholder={field.placeholder} className={cn(commonClass, "min-h-24")} />
    ) : (
      <textarea
        value={Array.isArray(value) ? value.join("\n") : String(value ?? "")}
        onChange={(event) => onChange(event.target.value)}
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
    const InputControl = field.data_type === "int" || field.data_type === "float"
      ? NumericInput : "input"
    control = readOnly && name === "email" && value ? (
      <a href={`mailto:${String(value)}`} className="link-text block rounded-lg border border-input bg-background px-2 py-1.5 text-sm font-semibold">
        {String(value)}
      </a>
    ) : (
      <InputControl
        type={field.display_type === "password" ? "password" : field.data_type === "int" || field.data_type === "float" ? "number" : "text"}
        step={field.step ?? (field.data_type === "int" ? 1 : field.data_type === "float" ? 0.001 : undefined)}
        value={String(value ?? "")}
        onChange={(event) => onChange(event.target.value)}
        disabled={readOnly}
        placeholder={field.placeholder}
        pattern={newIdentifier ? "[a-z0-9]+(?:[-_][a-z0-9]+)*" : undefined}
        aria-label={newIdentifier ? label : undefined}
        aria-describedby={help ? helpId : undefined}
        aria-invalid={identifierError || undefined}
        className={cn(commonClass, identifierError && "border-destructive")}
      />
    )
  }

  const outlined = ["input", "text", "textarea", "select", "password", "email", "number"].includes(field.display_type || "input") && field.data_type !== "json" && !field.groups
  const caption = <>{label}{field.required && !readOnly && <span className="ml-1 text-destructive">*</span>}</>
  return (
    <div className={cn(compact ? "text-xs" : "text-sm",
      field.display_type === "reporting-structured" && "@container/report",
      hideLabel && field.display_type === "catalog-structured" && "flex flex-wrap items-center gap-x-4",
      readOnly && ["reporting-structured", "catalog-structured"].includes(field.display_type || "") && "structured-form-readonly")}>
      {hideLabel && structured ? control : grouped ? (
        <fieldset className="min-w-0" aria-describedby={help ? helpId : undefined}>
          <legend className={cn("mb-1 font-medium text-foreground", inlineChoices && "font-semibold")}>{caption}</legend>
          {control}
        </fieldset>
      ) : inlineCheckbox ? (
        <label className="inline-flex min-h-8 items-center gap-2 type-body-sm font-medium">{control}{caption}</label>
      ) : <label className={cn("block", outlined ? "relative pt-2" : "space-y-1")}>
        <span className={cn("flex items-center gap-1 font-medium", outlined ? "form-field-label absolute left-3 top-0 z-10 px-1 type-meta text-muted-foreground" : "text-foreground")}>
          {caption}
        </span>
        {control}
      </label>}
      {newIdentifier && <span className={cn("block text-xs font-normal normal-case tracking-normal", identifierError ? "text-destructive" : "text-muted-foreground")}>Use lowercase identifiers: hyphens between distinct terms and underscores within an assay name, such as tumwgs-hema or hematology_gmsv1.</span>}
      {help && <span id={helpId} className="mt-1 block text-xs font-normal normal-case tracking-normal text-muted-foreground">{help}</span>}
    </div>
  )
}
