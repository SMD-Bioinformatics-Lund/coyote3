import type {
  Condition,
  FactDefinition
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
  return { type: "predicate", fact: fact?.path || "finding.gene", operator: fact?.operators[0] || "eq", value: "" }
}

export function parseValue(value: string, operator: string, fact?: FactDefinition): unknown {
  if (fact?.kind === "boolean") return value === "true"
  if (fact?.kind === "integer" || fact?.kind === "number") return Number(value)
  if (fact?.kind === "string_list" || ["in", "not_in", "overlaps", "between"].includes(operator)) {
    return value.split(",").map((item) => item.trim()).filter(Boolean)
  }
  return value
}

export function valueError(value: unknown, operator: string, fact?: FactDefinition) {
  const text = valueText(value).trim()
  if (!text) return "A value is required for this condition."
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
