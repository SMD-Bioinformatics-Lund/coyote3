import type { QueryCondition } from "./query-condition-types"
import { isFilterReference } from "./query-condition-types"

const operators: Record<string, string> = {
  eq: "Equals", ne: "Does not equal", in: "Is one of", nin: "Is not one of",
  gt: "Greater than", gte: "At least", lt: "Less than", lte: "At most",
  exists: "Field exists", regex: "Matches pattern", all: "Contains all",
  size: "Array size", type: "Stored type",
}

export function QueryConditionSummary({ condition }: { condition: QueryCondition }) {
  if (condition.type === "predicate") {
    const reference = isFilterReference(condition.value)
    const values = Array.isArray(condition.value) ? condition.value : [condition.value]
    return <dl className="grid min-w-0 gap-3 rounded-lg border border-border bg-background p-3 sm:grid-cols-3">
      <div className="min-w-0"><dt className="type-label text-muted-foreground">Field</dt><dd className="mt-1 break-words font-mono type-supporting">{condition.field}</dd></div>
      <div><dt className="type-label text-muted-foreground">Operator</dt><dd className="mt-1 type-supporting">{operators[condition.operator] ?? condition.operator} <span className="text-muted-foreground">(${condition.operator})</span></dd></div>
      <div className="min-w-0"><dt className="type-label text-muted-foreground">{reference ? "Sample filter reference" : "Value"}</dt><dd className="mt-1 break-words type-supporting">{reference && isFilterReference(condition.value) ? `sample.filters → ${condition.value.key}` : values.length ? values.map((value, index) => <span key={index} className="mr-1 inline-block rounded border border-border px-1.5 py-0.5 font-mono">{typeof value === "string" ? JSON.stringify(value) : JSON.stringify(value) ?? "undefined"}</span>) : "Empty list"}</dd></div>
    </dl>
  }
  const title = condition.type === "not" ? "NOT — invert condition" : condition.type === "elem_match" ? `Match one ${condition.field} element` : condition.type === "all" ? "AND — match all" : condition.type === "any" ? "OR — match any" : "NOR — match none"
  const children = condition.type === "not" ? [condition.child] : condition.type === "elem_match" ? [condition.condition] : condition.children
  return <section className="min-w-0 space-y-2 rounded-lg border border-border bg-muted/20 p-3" aria-label={title}>
    <h4 className="type-label">{title}</h4>
    {children.map((child, index) => <QueryConditionSummary key={index} condition={child} />)}
  </section>
}
