import type {
  ClinicalRule,
  ClinicalRuleAssayOption,
  RuleBlock
} from "./clinical-rules-types"


export const ANALYSES = {
  dna: ["SNV", "CNV", "TRANSLOCATION", "HRD", "MSI", "CNV_PROFILE", "COVERAGE", "FUSION", "TMB", "PGX"],
  rna: ["FUSION", "EXPRESSION", "CLASSIFICATION", "QC", "PGX"],
} as const

export const clone = <T,>(value: T): T => structuredClone(value)

export type NewRuleSetScope = {
  asp_id: string
  subpanel_id: string
  analyte: "dna" | "rna"
  language: string
  name: string
}

export type CreationMode = "blank" | "template" | "import"

export const emptyRuleSetScope = (): NewRuleSetScope => ({
  asp_id: "",
  subpanel_id: "base",
  analyte: "dna",
  language: "sv",
  name: "",
})

export const identifierPart = (value: string) => value
  .normalize("NFKD")
  .replace(/[\u0300-\u036f]/g, "")
  .toLowerCase()
  .replace(/[^a-z0-9]+/g, "_")
  .replace(/^_+|_+$/g, "")

export const nextIdentifier = (base: string, used: Iterable<string>) => {
  const normalized = identifierPart(base) || "rule"
  const existing = new Set(used)
  if (!existing.has(normalized)) return normalized
  let suffix = 2
  while (existing.has(`${normalized}_${suffix}`)) suffix += 1
  return `${normalized}_${suffix}`
}

export const nextOrdinal = (prefix: string, used: Iterable<string>) => {
  const existing = new Set(used)
  let ordinal = 1
  while (existing.has(`${prefix} ${ordinal}`)) ordinal += 1
  return ordinal
}

export const nextOrder = (used: number[], interval: number) =>
  used.length ? Math.max(...used) + interval : interval

export const generatedRuleSetName = (
  assay: ClinicalRuleAssayOption | undefined,
  subpanelId: string,
) => {
  if (!assay) return ""
  const subpanel = subpanelId.trim()
  const scope = subpanel && subpanel !== "base" ? ` - ${subpanel}` : ""
  return `${assay.display_name}${scope} clinical report rules`
}

export const newRule = (
  block: Pick<RuleBlock, "block_id" | "section" | "rules">,
  allRuleIds: string[],
): ClinicalRule => {
  const namePrefix = `${block.section} rule`
  const ordinal = nextOrdinal(namePrefix, block.rules.map((rule) => rule.name))
  return {
    rule_id: nextIdentifier(`${block.block_id}_rule_${ordinal}`, allRuleIds),
    name: `${namePrefix} ${ordinal}`,
    order: nextOrder(block.rules.map((rule) => rule.order), 10),
    enabled: true,
    condition: null,
    output: [{ type: "text", value: "New clinical report text" }],
    references: [],
  }
}

export const newRuleBlock = (blocks: RuleBlock[]): RuleBlock => {
  const ordinal = nextOrdinal("Report section", blocks.map((block) => block.section))
  const section = `Report section ${ordinal}`
  const blockId = nextIdentifier(section, blocks.map((block) => block.block_id))
  const block: RuleBlock = {
    block_id: blockId,
    name: section,
    analysis: null,
    evaluation: { mode: "once", collection: null },
    section,
    section_order: nextOrder(blocks.map((item) => item.section_order), 100),
    block_order: nextOrder(blocks.map((item) => item.block_order), 10),
    show_heading: true,
    match_strategy: "at_most_one",
    rules: [],
  }
  const existingRuleIds = blocks.flatMap((item) => item.rules.map((rule) => rule.rule_id))
  block.rules.push(newRule(block, existingRuleIds))
  return block
}
