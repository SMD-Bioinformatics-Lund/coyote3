import { useEffect, useRef, useState } from "react"
import type { ReactNode } from "react"
import { Copy, Plus, Trash2, ArrowUp, ArrowDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { clinicalConditionTone } from "./clinical-rules-visuals"
import { cn } from "@/lib/utils"
import type { QueryCondition, QueryField, QueryConditionCatalog } from "./query-condition-types"
import { newQueryPredicate, isFilterReference } from "./query-condition-types"
const control = "paper-inset w-full rounded-lg border border-input p-2 text-sm"
const textValue = (value: unknown) => Array.isArray(value) ? value.join("\n") : value === null || isFilterReference(value) ? "" : String(value ?? "")

function QueryValue({ condition, field, catalog, onChange }: {
  condition: Extract<QueryCondition, { type: "predicate" }>
  field?: QueryField
  catalog: QueryConditionCatalog
  onChange: (value: unknown) => void
}) {
  const { operator, value } = condition
  const [text, setText] = useState(textValue(value))
  const emitted = useRef(value)
  useEffect(() => {
    if (JSON.stringify(value) !== JSON.stringify(emitted.current)) setText(textValue(value))
    emitted.current = value
  }, [value])
  const list = ["in", "nin", "all", "mod"].includes(operator) || operator.startsWith("bits")
  const numeric = ["number", "integer"].includes(field?.kind ?? "") || operator === "size" || operator === "mod" || operator.startsWith("bits")
  const commaSeparated = field?.value_role === "gene" || numeric || !!field?.filter_references?.length
  const update = (raw: string) => {
    setText(raw)
    const parse = (item: string): unknown => field?.kind === "boolean" && ["true", "false"].includes(item) ? item === "true" : numeric && item.trim() !== "" && Number.isFinite(Number(item)) ? Number(item) : item
    const entries = raw.split(commaSeparated ? /[,\n]/ : /\n/).filter(item => item.trim() !== "").map(item => parse(item.trim()))
    const next = list ? operator === "mod" ? entries : [...new Set(entries)] : parse(raw)
    emitted.current = next
    onChange(next)
  }
  if (operator === "type") return <label className="type-label">BSON type<select className={control} value={String(value)} onChange={event => onChange(event.target.value)}>{catalog.bson_types.map(item => <option key={item}>{item}</option>)}</select></label>
  if (operator === "exists") return <label className="type-label">Value<select className={control} value={String(value)} onChange={event => onChange(event.target.value === "true")}><option value="true">True</option><option value="false">False</option></select></label>
  const references = (field?.filter_references ?? []).filter(ref => ref.kind === "string_list" ? ["in", "nin", "all"].includes(operator) : ["eq", "ne", "gt", "gte", "lt", "lte"].includes(operator))
  const reference = isFilterReference(value) ? value : undefined
  const sourceControl = references.length > 0 && <label className="block type-label">Value source<select aria-label="Condition value source" className={control} value={reference ? "reference" : "manual"} onChange={event => onChange(event.target.value === "reference" ? { source: "sample.filters", key: references[0].key } : list ? [] : numeric ? 0 : "")}><option value="reference">Sample filter reference</option><option value="manual">Enter manually</option></select></label>
  if (reference) return <div className="grid gap-3 md:grid-cols-2">{sourceControl}<label className="block min-w-0 type-label">Sample filter<select aria-label="Sample filter reference" className={control} value={reference.key} onChange={event => onChange({ source: "sample.filters", key: event.target.value })}>{references.map(ref => <option key={ref.key} value={ref.key}>{ref.path}</option>)}</select></label><p className="type-supporting text-muted-foreground md:col-span-2">Resolved from the sample’s active filters at evaluation time. No values are copied.</p></div>
  const values = Array.isArray(value) ? value : [value]
  const error = numeric && value !== null && values.some(item => typeof item !== "number" || !Number.isFinite(item) || ((field?.kind === "integer" || operator === "size" || operator.startsWith("bits") || operator === "mod") && !Number.isInteger(item)))
    ? "Enter valid numbers of the indicated type."
    : list && (!Array.isArray(value) || value.length === 0 || value.length > catalog.max_list_values) ? `Enter 1–${catalog.max_list_values} values, one per line.`
    : operator === "mod" && (values.length !== 2 || values[0] === 0) ? "Enter a nonzero divisor, then the remainder, on separate lines." : ""
  return <div className="grid gap-3 md:grid-cols-2">
    {sourceControl}
    {value !== null && <label className={cn("block min-w-0 type-label", !sourceControl && "md:col-span-2")}>{list ? commaSeparated ? "Values (comma-separated or one per line)" : "Values (one per line)" : "Value"}
      {list ? <textarea aria-label="Condition values" className={control} rows={3} value={text} aria-invalid={!!error} onChange={event => update(event.target.value)} /> : field?.kind === "boolean" ? <select aria-label="Condition value" className={control} value={String(value)} onChange={event => onChange(event.target.value === "true")}><option value="true">True</option><option value="false">False</option></select> : <Input aria-label="Condition value" value={text} aria-invalid={!!error} onChange={event => update(event.target.value)} />}
    </label>}
    {["eq", "ne"].includes(operator) && <label className="flex items-center gap-2 type-label md:col-span-2"><input type="checkbox" checked={value === null} onChange={event => onChange(event.target.checked ? null : field?.kind === "boolean" ? true : numeric ? 0 : "")} />Compare with null</label>}
    {error && <p role="alert" className="text-destructive type-supporting md:col-span-2">{error}</p>}
    <details className="md:col-span-2"><summary className="cursor-pointer type-supporting text-muted-foreground">Value guidance</summary>
    {field?.hint && <p className="text-muted-foreground type-supporting">{field.hint}</p>}
    <p className="text-muted-foreground type-supporting">{operator === "regex" ? "Case-sensitive pattern, up to 200 characters. Use explicit character classes; no shorthand classes, lookarounds, flags or repeated groups. At most one unbounded quantifier." : operator === "mod" ? "Two integers: divisor and remainder." : operator.startsWith("bits") ? "Bit positions from 0 to 63." : `Stored type: ${field?.kind.replaceAll("_", " ") ?? "unknown"}. Values are not automatically converted by MongoDB.`}</p>
    </details>
  </div>
}

export function QueryConditionBuilder({ value, fields, catalog, onChange, depth = 1, prefix = "", actions, caption }: {
  value: QueryCondition; fields: QueryField[]; catalog: QueryConditionCatalog
  onChange: (value: QueryCondition) => void; depth?: number; prefix?: string
  actions?: ReactNode; caption?: string
}) {
  const [fieldSearch, setFieldSearch] = useState("")
  const available = fields.filter(field => !prefix || field.path.startsWith(`${prefix}.`))
  const arrays = available.filter(field => field.kind === "object_list")
  const atLimit = depth >= catalog.max_depth
  const changeType = (type: QueryCondition["type"]) => {
    if (type === value.type) return
    if (type === "predicate") onChange(newQueryPredicate(available))
    else if (type === "not") onChange({ type, child: value })
    else if (type === "elem_match") {
      const field = arrays[0]?.path ?? ""
      onChange({ type, field, condition: newQueryPredicate(fields.filter(item => item.path.startsWith(`${field}.`))) })
    } else onChange({ type, children: "children" in value ? value.children : [value] })
  }
  const nested = (node: QueryCondition, update: (node: QueryCondition) => void, childPrefix = prefix, childActions?: ReactNode, childCaption?: string) => <QueryConditionBuilder value={node} fields={fields} catalog={catalog} onChange={update} depth={depth + 1} prefix={childPrefix} actions={childActions} caption={childCaption} />
  return <div className="min-w-0 overflow-hidden rounded-lg border bg-background">
    <div className={cn("flex flex-wrap items-end gap-3 border-b p-3", clinicalConditionTone(value.type === "nor" ? "not" : value.type === "elem_match" ? "collection_match" : value.type))}>
    <label className="block min-w-0 flex-1 type-label">{caption ?? "Condition logic"}<select aria-label="Condition logic" className={control} value={value.type} onChange={event => changeType(event.target.value as QueryCondition["type"])}>
      <option value="predicate">Field condition</option><option value="all" disabled={atLimit}>AND — match all</option><option value="any" disabled={atLimit}>OR — match any</option><option value="nor" disabled={atLimit}>NOR — match none</option><option value="not" disabled={atLimit}>NOT — invert condition</option><option value="elem_match" disabled={atLimit || !arrays.length}>Match the same array element</option>
    </select></label>
    {actions}
    </div>
    <div className="space-y-3 p-3">
    {value.type === "predicate" && (() => {
      const field = available.find(item => item.path === value.field)
      return <div className="grid items-start gap-4 md:grid-cols-2">
        <div className="min-w-0 space-y-2"><label className="type-label">Field<select aria-label="Condition field" className={control} value={value.field} onChange={event => onChange(newQueryPredicate(available.filter(item => item.path === event.target.value)))}>{available.filter(item => item.path === value.field || `${item.path} ${item.label}`.toLowerCase().includes(fieldSearch.toLowerCase())).map(item => <option key={item.path} value={item.path}>{item.label} ({item.kind.replaceAll("_", " ")})</option>)}</select></label><details><summary className="cursor-pointer type-supporting text-muted-foreground">Search stored field names</summary><Input aria-label="Search condition fields" placeholder="Search stored field names" value={fieldSearch} onChange={event => setFieldSearch(event.target.value)} /></details></div>
        <label className="type-label">Operator<select aria-label="Condition operator" className={control} value={value.operator} onChange={event => {
          const operator = event.target.value
          const next = operator === "exists" ? true : operator === "type" ? "string" : operator === "size" ? 0 : operator === "mod" ? [2, 0] : operator.startsWith("bits") ? [0] : ["in", "nin", "all"].includes(operator) ? [] : operator === "regex" ? "" : field?.kind === "boolean" ? true : ["integer", "number"].includes(field?.kind ?? "") ? 0 : ""
          const reference = isFilterReference(value.value) ? field?.filter_references?.find(ref => ref.key === (value.value as { key: string }).key) : undefined
          const keepReference = reference && (reference.kind === "string_list" ? ["in", "nin", "all"].includes(operator) : ["eq", "ne", "gt", "gte", "lt", "lte"].includes(operator))
          onChange({ ...value, operator, value: keepReference ? value.value : next })
        }}>{field?.operators.map(operator => <option key={operator} value={operator}>{catalog.operators[operator]} (${operator})</option>)}</select></label>
        <div className="min-w-0 border-t pt-3 md:col-span-2"><QueryValue key={`${value.field}:${value.operator}`} condition={value} field={field} catalog={catalog} onChange={next => onChange({ ...value, value: next })} /></div>
      </div>
    })()}
    {"children" in value && <details open className="space-y-3"><summary className="cursor-pointer type-label">{value.children.length} conditions · {value.type === "all" ? "all must match" : value.type === "any" ? "at least one must match" : "none may match"}</summary>
      {value.children.map((child, index) => <div key={index}>
        {nested(child, next => onChange({ ...value, children: value.children.map((item, i) => i === index ? next : item) }), prefix, <div className="flex shrink-0 gap-1">
          <Button type="button" size="icon-sm" variant="ghost" aria-label="Move condition up" disabled={index === 0} onClick={() => { const children = [...value.children]; [children[index - 1], children[index]] = [children[index], children[index - 1]]; onChange({ ...value, children }) }}><ArrowUp /></Button>
          <Button type="button" size="icon-sm" variant="ghost" aria-label="Move condition down" disabled={index === value.children.length - 1} onClick={() => { const children = [...value.children]; [children[index + 1], children[index]] = [children[index], children[index + 1]]; onChange({ ...value, children }) }}><ArrowDown /></Button>
          <Button type="button" size="icon-sm" variant="ghost" aria-label="Duplicate condition" onClick={() => onChange({ ...value, children: [...value.children, structuredClone(child)] })}><Copy /></Button>
          <Button type="button" size="icon-sm" variant="ghost" aria-label="Remove condition" disabled={value.children.length === 1} onClick={() => onChange({ ...value, children: value.children.filter((_, i) => i !== index) })}><Trash2 /></Button>
        </div>, `Condition ${index + 1}`)}
      </div>)}
      <Button type="button" size="sm" variant="outline" disabled={atLimit} onClick={() => onChange({ ...value, children: [...value.children, newQueryPredicate(available)] })}><Plus />Add condition</Button>
    </details>}
    {value.type === "not" && nested(value.child, child => onChange({ ...value, child }))}
    {value.type === "elem_match" && <>
      <label className="block type-label">Array<select aria-label="Condition array" className={control} value={value.field} onChange={event => onChange({ ...value, field: event.target.value, condition: newQueryPredicate(fields.filter(item => item.path.startsWith(`${event.target.value}.`))) })}>{arrays.map(field => <option key={field.path}>{field.path}</option>)}</select></label>
      <p className="text-muted-foreground type-supporting">All conditions inside this block apply to the same array element.</p>
      {nested(value.condition, condition => onChange({ ...value, condition }), value.field)}
    </>}
    </div>
  </div>
}
