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
import { RuleTerminologyEditor } from "./RuleTerminologyEditor"

export function RuleEditor({ rule, block, facts, controlledValues, change, terminology = {}, changeTerminology }: { rule: ClinicalRule; block: RuleBlock; facts: FactDefinition[]; controlledValues: Record<string, string[]>; change: (rule: ClinicalRule) => void; terminology?: Record<string, unknown>; changeTerminology?: (terms: Record<string, unknown>) => void }) {
  const scopedFacts = facts.filter((fact) => fact.scopes.includes(block.evaluation.mode))
  return (
    <div className="space-y-5 p-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="type-label">Clinical rule name<Input className="mt-1" value={rule.name} onChange={(event) => change({ ...rule, name: event.target.value })} /></label>
        <label className="type-label">Rule identifier<Input className="mt-1" value={rule.rule_id} onChange={(event) => change({ ...rule, rule_id: event.target.value })} /></label>
      </div>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={rule.enabled} onChange={(event) => change({ ...rule, enabled: event.target.checked })} /> Include this rule in generated report text</label>
      <p className="text-sm text-muted-foreground">A rule adds its text when its conditions match. Without a condition it applies to every {block.evaluation.mode === "once" ? "report" : "item in this section"}. Use separate rules for paired controls, selected gene lists, positive findings and no findings.</p>
      {!rule.condition && <label className="type-label block">Common condition<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value="" onChange={event => {
        const conditions: Record<string, ClinicalRule["condition"]> = {
          paired: { type: "predicate", fact: "sample.paired", operator: "eq", value: true },
          unpaired: { type: "predicate", fact: "sample.paired", operator: "eq", value: false },
          no_snvs: { type: "predicate", fact: "aggregates.snv_count", operator: "eq", value: 0 },
          no_cnvs: { type: "predicate", fact: "aggregates.cnv_count", operator: "eq", value: 0 },
          unaccredited: { type: "predicate", fact: "asp.accredited", operator: "eq", value: false },
        }
        if (conditions[event.target.value]) change({ ...rule, condition: conditions[event.target.value] })
      }}><option value="">Choose a starting condition…</option><option value="paired">Paired case/control analysis</option><option value="unpaired">No paired control</option><option value="no_snvs">No SNV findings</option><option value="no_cnvs">No CNV findings</option><option value="unaccredited">Assay not accredited</option></select></label>}
      <section><h3 className="type-section-title mb-2">When this text applies</h3>{rule.condition ? <ConditionBuilder value={rule.condition} facts={scopedFacts} allFacts={facts} controlledValues={controlledValues} onChange={(condition) => change({ ...rule, condition })} onRemove={() => change({ ...rule, condition: null })} /> : <Button type="button" variant="outline" onClick={() => change({ ...rule, condition: newPredicate(scopedFacts) })}><Plus /> Add condition</Button>}</section>
      <section><h3 className="type-section-title mb-2">Report text</h3><OutputEditor nodes={rule.output} facts={scopedFacts} onChange={(output) => change({ ...rule, output })} /></section>
      {[...new Set(rule.output.filter(node => node.type === "renderer").map(node => node.name))].map(name => {
        const terms = terminology[name]
        return <details key={name} className="rounded-lg border p-3"><summary className="cursor-pointer font-medium">Edit {name.replaceAll("_", " ")} wording</summary><p className="my-2 text-sm text-muted-foreground">These phrases are shared by this structured renderer throughout the rule set. Preserve intentional spaces between fragments and test the resulting sentences.</p>{terms && typeof terms === "object" && !Array.isArray(terms) && changeTerminology ? <RuleTerminologyEditor value={terms as Record<string, unknown>} change={next => changeTerminology({ ...terminology, [name]: next })} /> : <p role="alert" className="text-sm text-destructive">No wording is configured for this renderer. Copy a reviewed rule-set template with its terminology, or remove this output part and use text plus dynamic values. The General introduction starter provides editable introduction rules.</p>}</details>
      })}
      <label className="type-label block">Clinical rationale<textarea className="paper-inset mt-1 min-h-20 w-full rounded-lg p-2 text-sm" value={rule.rationale || ""} onChange={(event) => change({ ...rule, rationale: event.target.value || null })} /></label>
    </div>
  )
}
