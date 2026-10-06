import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import {
  Plus,
  Trash2
} from "lucide-react"
import type {
  Condition,
  FactDefinition
} from "./clinical-rules-types"
import {
  clinicalConditionTone
} from "./clinical-rules-visuals"
import { newPredicate, OPERATOR_LABELS, parseValue, valueError, valueText } from "./rule-condition-values"

export function ConditionBuilder({
  value,
  facts,
  allFacts = facts,
  onChange,
  onRemove,
  depth = 0,
  controlledValues = {},
}: {
  value: Condition
  facts: FactDefinition[]
  allFacts?: FactDefinition[]
  onChange: (value: Condition) => void
  onRemove?: () => void
  depth?: number
  controlledValues?: Record<string, string[]>
}) {
  const replaceType = (type: Condition["type"]) => {
    if (type === "predicate") onChange(newPredicate(facts))
    else if (type === "all" || type === "any") onChange({ type, children: [newPredicate(facts)] })
    else if (type === "not") onChange({ type, child: newPredicate(facts) })
    else onChange({ type, collection: "findings", quantifier: "any", where: newPredicate(facts) })
  }
  return (
    <div className={cn("rounded-r-lg border-l-2 p-3", clinicalConditionTone(value.type), depth > 0 && "mt-2")}>
      <div className="flex flex-wrap items-center gap-2">
        <select className="paper-inset responsive-control-height rounded-lg px-2 text-sm" value={value.type} onChange={(event) => replaceType(event.target.value as Condition["type"])}>
          <option value="predicate">Condition</option>
          <option value="all">Match all</option>
          <option value="any">Match any</option>
          <option value="not">Exclude when</option>
          <option value="collection_match">Find in collection</option>
        </select>
        {onRemove && <Button type="button" variant="ghost" size="icon-sm" title="Remove condition" onClick={onRemove}><Trash2 /></Button>}
      </div>
      {value.type === "predicate" && (
        <PredicateEditor value={value} facts={facts} controlledValues={controlledValues} onChange={onChange} />
      )}
      {(value.type === "all" || value.type === "any") && (
        <div className="mt-2 space-y-2">
          {value.children.map((child, index) => (
            <ConditionBuilder
              key={index}
              value={child}
              facts={facts}
              allFacts={allFacts}
              depth={depth + 1}
              controlledValues={controlledValues}
              onChange={(next) => onChange({ ...value, children: value.children.map((item, childIndex) => childIndex === index ? next : item) })}
              onRemove={value.children.length > 1 ? () => onChange({ ...value, children: value.children.filter((_, childIndex) => childIndex !== index) }) : undefined}
            />
          ))}
          <Button type="button" variant="outline" size="sm" onClick={() => onChange({ ...value, children: [...value.children, newPredicate(facts)] })}><Plus /> Add condition</Button>
        </div>
      )}
      {value.type === "not" && <ConditionBuilder value={value.child} facts={facts} allFacts={allFacts} depth={depth + 1} controlledValues={controlledValues} onChange={(child) => onChange({ ...value, child })} />}
      {value.type === "collection_match" && (
        <div className="mt-2 space-y-2">
          <div className="grid gap-2 sm:grid-cols-2">
            <label className="type-label">Collection<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={value.collection} onChange={(event) => onChange({ ...value, collection: event.target.value as typeof value.collection })}><option value="findings">Findings</option><option value="hrd">HRD</option><option value="msi">MSI</option><option value="tmb">TMB</option><option value="applied_gene_lists">Applied gene lists</option><option value="tier_summaries">Tier summaries</option></select></label>
            <label className="type-label">Match<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={value.quantifier} onChange={(event) => onChange({ ...value, quantifier: event.target.value as typeof value.quantifier })}><option value="any">At least one</option><option value="none">None</option><option value="all">Every item</option><option value="count">A specific count</option></select></label>
          </div>
          {value.quantifier === "count" && (
            <div className="grid gap-2 sm:grid-cols-[1fr_1fr]">
              <label className="type-label">Comparison<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={value.count?.operator || "gte"} onChange={(event) => onChange({ ...value, count: { operator: event.target.value as NonNullable<typeof value.count>["operator"], value: value.count?.value ?? 1 } })}><option value="eq">Exactly</option><option value="ne">Not equal to</option><option value="gt">More than</option><option value="gte">At least</option><option value="lt">Fewer than</option><option value="lte">At most</option></select></label>
              <label className="type-label">Number<Input className="mt-1" type="number" min={0} value={value.count?.value ?? 1} onChange={(event) => onChange({ ...value, count: { operator: value.count?.operator || "gte", value: Number(event.target.value) } })} /></label>
            </div>
          )}
          <ConditionBuilder value={value.where} facts={allFacts.filter((fact) => fact.scopes.includes("each_item"))} allFacts={allFacts} depth={depth + 1} controlledValues={controlledValues} onChange={(where) => onChange({ ...value, where })} />
        </div>
      )}
    </div>
  )
}

export function PredicateEditor({ value, facts, controlledValues, onChange }: { value: Extract<Condition, { type: "predicate" }>; facts: FactDefinition[]; controlledValues: Record<string, string[]>; onChange: (value: Condition) => void }) {
  const fact = facts.find((item) => item.path === value.fact) || facts[0]
  const operators = fact?.operators || ["eq"]
  const noValue = ["is_empty", "is_unknown"].includes(value.operator)
  const options = controlledValues[value.fact] || fact?.value_options || []
  const error = noValue ? "" : valueError(value.value, value.operator, { ...fact, value_options: options })
  return (
    <div className="mt-2 grid gap-2 lg:grid-cols-[1.2fr_1fr_1.4fr]">
      <select className="paper-inset rounded-lg p-2 text-sm" value={value.fact} onChange={(event) => { const selected = facts.find((item) => item.path === event.target.value); onChange({ type: "predicate", fact: event.target.value, operator: selected?.operators[0] || "eq", value: selected?.kind === "boolean" ? true : "" }) }}>
        {facts.map((item) => <option key={item.path} value={item.path}>{item.label}</option>)}
      </select>
      <select className="paper-inset rounded-lg p-2 text-sm" value={value.operator} onChange={(event) => onChange({ ...value, operator: event.target.value })}>
        {operators.map((operator) => <option key={operator} value={operator}>{OPERATOR_LABELS[operator] || operator}</option>)}
      </select>
      {!noValue && (fact?.kind === "boolean" || value.operator === "exists" ? (
        <select className="paper-inset rounded-lg p-2 text-sm" value={String(value.value ?? true)} onChange={(event) => onChange({ ...value, value: event.target.value === "true" })}><option value="true">Yes</option><option value="false">No</option></select>
      ) : options.length && !["in", "not_in", "overlaps", "between"].includes(value.operator) ? (
        <select className="paper-inset rounded-lg p-2 text-sm" value={String(value.value ?? "")} onChange={(event) => onChange({ ...value, value: event.target.value })}>
          <option value="">Select value</option>
          {options.map((option) => <option key={option} value={option}>{option}</option>)}
        </select>
      ) : (
        <div className="relative"><Input aria-label="Condition value" aria-invalid={Boolean(error)} title={error || undefined} value={valueText(value.value)} onChange={(event) => onChange({ ...value, value: parseValue(event.target.value, value.operator, fact) })} className={cn(error && "border-destructive focus-visible:ring-destructive/30")} />{fact?.unit && <span className="absolute right-2 top-2 text-xs text-muted-foreground">{fact.unit}</span>}{error && <span className="mt-1 block text-xs text-destructive">{error}</span>}</div>
      ))}
    </div>
  )
}
