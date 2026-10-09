export type QueryCondition =
  | { type: "predicate"; field: string; operator: string; value: unknown }
  | { type: "all" | "any" | "nor"; children: QueryCondition[] }
  | { type: "not"; child: QueryCondition }
  | { type: "elem_match"; field: string; condition: QueryCondition }

export type QueryField = { path: string; label: string; kind: string; operators: string[]; value_role?: "gene"; hint?: string; filter_references?: { key: string; kind: string; path: string }[] }
export type QueryConditionCatalog = {
  fields: Record<string, QueryField[]>
  operators: Record<string, string>
  bson_types: string[]
  max_depth: number
  max_nodes: number
  max_list_values: number
}

export function isFilterReference(value: unknown): value is { source: "sample.filters"; key: string } {
  return typeof value === "object" && value !== null && "source" in value && value.source === "sample.filters" && "key" in value && typeof value.key === "string"
}

export function conditionNeedsSample(condition: QueryCondition): boolean {
  if (condition.type === "predicate") return isFilterReference(condition.value)
  if (condition.type === "not") return conditionNeedsSample(condition.child)
  if (condition.type === "elem_match") return conditionNeedsSample(condition.condition)
  return condition.children.some(conditionNeedsSample)
}

export function newQueryPredicate(fields: QueryField[]): QueryCondition {
  const field = fields.find(item => item.kind !== "object_list") ?? fields[0]
  const operator = field?.value_role === "gene" && field.operators.includes("in") ? "in" : field?.operators.includes("eq") ? "eq" : "exists"
  const reference = field?.filter_references?.find(ref => operator === "in" ? ref.kind === "string_list" : operator === "eq" && ref.kind !== "string_list")
  if (reference) return { type: "predicate", field: field!.path, operator, value: { source: "sample.filters", key: reference.key } }
  return { type: "predicate", field: field?.path ?? "", operator, value: operator === "in" ? [] : operator === "exists" || field?.kind === "boolean" ? true : ["number", "integer"].includes(field?.kind ?? "") ? 0 : "" }
}

export function describeQueryCondition(condition: QueryCondition): string {
  if (condition.type === "predicate") return `${condition.field} $${condition.operator} ${isFilterReference(condition.value) ? `sample.filters → ${condition.value.key}` : JSON.stringify(condition.value)}`
  if (condition.type === "not") return `NOT (${describeQueryCondition(condition.child)})`
  if (condition.type === "elem_match") return `One ${condition.field} element: (${describeQueryCondition(condition.condition)})`
  const joiner = condition.type === "all" ? " AND " : " OR "
  return `${condition.type === "nor" ? "NONE OF " : ""}(${condition.children.map(describeQueryCondition).join(joiner)})`
}
