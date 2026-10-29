import type {
  ClinicalRule,
  ClinicalRuleAssayOption,
  OutputNode,
  RuleBlock
} from "./clinical-rules-types"


export const ANALYSES = {
  dna: ["SNV", "CNV", "TRANSLOCATION", "HRD", "MSI", "CNV_PROFILE", "COVERAGE", "TMB", "PGX"],
  rna: ["FUSION", "EXPRESSION", "CLASSIFICATION", "QC"],
} as const

export const clone = <T,>(value: T): T => structuredClone(value)

export const ruleSectionLabel = (section: string): string =>
  section === "analysis_description" ? "Analysis description" : section

export type NewRuleSetScope = {
  asp_id: string
  diagnosis_id: string
  analyte: "dna" | "rna"
  language: string
  name: string
}

export type CreationMode = "blank" | "template" | "import"

export const emptyRuleSetScope = (): NewRuleSetScope => ({
  asp_id: "",
  diagnosis_id: "base",
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
  diagnosisId: string,
) => {
  if (!assay) return ""
  const diagnosis = diagnosisId.trim()
  const scope = diagnosis && diagnosis !== "base" ? ` - ${diagnosis}` : ""
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

export const SECTION_STARTERS = [
  ["intro", "General introduction", ""],
  ["analysis_description", "Analysis description", ""],
  ["snv_summary", "SNV summary: findings / no findings", "SNV"],
  ["snv", "Variant text", "SNV"],
  ["cnv", "CNV text", "CNV"],
  ["translocation", "DNA fusion text", "TRANSLOCATION"],
  ["fusion", "RNA fusion text", "FUSION"],
  ["hrd", "HRD text", "HRD"],
  ["msi", "MSI text", "MSI"],
  ["tmb", "TMB text", "TMB"],
  ["closing", "Closing text", ""],
] as const

export function sectionStarter(blocks: RuleBlock[], key: string, scope: NewRuleSetScope): RuleBlock {
  const preset = SECTION_STARTERS.find(([id]) => id === key)
  const block = newRuleBlock(blocks)
  if (!preset) return block
  block.block_id = nextIdentifier(`${scope.asp_id}_${scope.diagnosis_id}_${key}`, blocks.map(item => item.block_id))
  block.section = block.name = preset[1]
  block.analysis = preset[2] || null
  block.show_heading = !["intro", "closing", "analysis_description"].includes(key)
  if (key === "analysis_description") block.section = "analysis_description"
  block.rules = []
  const used = blocks.flatMap(item => item.rules.map(rule => rule.rule_id))
  const add = (name: string, output: OutputNode[], condition: ClinicalRule["condition"] = null) => {
    const rule = newRule(block, used)
    rule.name = name
    rule.rule_id = nextIdentifier(`${block.block_id}_${name}`, used)
    rule.enabled = false
    rule.output = output
    rule.condition = condition
    if (key === "intro" && block.rules.length) rule.presentation = "continue"
    block.rules.push(rule)
    used.push(rule.rule_id)
  }
  const text = (value: string): OutputNode => ({ type: "text", value })
  const fact = (path: string): OutputNode => ({ type: "fact", path, formatter: "text", missing: "error" })
  const list = (path: string): OutputNode => ({ type: "list", path, formatter: "text", missing: "error", conjunction: scope.language === "sv" ? "och" : "and" })
  const number = (path: string): OutputNode => ({ type: "number", path, precision: 0, unit: "", missing: "error" })
  const predicate = (fact: string, operator: string, value: unknown): ClinicalRule["condition"] => ({ type: "predicate", fact, operator, value })
  const sv = scope.language === "sv"
  if (key === "intro" || key === "analysis_description") {
    block.match_strategy = "all_matches"
    const analysis = scope.analyte === "rna" ? "fusion" : "snv"
    add("Assay and panel scope", [text(sv ? "Analysen omfattar " : "The analysis covers "), number("asp.covered_genes_count"), text(sv ? " gener i " : " genes in "), fact("asp.display_name"), text(". ")])
    add("Paired control wording", [text(sv ? "Analysen har utförts med ett parat kontrollprov. " : "The analysis was performed with a paired control sample. ")], predicate("sample.paired", "eq", true))
    add("Unpaired control wording", [text(sv ? "Analysen har utförts utan parat kontrollprov. " : "The analysis was performed without a paired control sample. ")], predicate("sample.paired", "eq", false))
    add("Selected gene lists", [text(sv ? "Analysen omfattar genlistan: " : "Selected gene lists: "), list(`gene_lists.${analysis}.names`), text(sv ? " som innefattar " : " covering "), number(`gene_lists.${analysis}.gene_count`), text(sv ? " gener. " : " genes. ")], predicate(`gene_lists.${analysis}.gene_count`, "gt", 0))
    add("Selected germline genes", [text(sv ? "För " : "For "), list(`gene_lists.${analysis}.germline_genes`), text(sv ? " undersöks även konstitutionella mutationer." : " constitutional variants are also investigated.")], { type: "all", children: [predicate("sample.paired", "eq", true)!, { type: "not", child: { type: "predicate", fact: `gene_lists.${analysis}.germline_genes`, operator: "is_empty" } }] })
  } else if (key === "snv_summary") {
    block.section = block.name = sv ? "Kliniskt relevanta SNVs och små INDELs" : "SNV summary"
    block.evaluation = { mode: "once", collection: null }
    block.match_strategy = "exactly_one"
    add("Reportable SNVs present", [{ type: "renderer", name: "tier_summary" }], predicate("aggregates.has_tiered_snvs", "eq", true))
    add("No reportable tiered SNVs", [text(sv ? "Vid analysen har inga somatiskt förvärvade mutationer i undersökta gener påvisats." : "Enter reviewed wording for no reportable tiered SNVs.")], predicate("aggregates.has_tiered_snvs", "eq", false))
  } else if (key === "closing") {
    block.match_strategy = "all_matches"
    add("Closing wording", [text(sv ? "Ange granskad avslutande text." : "Enter reviewed closing text.")])
    add("Outside accreditation", [text(sv ? "Analysen omfattas inte av ackrediteringen." : "The analysis is not covered by accreditation.")], predicate("asp.accredited", "eq", false))
  } else {
    block.evaluation = ["hrd", "msi", "tmb"].includes(key)
      ? { mode: "each_item", collection: key as "hrd" | "msi" | "tmb" }
      : { mode: "each_finding", collection: null }
    add(preset[1], [text("Enter reviewed report wording.")], ["hrd", "msi", "tmb"].includes(key) ? null : predicate("finding.kind", "eq", key))
  }
  return block
}
