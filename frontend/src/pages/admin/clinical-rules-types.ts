export type RuleStatus =
  | "draft"
  | "submitted"
  | "in_clinical_review"
  | "approved"
  | "rejected"
  | "published"
  | "retired"

export type FactDefinition = {
  path: string
  label: string
  group: string
  kind: "boolean" | "integer" | "number" | "string" | "string_list" | "object_list"
  operators: string[]
  scopes: string[]
  unit?: string | null
  description?: string
  value_options?: string[]
  value_format?: "gene" | "integer" | "number" | "text"
}

export type ClinicalRuleAssayOption = {
  asp_id: string
  display_name: string
  analyte: "dna" | "rna"
}

export type ClinicalRuleReviewerOption = { username: string; name: string }

export type PredicateCondition = {
  type: "predicate"
  fact: string
  operator: string
  value?: unknown
}

export type Condition =
  | PredicateCondition
  | { type: "all" | "any"; children: Condition[] }
  | { type: "not"; child: Condition }
  | {
      type: "collection_match"
      collection: "findings" | "biomarkers" | "applied_gene_lists" | "tier_summaries"
      quantifier: "any" | "none" | "all" | "count"
      where: Condition
      count?: { operator: "eq" | "ne" | "gt" | "gte" | "lt" | "lte"; value: number }
    }

export type OutputNode =
  | { type: "text"; value: string }
  | { type: "fact"; path: string; formatter: "text" | "gene_symbol" | "upper" | "lower"; missing: "error" | "omit" }
  | { type: "list"; path: string; conjunction: string; formatter: "text" | "gene_symbol" | "upper" | "lower"; missing: "error" | "omit" }
  | { type: "number"; path: string; precision: number; unit: "" | "%" | "x"; missing: "error" | "omit" }
  | { type: "message"; count_path: string; one: string; other: string }
  | { type: "renderer"; name: "dna_report_intro" | "tier_summary" | "fusion_summary"; source?: string }
  | { type: "paragraph_break" }

export type ClinicalRule = {
  rule_id: string
  name: string
  order: number
  enabled: boolean
  condition?: Condition | null
  output: OutputNode[]
  references: string[]
  rationale?: string | null
}

export type RuleBlock = {
  block_id: string
  name: string
  analysis?: string | null
  evaluation: {
    mode: "once" | "each_finding" | "each_item"
    collection?: "findings" | "biomarkers" | "applied_gene_lists" | "tier_summaries" | null
  }
  section: string
  section_order: number
  block_order: number
  show_heading: boolean
  match_strategy: "all_matches" | "first_match" | "exactly_one" | "at_most_one"
  rules: ClinicalRule[]
}

export type ClinicalRuleSet = {
  _id: string
  rule_set_id: string
  schema_version: number
  content_version: number
  revision: number
  scope: { asp_id: string; subpanel_id: string; analyte: "dna" | "rna"; language: string }
  name: string
  status: RuleStatus
  active: boolean
  minimum_engine_version: number
  analysis_declarations: Record<string, { narrative: "enabled" | "none" }>
  terminology: Record<string, unknown>
  blocks: RuleBlock[]
  test_cases: unknown[]
  references: Record<string, unknown>[]
  change_summary: string
  review: {
    submitted_by?: string | null
    clinical_reviewer?: string | null
    clinical_decision_reason?: string | null
    publisher?: string | null
  }
  updated_at: string
  updated_by: string
  created_at?: string
  created_by?: string
}

export type ClinicalRuleRevision = {
  _id?: string
  rule_set_oid: string
  rule_set_id: string
  content_version: number
  revision: number
  action: string
  actor: string
  occurred_at: string
  reason?: string | null
  previous_revision_hash?: string | null
  revision_hash: string
  document: ClinicalRuleSet
}
