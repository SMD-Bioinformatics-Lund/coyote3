import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Plus
} from "lucide-react"
import type {
  ClinicalRule,
  FactDefinition,
  RuleBlock
} from "./clinical-rules-types"
import { newPredicate } from "./rule-condition-values"
import { ConditionBuilder } from "./RuleConditionBuilder"
import { OutputEditor } from "./RuleOutputEditor"

export function RuleEditor({ rule, block, facts, controlledValues, change }: { rule: ClinicalRule; block: RuleBlock; facts: FactDefinition[]; controlledValues: Record<string, string[]>; change: (rule: ClinicalRule) => void }) {
  const scopedFacts = facts.filter((fact) => fact.scopes.includes(block.evaluation.mode))
  return (
    <div className="space-y-5 p-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="type-label">Clinical rule name<Input className="mt-1" value={rule.name} onChange={(event) => change({ ...rule, name: event.target.value })} /></label>
        <label className="type-label">Rule identifier<Input className="mt-1" value={rule.rule_id} onChange={(event) => change({ ...rule, rule_id: event.target.value })} /></label>
      </div>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={rule.enabled} onChange={(event) => change({ ...rule, enabled: event.target.checked })} /> Include this rule in generated report text</label>
      <section><h3 className="type-section-title mb-2">When this text applies</h3>{rule.condition ? <ConditionBuilder value={rule.condition} facts={scopedFacts} allFacts={facts} controlledValues={controlledValues} onChange={(condition) => change({ ...rule, condition })} onRemove={() => change({ ...rule, condition: null })} /> : <Button type="button" variant="outline" onClick={() => change({ ...rule, condition: newPredicate(scopedFacts) })}><Plus /> Add condition</Button>}</section>
      <section><h3 className="type-section-title mb-2">Report text</h3><OutputEditor nodes={rule.output} facts={scopedFacts} onChange={(output) => change({ ...rule, output })} /></section>
      <label className="type-label block">Clinical rationale<textarea className="paper-inset mt-1 min-h-20 w-full rounded-lg p-2 text-sm" value={rule.rationale || ""} onChange={(event) => change({ ...rule, rationale: event.target.value || null })} /></label>
    </div>
  )
}
