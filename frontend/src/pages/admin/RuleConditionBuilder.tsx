import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { useEffect, useRef, useState } from "react"
import { icon } from "@/lib/assets"
import type {
  Condition,
  FactDefinition
} from "./clinical-rules-types"
import {
  clinicalConditionTone
} from "./clinical-rules-visuals"
import { newCollectionPredicate, newPredicate, OPERATOR_LABELS, parseValue, predicateFor, valueError, valueText } from "./rule-condition-values"
import { RuleHelp } from "./RuleHelp"

export function ConditionBuilder({
  value,
  facts,
  allFacts = facts,
  onChange,
  onRemove,
  depth = 0,
  controlledValues = {},
  allowCollections = true,
}: {
  value: Condition
  facts: FactDefinition[]
  allFacts?: FactDefinition[]
  onChange: (value: Condition) => void
  onRemove?: () => void
  depth?: number
  controlledValues?: Record<string, string[]>
  allowCollections?: boolean
}) {
  const replaceType = (type: Condition["type"]) => {
    if (type === "predicate") onChange(newPredicate(facts))
    else if (type === "all" || type === "any") onChange({ type, children: [newPredicate(facts)] })
    else if (type === "not") onChange({ type, child: newPredicate(facts) })
    else onChange({ type, collection: "findings", quantifier: "any", where: newCollectionPredicate(allFacts, "findings") })
  }
  return (
    <div className={cn("rounded-r-lg border-l-2 p-3", clinicalConditionTone(value.type), depth > 0 && "mt-2")}>
      <div className="flex flex-wrap items-center gap-2">
        <select className="paper-inset responsive-control-height rounded-lg px-2 text-sm" value={value.type} onChange={(event) => replaceType(event.target.value as Condition["type"])}>
          <option value="predicate">Condition</option>
          <option value="all">Match all</option>
          <option value="any">Match any</option>
          <option value="not">Exclude when</option>
          {allowCollections && <option value="collection_match">Find in collection</option>}
        </select>
        <RuleHelp label="Combine conditions">Condition checks one value. Match all requires every child condition. Match any accepts at least one. Exclude when reverses a condition. Find in collection checks individual findings, selected gene lists or measurements; put related checks inside the same item match.</RuleHelp>
        {onRemove && <Button type="button" variant="ghost" size="icon-sm" title="Remove condition" onClick={onRemove}><icon.trash2 /></Button>}
      </div>
      {value.type === "predicate" && (
        <PredicateEditor value={value} facts={facts} controlledValues={controlledValues} onChange={onChange} />
      )}
      {(value.type === "all" || value.type === "any") && (
        <div className="mt-2 space-y-2">
          {value.children.map((child, index) => (
            <ConditionBuilder
              allowCollections={allowCollections}
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
          <Button type="button" className="clinical-rule-action" data-action="condition" variant="outline" size="sm" onClick={() => onChange({ ...value, children: [...value.children, newPredicate(facts)] })}><icon.plus /> Add condition</Button>
        </div>
      )}
      {value.type === "not" && <ConditionBuilder allowCollections={allowCollections} value={value.child} facts={facts} allFacts={allFacts} depth={depth + 1} controlledValues={controlledValues} onChange={(child) => onChange({ ...value, child })} />}
      {value.type === "collection_match" && (
        <div className="mt-2 space-y-2">
          <div className="grid gap-2 sm:grid-cols-2">
            <label className="type-label">Collection<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={value.collection} onChange={(event) => onChange({ ...value, collection: event.target.value as typeof value.collection, where: newCollectionPredicate(allFacts, event.target.value) })}><option value="findings">Findings</option><option value="hrd">HRD</option><option value="msi">MSI</option><option value="tmb">TMB</option><option value="applied_gene_lists">Applied gene lists</option><option value="tier_summaries">Tier summaries</option></select></label>
            <label className="type-label">Match<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={value.quantifier} onChange={(event) => onChange({ ...value, quantifier: event.target.value as typeof value.quantifier, count: event.target.value === "count" ? value.count || { operator: "gte", value: 1 } : undefined })}><option value="any">At least one</option><option value="none">None</option><option value="all">Every item</option><option value="count">A specific count</option></select></label>
          </div>
          {value.quantifier === "count" && (
            <div className="grid gap-2 sm:grid-cols-[1fr_1fr]">
              <label className="type-label">Comparison<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={value.count?.operator || "gte"} onChange={(event) => onChange({ ...value, count: { operator: event.target.value as NonNullable<typeof value.count>["operator"], value: value.count?.value ?? 1 } })}><option value="eq">Exactly</option><option value="ne">Not equal to</option><option value="gt">More than</option><option value="gte">At least</option><option value="lt">Fewer than</option><option value="lte">At most</option></select></label>
              <label className="type-label">Number<Input className="mt-1" type="number" min={0} value={value.count?.value ?? 1} onChange={(event) => onChange({ ...value, count: { operator: value.count?.operator || "gte", value: Number(event.target.value) } })} /></label>
            </div>
          )}
          <p className="type-body-sm text-muted-foreground">Only items matching the condition below are counted. Changing the collection starts a new item condition.</p>
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
  const configuredOptions = fact?.kind === "boolean" ? ["true", "false"] : controlledValues[value.fact] || fact?.value_options || []
  const options = value.fact.endsWith(".filter_flags") && configuredOptions.length
    ? Array.from(new Set([...configuredOptions, ...(Array.isArray(value.value) ? value.value : [value.value])
      .filter((item): item is string => typeof item === "string" && item !== "")]))
    : configuredOptions
  const error = noValue ? "" : valueError(value.value, value.operator, { ...fact, value_options: options })
  return (
    <div className="mt-2 grid gap-2 lg:grid-cols-[1.2fr_1fr_1.4fr]">
      <select aria-label="Condition fact" className="paper-inset rounded-lg p-2 text-sm" value={value.fact} onChange={(event) => { const selected = facts.find((item) => item.path === event.target.value); onChange(predicateFor(event.target.value, selected?.operators[0] || "eq", selected)) }}>
        {[...new Set(facts.map(item => item.group))].map(group => <optgroup key={group} label={group}>{facts.filter(item => item.group === group).map(item => <option key={item.path} value={item.path}>{item.label}</option>)}</optgroup>)}
      </select>
      <select aria-label="Condition operator" className="paper-inset rounded-lg p-2 text-sm" value={value.operator} onChange={(event) => onChange(predicateFor(value.fact, event.target.value, fact, value.value))}>
        {operators.map((operator) => <option key={operator} value={operator}>{OPERATOR_LABELS[operator] || operator}</option>)}
      </select>
      {!noValue && ((fact?.kind === "boolean" && !["in", "not_in"].includes(value.operator)) || value.operator === "exists" ? (
        <select className="paper-inset rounded-lg p-2 text-sm" value={String(value.value ?? true)} onChange={(event) => onChange({ ...value, value: event.target.value === "true" })}><option value="true">Yes</option><option value="false">No</option></select>
      ) : options.length && value.operator !== "between" ? (
        <select aria-label="Condition value" className="paper-inset rounded-lg p-2 text-sm"
          multiple={["in", "not_in", "overlaps"].includes(value.operator)}
          value={["in", "not_in", "overlaps"].includes(value.operator)
            ? Array.isArray(value.value) ? value.value.map(String) : []
            : String(value.value ?? "")}
          onChange={(event) => onChange({ ...value, value: ["in", "not_in", "overlaps"].includes(value.operator)
            ? Array.from(event.target.selectedOptions, option => fact?.kind === "boolean" ? option.value === "true" : ["integer", "number"].includes(fact?.kind || "") ? Number(option.value) : option.value)
            : event.target.value })}>
          {!["in", "not_in", "overlaps"].includes(value.operator) && <option value="">Select value</option>}
          {options.map((option) => <option key={option} value={option}>{option}</option>)}
        </select>
      ) : (
        <div className="relative"><ConditionTextInput key={`${value.fact}:${value.operator}`} value={value.value} error={error} change={text => { const parsed = parseValue(text, value.operator, fact); onChange({ ...value, value: parsed }); return parsed }} />{fact?.unit && <span className="absolute right-2 top-2 text-xs text-muted-foreground">{fact.unit}</span>}{error && <span className="mt-1 block text-xs text-destructive">{error}</span>}</div>
      ))}
    </div>
  )
}

function ConditionTextInput({ value, error, change }: { value: unknown; error: string; change: (text: string) => unknown }) {
  const [text, setText] = useState(() => valueText(value))
  const previous = useRef(JSON.stringify(value))
  useEffect(() => {
    const incoming = JSON.stringify(value)
    if (incoming !== previous.current) { previous.current = incoming; setText(valueText(value)) }
  }, [value])
  return <Input aria-label="Condition value" aria-invalid={Boolean(error)} title={error || undefined} value={text} onChange={event => {
    setText(event.target.value)
    // The parent receives typed values; the local buffer retains commas while typing.
    previous.current = JSON.stringify(change(event.target.value))
  }} className={cn(error && "border-destructive focus-visible:ring-destructive/30")} />
}
