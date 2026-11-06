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
import { annotationFindingOptions, type AnnotationFindingKind, type BulkAnnotationGroupOption, type BulkAnnotationRule, type FactDefinition } from "./clinical-rules-types"

type Tier = 1 | 2 | 3
const tierNames = { 1: "I", 2: "II", 3: "III" }

export function BulkAnnotationEditor({ rules, facts, controlledValues, editable, onChange,
  onTextError, tier, setTier, ruleIds, sectionsWidth, setSectionsWidth, analyte, findingKind, setFindingKind }: {
  analyte: "dna" | "rna"; findingKind: AnnotationFindingKind; setFindingKind: (kind: AnnotationFindingKind) => void
  rules: BulkAnnotationRule[]; facts: FactDefinition[]; controlledValues: Record<string, string[]>;
  editable: boolean; onChange: (rules: BulkAnnotationRule[]) => void;
  onTextError: (error: string) => void; tier: Tier; setTier: (tier: Tier) => void;
  ruleIds: string[]
  sectionsWidth: number; setSectionsWidth: (width: number) => void
}) {
  const [selectedIds, setSelectedIds] = useState<Record<string, string>>({})
  const selectionKey = `${findingKind}:${tier}`
  const selectedId = selectedIds[selectionKey] || ""
  const setSelectedId = (id: string) => setSelectedIds(current => ({ ...current, [selectionKey]: id }))
  const tierRules = rules.filter(item => item.tier === tier && (item.finding_kind || "small_variant") === findingKind).sort((a, b) => a.order - b.order)
  const rule = tierRules.find(item => item.rule_id === selectedId) || tierRules[0]
  const index = tierRules.findIndex(item => item === rule)
  const change = (next: BulkAnnotationRule) => onChange(rules.map(item => item === rule ? next : item))
  return <div className="clinical-rules-editor-layout min-h-0">
    <aside className="min-h-0 space-y-2 border-b border-border bg-muted/15 p-3 md:border-b-0">
      <label className="type-label block">Finding type<select className="paper-inset mt-1 w-full rounded-lg p-2 type-body" value={findingKind} onChange={event => { setFindingKind(event.target.value as AnnotationFindingKind); onTextError("") }}>{annotationFindingOptions[analyte].map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
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
          onChange([...rules, { rule_id, name: `Tier ${tierNames[tier]} annotation ${suffix}`, tier, finding_kind: findingKind,
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
              : <><p className="type-body-sm text-muted-foreground">No condition: fallback for this finding type and tier.</p>{editable && facts.length > 0 && <Button type="button" variant="outline" size="sm" onClick={() => change({ ...rule, condition: { type: "predicate", fact: "sample.asp_id", operator: "eq", value: "" } })}>Add annotation condition</Button>}</>}
          </section>
          <section className="space-y-2"><h3 className="type-section-title">Annotation text</h3><SentenceOutputEditor label="Annotation sentence" examplePath={findingKind === "small_variant" ? "finding.gene" : findingKind === "cnv" ? "finding.chromosome" : "finding.fusion_gene_1"} key={rule.rule_id} nodes={rule.output} facts={facts} onChange={output => change({ ...rule, output })} onErrorChange={onTextError} readOnly={!editable} /></section>
          <label className="flex items-center gap-2 type-body-sm"><input type="checkbox" checked={rule.enabled} onChange={event => change({ ...rule, enabled: event.target.checked })} />Enable this annotation template</label>
          <details><summary className="cursor-pointer type-label">Template details</summary><p className="mt-2 break-all type-meta">Identifier: {rule.rule_id}</p><MarkdownComposer label="Annotation rationale" value={rule.rationale || ""} onChange={rationale => change({ ...rule, rationale })} maxLength={null} readOnly={!editable} compact /></details>
        </fieldset>
      </> : <p className="type-body-sm text-muted-foreground">No annotation templates for Tier {tierNames[tier]}.</p>}
    </div>
  </div>
}

export function BulkAnnotationPreview({ documentId, revision, saved, tier, scopeDiagnosis, groups, findingKind }: {
  findingKind: AnnotationFindingKind
  documentId: string; revision: number; saved: boolean; tier: Tier; scopeDiagnosis: string;
  groups: BulkAnnotationGroupOption[]
}) {
  const [diagnosis, setDiagnosis] = useState(scopeDiagnosis)
  useEffect(() => { setDiagnosis(scopeDiagnosis) }, [scopeDiagnosis])
  const [gene, setGene] = useState("")
  const [consequence, setConsequence] = useState("")
  const [hgvsc, setHgvsc] = useState("")
  const [hgvsp, setHgvsp] = useState("")
  const [group, setGroup] = useState("")
  const [transcript, setTranscript] = useState("")
  const [variantType, setVariantType] = useState("")
  const [oncokb, setOncokb] = useState("unknown")
  const [oncokbDescription, setOncokbDescription] = useState("")
  const [structural, setStructural] = useState<Record<string, string>>({})
  const structuralFields = findingKind === "cnv"
    ? [["chromosome", "Chromosome"], ["start", "Start"], ["end", "End"], ["cnv_effect", "Copy-number effect"]]
    : [["fusion_gene_1", "First partner gene"], ["fusion_gene_2", "Second partner gene"], ...(findingKind === "fusion" ? [["fusion_breakpoint_1", "First breakpoint"], ["fusion_breakpoint_2", "Second breakpoint"]] : [])]
  const preview = useMutation({ mutationFn: () => api.post<{ rule_id: string | null; text: string | null }>(
    `/admin/clinical-rule-sets/versions/${documentId}/bulk-annotations/preview`,
    { tier, finding_kind: findingKind, ...(findingKind === "small_variant" ? {} : Object.fromEntries(structuralFields.map(([key]) => [key, structural[key] ? (["start", "end"].includes(key) ? Number(structural[key]) : structural[key]) : null]))), diagnosis_id: diagnosis.trim() || null, asp_group: group || null, gene: findingKind === "small_variant" ? gene || null : null, consequence: findingKind === "small_variant" ? consequence.split(/[,&]/).map(item => item.trim()).filter(Boolean) : [], hgvsc: findingKind === "small_variant" ? hgvsc || null : null, hgvsp: findingKind === "small_variant" ? hgvsp || null : null,
      transcript: findingKind === "small_variant" ? transcript || null : null, variant_type: findingKind === "small_variant" ? variantType || null : null,
      oncokb_gene_present: findingKind !== "small_variant" || oncokb === "unknown" ? null : oncokb === "present", oncokb_gene_description: findingKind === "small_variant" ? oncokbDescription || null : null },
    { errorNotice: "inline" },
  ).then(response => response.data) })
  const reset = preview.reset
  useEffect(() => { reset() }, [documentId, revision, tier, findingKind, structural, diagnosis, gene, consequence, hgvsc, hgvsp, group, transcript, variantType, oncokb, oncokbDescription, reset])
  return <section aria-label="Bulk annotation preview" className="space-y-3">
    <h2 className="type-section-title">Annotation preview · Tier {tierNames[tier]}</h2>
    <p className="type-body-sm text-muted-foreground">Enter synthetic finding values to check matching and wording. No sample or annotation is created.</p>
    <label className="type-label block">Biological group<select aria-label="Annotation preview Biological group" className="paper-inset mt-1 w-full rounded-lg p-2 type-body" value={group} onChange={event => setGroup(event.target.value)}><option value="">Use assay biological group</option>{groups.map(item => <option key={item.group_id} value={item.group_id}>{[...item.path_names].reverse().join(" › ")} ({item.group_id}){item.is_active ? "" : " · inactive"}</option>)}</select></label>
    <label className="type-label block">Diagnosis<Input className="mt-1" aria-label="Annotation preview Diagnosis" value={diagnosis} onChange={event => setDiagnosis(event.target.value)} /></label>
    {findingKind === "small_variant" && <>{([["Gene", gene, setGene], ["Consequence", consequence, setConsequence], ["HGVS c", hgvsc, setHgvsc], ["HGVS p", hgvsp, setHgvsp], ["Selected transcript", transcript, setTranscript], ["Variant class", variantType, setVariantType], ["OncoKB gene description", oncokbDescription, setOncokbDescription]] as const).map(([label, value, setValue]) => <label key={label} className="type-label block">{label}<Input className="mt-1" aria-label={`Annotation preview ${label}`} value={value} onChange={event => setValue(event.target.value)} /></label>)}
    <label className="type-label block">Simulated OncoKB status<select aria-label="Annotation preview OncoKB status" className="paper-inset mt-1 w-full rounded-lg p-2 type-body" value={oncokb} onChange={event => setOncokb(event.target.value)}><option value="unknown">Unknown</option><option value="present">Gene present</option><option value="absent">Gene absent</option></select></label>
    <p className="type-meta text-muted-foreground">OncoKB values here are simulated. Bulk actions read the local knowledgebase.</p>
    </>}
    {findingKind !== "small_variant" && structuralFields.map(([key, label]) => <label key={key} className="type-label block">{label}<Input className="mt-1" value={structural[key] || ""} type={["start", "end"].includes(key) ? "number" : "text"} min={0} step={1} onChange={event => setStructural(current => ({ ...current, [key]: event.target.value }))} /></label>)}
    <Button type="button" variant="outline" disabled={!saved || preview.isPending} onClick={() => preview.mutate()}>Preview annotation</Button>
    {!saved && <p role="status" className="type-meta text-muted-foreground">Waiting for valid edits to save.</p>}
    {preview.error && <p role="alert" className="type-body-sm text-destructive">{preview.error instanceof Error ? preview.error.message : "Annotation preview failed."}</p>}
    {preview.data && <div className="paper-inset space-y-2 rounded-lg p-3"><p className="type-meta">{preview.data.rule_id ? `Matched template: ${preview.data.rule_id}` : "No enabled template matched. Bulk tiering will add no automatic annotation text."}</p>{preview.data.text && <MarkdownText text={preview.data.text} />}</div>}
  </section>
}
