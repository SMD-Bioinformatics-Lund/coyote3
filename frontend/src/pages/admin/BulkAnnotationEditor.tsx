import { useEffect, useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { MarkdownText } from "@/components/comments/MarkdownText"
import { MarkdownComposer } from "@/components/comments/MarkdownComposer"
import { api } from "@/lib/api"
import { ResizeDivider } from "@/components/admin/RuleWorkspaceDivider"
import { ConditionBuilder } from "./RuleConditionBuilder"
import { SentenceOutputEditor } from "./SentenceOutputEditor"
import type { BulkAnnotationRule, FactDefinition } from "./clinical-rules-types"

type Tier = 1 | 2 | 3
const tierNames = { 1: "I", 2: "II", 3: "III" }

export function BulkAnnotationEditor({ rules, facts, controlledValues, editable, onChange,
  onTextError, tier, setTier, ruleIds, sectionsWidth, setSectionsWidth }: {
  rules: BulkAnnotationRule[]; facts: FactDefinition[]; controlledValues: Record<string, string[]>;
  editable: boolean; onChange: (rules: BulkAnnotationRule[]) => void;
  onTextError: (error: string) => void; tier: Tier; setTier: (tier: Tier) => void;
  ruleIds: string[]
  sectionsWidth: number; setSectionsWidth: (width: number) => void
}) {
  const [selectedIds, setSelectedIds] = useState<Partial<Record<Tier, string>>>({})
  const selectedId = selectedIds[tier] || ""
  const setSelectedId = (id: string) => setSelectedIds(current => ({ ...current, [tier]: id }))
  const tierRules = rules.filter(item => item.tier === tier).sort((a, b) => a.order - b.order)
  const rule = tierRules.find(item => item.rule_id === selectedId) || tierRules[0]
  const index = tierRules.findIndex(item => item === rule)
  const change = (next: BulkAnnotationRule) => onChange(rules.map(item => item === rule ? next : item))
  return <div className="clinical-rules-editor-layout min-h-0">
    <aside className="min-h-0 space-y-2 border-b border-border bg-muted/15 p-3 md:border-b-0">
      <h3 className="type-label">Target tier</h3>
      {([1, 2, 3] as const).map(value => <Button key={value} type="button" variant={tier === value ? "secondary" : "ghost"} className="w-full justify-start" aria-pressed={tier === value} onClick={() => { setTier(value); onTextError("") }}>Tier {tierNames[value]}</Button>)}
      <p className="type-meta text-muted-foreground">Templates add text to the tier selected by the user. They do not choose the tier.</p>
    </aside>
    <ResizeDivider label="Resize annotation tiers" width={sectionsWidth} setWidth={setSectionsWidth} min={160} max={360} />
    <div className="min-h-0 min-w-0 space-y-4 overflow-y-auto p-4">
      <p className="type-body-sm text-muted-foreground">Bulk actions only. The first enabled matching template for this tier supplies the annotation text. Individual tiering is unchanged.</p>
      <div className="flex flex-wrap gap-2" aria-label="Annotation templates">
        {tierRules.map(item => <Button key={item.rule_id} type="button" size="sm" variant={item === rule ? "secondary" : "outline"} aria-pressed={item === rule} onClick={() => { setSelectedId(item.rule_id); onTextError("") }}>{item.name}</Button>)}
        {editable && <Button type="button" size="sm" variant="outline" onClick={() => {
          let suffix = 1
          while (ruleIds.includes(`bulk_tier_${tier}_${suffix}`)) suffix++
          const rule_id = `bulk_tier_${tier}_${suffix}`
          onChange([...rules, { rule_id, name: `Tier ${tierNames[tier]} annotation ${suffix}`, tier,
            order: Math.max(0, ...tierRules.map(item => item.order)) + 10,
            enabled: false, condition: null, output: [{ type: "text", value: "" }], references: [] }])
          setSelectedId(rule_id)
        }}>Add annotation template</Button>}
      </div>
      {rule ? <>
        {editable && <div className="flex flex-wrap gap-2">
          {([-1, 1] as const).map(direction => <Button key={direction} type="button" size="sm" variant="outline" disabled={index + direction < 0 || index + direction >= tierRules.length} onClick={() => {
            const next = [...tierRules]
            const [moved] = next.splice(index, 1)
            next.splice(index + direction, 0, moved)
            setSelectedId(rule.rule_id)
            const orders = new Map(next.map((item, position) => [item.rule_id, (position + 1) * 10]))
            onChange(rules.map(item => orders.has(item.rule_id) ? { ...item, order: orders.get(item.rule_id)! } : item))
          }}>Move template {direction < 0 ? "up" : "down"}</Button>)}
          <Button type="button" size="sm" variant="destructive" onClick={() => { onChange(rules.filter(item => item !== rule)); onTextError("") }}>Remove template</Button>
        </div>}
        <fieldset disabled={!editable} className="space-y-4">
          <label className="type-label block">Annotation template name<Input className="mt-1" value={rule.name} onChange={event => change({ ...rule, name: event.target.value })} /></label>
          <section className="space-y-2"><h3 className="type-section-title">When this annotation applies</h3>
            {rule.condition ? <ConditionBuilder allowCollections={false} value={rule.condition} facts={facts} allFacts={facts} controlledValues={controlledValues} onChange={condition => change({ ...rule, condition })} onRemove={() => change({ ...rule, condition: null })} />
              : <><p className="type-body-sm text-muted-foreground">No condition: fallback for every finding assigned this tier.</p>{editable && facts.length > 0 && <Button type="button" variant="outline" size="sm" onClick={() => change({ ...rule, condition: { type: "predicate", fact: "finding.gene", operator: "eq", value: "" } })}>Add annotation condition</Button>}</>}
          </section>
          <section className="space-y-2"><h3 className="type-section-title">Annotation text</h3><SentenceOutputEditor label="Annotation sentence" examplePath="finding.gene" key={rule.rule_id} nodes={rule.output} facts={facts} onChange={output => change({ ...rule, output })} onErrorChange={onTextError} readOnly={!editable} /></section>
          <label className="flex items-center gap-2 type-body-sm"><input type="checkbox" checked={rule.enabled} onChange={event => change({ ...rule, enabled: event.target.checked })} />Enable this annotation template</label>
          <details><summary className="cursor-pointer type-label">Template details</summary><p className="mt-2 break-all type-meta">Identifier: {rule.rule_id}</p><MarkdownComposer label="Annotation rationale" value={rule.rationale || ""} onChange={rationale => change({ ...rule, rationale })} maxLength={null} readOnly={!editable} compact /></details>
        </fieldset>
      </> : <p className="type-body-sm text-muted-foreground">No annotation templates for Tier {tierNames[tier]}.</p>}
    </div>
  </div>
}

export function BulkAnnotationPreview({ documentId, revision, saved, tier, scopeDiagnosis }: {
  documentId: string; revision: number; saved: boolean; tier: Tier; scopeDiagnosis: string
}) {
  const [diagnosis, setDiagnosis] = useState(scopeDiagnosis)
  useEffect(() => { setDiagnosis(scopeDiagnosis) }, [scopeDiagnosis])
  const [gene, setGene] = useState("")
  const [consequence, setConsequence] = useState("")
  const [hgvsc, setHgvsc] = useState("")
  const [hgvsp, setHgvsp] = useState("")
  const preview = useMutation({ mutationFn: () => api.post<{ rule_id: string | null; text: string | null }>(
    `/admin/clinical-rule-sets/versions/${documentId}/bulk-annotations/preview`,
    { tier, diagnosis_id: diagnosis.trim() || null, gene: gene || null, consequence: consequence.split(/[,&]/).map(item => item.trim()).filter(Boolean), hgvsc: hgvsc || null, hgvsp: hgvsp || null },
    { errorNotice: "inline" },
  ).then(response => response.data) })
  const reset = preview.reset
  useEffect(() => { reset() }, [documentId, revision, tier, diagnosis, gene, consequence, hgvsc, hgvsp, reset])
  return <section aria-label="Bulk annotation preview" className="space-y-3">
    <h2 className="type-section-title">Annotation preview · Tier {tierNames[tier]}</h2>
    <p className="type-body-sm text-muted-foreground">Enter synthetic finding values to check matching and wording. No sample or annotation is created.</p>
    {([["Diagnosis", diagnosis, setDiagnosis], ["Gene", gene, setGene], ["Consequence", consequence, setConsequence], ["HGVS c", hgvsc, setHgvsc], ["HGVS p", hgvsp, setHgvsp]] as const).map(([label, value, setValue]) => <label key={label} className="type-label block">{label}<Input className="mt-1" aria-label={`Annotation preview ${label}`} value={value} onChange={event => setValue(event.target.value)} /></label>)}
    <Button type="button" variant="outline" disabled={!saved || preview.isPending} onClick={() => preview.mutate()}>Preview annotation</Button>
    {!saved && <p role="status" className="type-meta text-muted-foreground">Waiting for valid edits to save.</p>}
    {preview.error && <p role="alert" className="type-body-sm text-destructive">{preview.error instanceof Error ? preview.error.message : "Annotation preview failed."}</p>}
    {preview.data && <div className="paper-inset space-y-2 rounded-lg p-3"><p className="type-meta">{preview.data.rule_id ? `Matched template: ${preview.data.rule_id}` : "No enabled template matched. Bulk tiering will add no automatic annotation text."}</p>{preview.data.text && <MarkdownText text={preview.data.text} />}</div>}
  </section>
}
