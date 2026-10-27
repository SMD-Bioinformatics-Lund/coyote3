import type {
  Condition,
  FactDefinition,
  PredicateCondition
} from "./clinical-rules-types"


export const OPERATOR_LABELS: Record<string, string> = {
  eq: "is",
  ne: "is not",
  in: "is one of",
  not_in: "is not one of",
  contains: "contains",
  overlaps: "overlaps",
  exists: "is available",
  gt: "is greater than",
  gte: "is at least",
  lt: "is less than",
  lte: "is at most",
  between: "is between",
  is_empty: "is empty",
  is_unknown: "is unknown",
}

export function newPredicate(facts: FactDefinition[]): Condition {
  const fact = facts[0]
  return predicateFor(fact?.path || "finding.gene", fact?.operators[0] || "eq", fact)
}

export function newCollectionPredicate(facts: FactDefinition[], collection: string): Condition {
  const path = collection === "applied_gene_lists" ? "item.selected_for"
    : collection === "tier_summaries" ? "item.tier"
    : ["hrd", "msi", "tmb"].includes(collection) ? "item.value" : "item.kind"
  const fact = facts.find(item => item.path === path)
  return predicateFor(path, fact?.kind === "string_list" ? "contains" : fact?.operators[0] || "eq", fact)
}

export function predicateFor(path: string, operator: string, fact?: FactDefinition, previous?: unknown): PredicateCondition {
  if (["is_empty", "is_unknown"].includes(operator)) return { type: "predicate", fact: path, operator }
  const multiple = ["in", "not_in", "overlaps", "between"].includes(operator)
  const value = multiple ? Array.isArray(previous) ? previous : []
    : operator === "exists" || fact?.kind === "boolean"
    ? typeof previous === "boolean" ? previous : true
      : Array.isArray(previous) || typeof previous === "boolean" ? "" : previous ?? ""
  return { type: "predicate", fact: path, operator, value }
}

export function parseValue(value: string, operator: string, fact?: FactDefinition): unknown {
  if (operator === "exists") return value === "true"
  if (["in", "not_in", "overlaps", "between"].includes(operator)) {
    const values = value.split(",").map((item) => item.trim()).filter(Boolean)
    return fact?.kind === "boolean" ? values.map(item => item === "true") : ["integer", "number"].includes(fact?.kind || "") ? values.map(Number) : values
  }
  if (fact?.kind === "boolean") return value === "true"
  if (fact?.kind === "integer" || fact?.kind === "number") return value.trim() ? Number(value) : ""
  return value
}

export function valueError(value: unknown, operator: string, fact?: FactDefinition) {
  if (["is_empty", "is_unknown"].includes(operator)) return ""
  if (operator === "exists") return typeof value === "boolean" ? "" : "Choose Yes or No."
  const text = valueText(value).trim()
  if (!text) return "A value is required for this condition."
  if (["in", "not_in", "overlaps", "between"].includes(operator) && !Array.isArray(value)) return "Enter a list of values."
  if (fact?.kind === "boolean" && !["in", "not_in"].includes(operator) && typeof value !== "boolean") return "Choose Yes or No."
  if (fact?.kind === "boolean" && Array.isArray(value) && value.some(item => typeof item !== "boolean")) return "Choose Yes or No values."
  const values = Array.isArray(value) ? value : [value]
  if (["integer", "number"].includes(fact?.kind || "") && values.some((item) => !Number.isFinite(Number(item)))) {
    return `Enter ${fact?.kind === "integer" ? "whole numbers" : "numeric values"}.`
  }
  if (fact?.kind === "integer" && values.some((item) => !Number.isInteger(Number(item)))) return "Enter whole numbers."
  if (fact?.value_format === "gene" && values.some((item) => !/^[A-Za-z0-9][A-Za-z0-9-]*$/.test(String(item)))) {
    return "Use HGNC gene symbols, separated by commas where multiple values are accepted."
  }
  if (fact?.value_options?.length && values.some((item) => !fact.value_options?.includes(String(item)))) {
    return "Select one of the configured values."
  }
  if (operator === "between" && Array.isArray(value) && value.length !== 2) return "Enter exactly two comma-separated values."
  return ""
}

export function valueText(value: unknown) {
  return Array.isArray(value) ? value.join(", ") : String(value ?? "")
}

export function conditionError(condition: Condition | null | undefined, facts: FactDefinition[], choices: Record<string, string[]>): string {
  if (!condition) return ""
  if (condition.type === "predicate") {
    const fact = facts.find(item => item.path === condition.fact)
    if (!fact) return ""
    return valueError(condition.value, condition.operator, { ...fact, value_options: choices[fact.path] || fact.value_options })
  }
  if (condition.type === "not") return conditionError(condition.child, facts, choices)
  if (condition.type === "collection_match") return conditionError(condition.where, facts, choices)
  return condition.children.map(child => conditionError(child, facts, choices)).find(Boolean) || ""
}
