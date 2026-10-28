import { useState } from "react"
import { icon } from "@/lib/assets"
import { MarkdownText } from "@/components/comments/MarkdownText"
import { Badge } from "@/components/ui/badge"
import type { ClinicalRuleSet, Condition, FactDefinition, RuleBlock } from "./clinical-rules-types"
import { OPERATOR_LABELS, valueText } from "./rule-condition-values"
import { outputPreview } from "./rule-output-preview"

const placementLabels = {
  paragraph: "New paragraph",
  continue: "Continue previous sentence",
  line: "New line",
  bullet: "Bullet point",
  numbered: "Numbered item",
}

const matchLabels: Record<RuleBlock["match_strategy"], string> = {
  all_matches: "Include all matching sentences in order.",
  first_match: "Use the first matching sentence only.",
  exactly_one: "Exactly one sentence must match each evaluation.",
  at_most_one: "Include at most one matching sentence per evaluation.",
}

function describeCondition(condition: Condition, facts: FactDefinition[]): string {
  if (condition.type === "predicate") {
    const label = facts.find(fact => fact.path === condition.fact)?.label || condition.fact
    const operator = OPERATOR_LABELS[condition.operator] || condition.operator
    const value = typeof condition.value === "boolean"
      ? condition.value ? "Yes" : "No" : valueText(condition.value)
    return `${label} ${operator}${value ? ` ${value}` : ""}`
  }
  if (condition.type === "not") return `Not (${describeCondition(condition.child, facts)})`
  if (condition.type === "collection_match") {
    const collection = condition.collection.replaceAll("_", " ")
    const match = condition.quantifier === "count"
      ? `Count ${OPERATOR_LABELS[condition.count?.operator || "gte"] || "at least"} ${condition.count?.value ?? 1}`
      : { any: "At least one", none: "No", all: "Every" }[condition.quantifier]
    return `${match} ${collection} matching (${describeCondition(condition.where, facts)})`
  }
  const conjunction = condition.type === "all" ? " AND " : " OR "
  return condition.children.map(child => `(${describeCondition(child, facts)})`).join(conjunction)
}

export function RuleCompositionPreview({ draft, facts }: {
  draft: ClinicalRuleSet; facts: FactDefinition[]
}) {
  const [showConditionalText, setShowConditionalText] = useState(true)
  const blocks = [...draft.blocks]
    .sort((a, b) => a.section_order - b.section_order || a.block_order - b.block_order)
    .filter(block => block.rules.some(rule => rule.enabled))
  if (!blocks.length) return <p className="type-body-sm text-muted-foreground">Enable reviewed rules to see their wording here.</p>

  return <div className="space-y-4">
    <div className="space-y-2">
      <Badge variant="secondary"><icon.gitBranch aria-hidden="true" />Report structure</Badge>
      <p className="type-body-sm text-muted-foreground">Conditional sentences are shown separately, in report order. They are not all included in a report. Select a sample to see which sentences match and how they join. Brackets represent dynamic values.</p>
      <label className="flex items-center gap-2 type-body-sm"><input type="checkbox" checked={showConditionalText} onChange={event => setShowConditionalText(event.target.checked)} />Show conditional wording</label>
    </div>
    {blocks.map(block => <section key={block.block_id} aria-label={`Preview section: ${block.section}`} className="space-y-2 border-t border-border pt-3">
      <header className="space-y-1">
        <h3 className="type-section-title break-words">{block.section}</h3>
        <p className="type-meta text-muted-foreground">{block.show_heading ? "Heading included in report" : "No heading in report"} · {block.evaluation.mode === "once" ? "Once per report" : block.evaluation.mode === "each_finding" ? "For each finding" : "For each item"}</p>
        <p className="type-body-sm text-muted-foreground">{matchLabels[block.match_strategy]}</p>
      </header>
      <ol className="space-y-2" aria-label={`Sentences in ${block.section}`}>
        {[...block.rules].filter(rule => rule.enabled).sort((a, b) => a.order - b.order).map((rule, index) => <li key={rule.rule_id}>
          <article aria-label={rule.name} className="min-w-0 space-y-2 rounded-lg border border-border bg-card p-3 shadow-sm">
            <header className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={rule.condition ? "secondary" : "outline"}>{rule.condition ? "Conditional" : "No condition"}</Badge>
                <span className="type-meta text-muted-foreground">{index + 1} · {placementLabels[rule.presentation || "paragraph"]}</span>
              </div>
              <h4 className="type-body-sm font-semibold break-words">{rule.name}</h4>
            </header>
            {(!rule.condition || showConditionalText) && <div className="break-words type-body-sm"><MarkdownText text={outputPreview(rule.output, facts) || "No wording configured."} /></div>}
            {rule.condition && <details className="type-body-sm text-muted-foreground">
              <summary className="cursor-pointer rounded-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">When this sentence applies</summary>
              <p className="mt-2 break-words">{describeCondition(rule.condition, facts)}</p>
            </details>}
          </article>
        </li>)}
      </ol>
    </section>)}
  </div>
}
