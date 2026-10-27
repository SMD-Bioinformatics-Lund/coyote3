import type { Condition, FactDefinition } from "./clinical-rules-types"

export const CONDITION_PRESETS: { key: string; label: string; hint: string; condition: Condition }[] = [
  { key: "paired", label: "Paired control available", hint: "Use control-material wording only when a paired analysis was prepared. This does not identify the control tissue.", condition: { type: "predicate", fact: "sample.paired", operator: "eq", value: true } },
  { key: "unpaired", label: "No paired control", hint: "Adds this sentence for an unpaired analysis. Leave the rule disabled if no unpaired sentence is required.", condition: { type: "predicate", fact: "sample.paired", operator: "eq", value: false } },
  { key: "tiered_snvs", label: "Reportable tiered SNVs present", hint: "Matches prepared, reportable tier groups. It does not assign tiers or restore excluded findings.", condition: { type: "predicate", fact: "aggregates.has_tiered_snvs", operator: "eq", value: true } },
  { key: "no_tiered_snvs", label: "No reportable tiered SNVs", hint: "Use for the negative summary. Unclassified SNVs may still exist; this is different from a raw SNV count of zero.", condition: { type: "predicate", fact: "aggregates.has_tiered_snvs", operator: "eq", value: false } },
  { key: "selected_snv_lists", label: "At least one SNV gene list selected", hint: "Counts only applied lists selected for SNV, excluding lists selected solely for other analyses. Change the count for singular/plural wording.", condition: { type: "collection_match", collection: "applied_gene_lists", quantifier: "count", count: { operator: "gte", value: 1 }, where: { type: "predicate", fact: "item.selected_for", operator: "contains", value: "snv" } } },
  { key: "unaccredited", label: "Assay outside accreditation", hint: "Adds an accreditation disclaimer when the assay is marked unaccredited.", condition: { type: "predicate", fact: "asp.accredited", operator: "eq", value: false } },
]

export function availableConditionPresets(facts: FactDefinition[]) {
  const paths = new Set(facts.map(fact => fact.path))
  return CONDITION_PRESETS.filter(preset => preset.condition.type === "predicate"
    ? paths.has(preset.condition.fact)
    : paths.has("item.selected_for"))
}

export function matchingConditionPreset(condition: Condition | null | undefined, facts: FactDefinition[]) {
  const fingerprint = (value: unknown) => JSON.stringify(value, (_key, item: unknown) => item && typeof item === "object" && !Array.isArray(item)
    ? Object.fromEntries(Object.entries(item).sort(([a], [b]) => a.localeCompare(b))) : item)
  return availableConditionPresets(facts).find(preset => fingerprint(preset.condition) === fingerprint(condition))
}
