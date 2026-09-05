import { useEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent, type PointerEvent } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import {
  Beaker,
  BookOpenCheck,
  Check,
  CirclePlus,
  CopyPlus,
  FileCheck2,
  GitCompareArrows,
  GripVertical,
  History,
  ListFilter,
  Plus,
  PanelLeftClose,
  PanelLeftOpen,
  Save,
  Search,
  Send,
  ShieldCheck,
  Trash2,
} from "lucide-react"

import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"
import { hasPermission, useCurrentUserAccess } from "@/lib/access-control"
import { cn } from "@/lib/utils"
import type {
  ClinicalRule,
  ClinicalRuleAssayOption,
  ClinicalRuleRevision,
  ClinicalRuleSet,
  Condition,
  FactDefinition,
  OutputNode,
  RuleBlock,
} from "./clinical-rules-types"
import {
  CLINICAL_RULE_STATUS_LABELS,
  clinicalConditionTone,
  clinicalRuleSectionTone,
} from "./clinical-rules-visuals"
import { ClinicalRuleStatusBadge } from "./ClinicalRuleStatusBadge"

const OPERATOR_LABELS: Record<string, string> = {
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

const ANALYSES = {
  dna: ["SNV", "CNV", "TRANSLOCATION", "BIOMARKER", "CNV_PROFILE", "COVERAGE", "FUSION", "TMB", "PGX"],
  rna: ["FUSION", "EXPRESSION", "CLASSIFICATION", "QC", "PGX"],
} as const

const clone = <T,>(value: T): T => structuredClone(value)

function storedWidth(key: string, fallback: number) {
  if (typeof window === "undefined") return fallback
  try {
    const value = Number(window.localStorage.getItem(key))
    return Number.isFinite(value) && value > 0 ? value : fallback
  } catch {
    return fallback
  }
}

function ResizeDivider({
  label,
  width,
  setWidth,
  min,
  max,
  direction = 1,
}: {
  label: string
  width: number
  setWidth: (width: number) => void
  min: number
  max: number
  direction?: 1 | -1
}) {
  const start = useRef({ x: 0, width })
  const clamp = (value: number) => Math.min(max, Math.max(min, value))
  const update = (value: number) => {
    const nextWidth = clamp(value)
    setWidth(nextWidth)
    try {
      window.localStorage.setItem(`clinical-rules-width:${label}`, String(nextWidth))
    } catch {
      // Resizing remains available when browser storage is disabled.
    }
  }
  const finish = (event: PointerEvent<HTMLDivElement>) => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
  }
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return
    event.preventDefault()
    const delta = event.key === 'ArrowRight' ? 16 : -16
    update(width + delta * direction)
  }
  return <div role="separator" aria-label={label} aria-orientation="vertical" aria-valuemin={min} aria-valuemax={max} aria-valuenow={Math.round(width)} tabIndex={0} className="clinical-rules-divider" onKeyDown={onKeyDown} onPointerDown={(event) => { if (event.pointerType === "mouse" && event.button !== 0) return; start.current = { x: event.clientX, width }; event.currentTarget.setPointerCapture(event.pointerId) }} onPointerMove={(event) => { if (event.currentTarget.hasPointerCapture(event.pointerId)) update(start.current.width + (event.clientX - start.current.x) * direction) }} onPointerUp={finish} onPointerCancel={finish}><GripVertical /></div>
}

type NewRuleSetScope = {
  asp_id: string
  subpanel_id: string
  analyte: "dna" | "rna"
  language: string
  name: string
}

const emptyRuleSetScope = (): NewRuleSetScope => ({
  asp_id: "",
  subpanel_id: "base",
  analyte: "dna",
  language: "sv",
  name: "",
})

const identifierPart = (value: string) => value
  .normalize("NFKD")
  .replace(/[\u0300-\u036f]/g, "")
  .toLowerCase()
  .replace(/[^a-z0-9]+/g, "_")
  .replace(/^_+|_+$/g, "")

const nextIdentifier = (base: string, used: Iterable<string>) => {
  const normalized = identifierPart(base) || "rule"
  const existing = new Set(used)
  if (!existing.has(normalized)) return normalized
  let suffix = 2
  while (existing.has(`${normalized}_${suffix}`)) suffix += 1
  return `${normalized}_${suffix}`
}

const nextOrdinal = (prefix: string, used: Iterable<string>) => {
  const existing = new Set(used)
  let ordinal = 1
  while (existing.has(`${prefix} ${ordinal}`)) ordinal += 1
  return ordinal
}

const nextOrder = (used: number[], interval: number) =>
  used.length ? Math.max(...used) + interval : interval

const generatedRuleSetName = (
  assay: ClinicalRuleAssayOption | undefined,
  subpanelId: string,
) => {
  if (!assay) return ""
  const subpanel = subpanelId.trim()
  const scope = subpanel && subpanel !== "base" ? ` - ${subpanel}` : ""
  return `${assay.display_name}${scope} clinical report rules`
}

const newRule = (
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

const newRuleBlock = (blocks: RuleBlock[]): RuleBlock => {
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
    match_strategy: "first_match",
    rules: [],
  }
  const existingRuleIds = blocks.flatMap((item) => item.rules.map((rule) => rule.rule_id))
  block.rules.push(newRule(block, existingRuleIds))
  return block
}

function newPredicate(facts: FactDefinition[]): Condition {
  const fact = facts[0]
  return { type: "predicate", fact: fact?.path || "finding.gene", operator: fact?.operators[0] || "eq", value: "" }
}

function parseValue(value: string, operator: string, fact?: FactDefinition): unknown {
  if (fact?.kind === "boolean") return value === "true"
  if (fact?.kind === "integer" || fact?.kind === "number") return Number(value)
  if (fact?.kind === "string_list" || ["in", "not_in", "overlaps", "between"].includes(operator)) {
    return value.split(",").map((item) => item.trim()).filter(Boolean)
  }
  return value
}

function valueText(value: unknown) {
  return Array.isArray(value) ? value.join(", ") : String(value ?? "")
}

function ConditionBuilder({
  value,
  facts,
  allFacts = facts,
  onChange,
  onRemove,
  depth = 0,
}: {
  value: Condition
  facts: FactDefinition[]
  allFacts?: FactDefinition[]
  onChange: (value: Condition) => void
  onRemove?: () => void
  depth?: number
}) {
  const replaceType = (type: Condition["type"]) => {
    if (type === "predicate") onChange(newPredicate(facts))
    else if (type === "all" || type === "any") onChange({ type, children: [newPredicate(facts)] })
    else if (type === "not") onChange({ type, child: newPredicate(facts) })
    else onChange({ type, collection: "findings", quantifier: "any", where: newPredicate(facts) })
  }
  return (
    <div className={cn("rounded-r-lg border-l-2 p-3", clinicalConditionTone(value.type), depth > 0 && "mt-2")}>
      <div className="flex flex-wrap items-center gap-2">
        <select className="paper-inset responsive-control-height rounded-lg px-2 text-sm" value={value.type} onChange={(event) => replaceType(event.target.value as Condition["type"])}>
          <option value="predicate">Condition</option>
          <option value="all">Match all</option>
          <option value="any">Match any</option>
          <option value="not">Exclude when</option>
          <option value="collection_match">Find in collection</option>
        </select>
        {onRemove && <Button type="button" variant="ghost" size="icon-sm" title="Remove condition" onClick={onRemove}><Trash2 /></Button>}
      </div>
      {value.type === "predicate" && (
        <PredicateEditor value={value} facts={facts} onChange={onChange} />
      )}
      {(value.type === "all" || value.type === "any") && (
        <div className="mt-2 space-y-2">
          {value.children.map((child, index) => (
            <ConditionBuilder
              key={index}
              value={child}
              facts={facts}
              allFacts={allFacts}
              depth={depth + 1}
              onChange={(next) => onChange({ ...value, children: value.children.map((item, childIndex) => childIndex === index ? next : item) })}
              onRemove={value.children.length > 1 ? () => onChange({ ...value, children: value.children.filter((_, childIndex) => childIndex !== index) }) : undefined}
            />
          ))}
          <Button type="button" variant="outline" size="sm" onClick={() => onChange({ ...value, children: [...value.children, newPredicate(facts)] })}><Plus /> Add condition</Button>
        </div>
      )}
      {value.type === "not" && <ConditionBuilder value={value.child} facts={facts} allFacts={allFacts} depth={depth + 1} onChange={(child) => onChange({ ...value, child })} />}
      {value.type === "collection_match" && (
        <div className="mt-2 space-y-2">
          <div className="grid gap-2 sm:grid-cols-2">
            <label className="type-label">Collection<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={value.collection} onChange={(event) => onChange({ ...value, collection: event.target.value as typeof value.collection })}><option value="findings">Findings</option><option value="biomarkers">Biomarkers</option><option value="applied_gene_lists">Applied gene lists</option><option value="tier_summaries">Tier summaries</option></select></label>
            <label className="type-label">Match<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={value.quantifier} onChange={(event) => onChange({ ...value, quantifier: event.target.value as typeof value.quantifier })}><option value="any">At least one</option><option value="none">None</option><option value="all">Every item</option><option value="count">A specific count</option></select></label>
          </div>
          {value.quantifier === "count" && (
            <div className="grid gap-2 sm:grid-cols-[1fr_1fr]">
              <label className="type-label">Comparison<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={value.count?.operator || "gte"} onChange={(event) => onChange({ ...value, count: { operator: event.target.value as NonNullable<typeof value.count>["operator"], value: value.count?.value ?? 1 } })}><option value="eq">Exactly</option><option value="ne">Not equal to</option><option value="gt">More than</option><option value="gte">At least</option><option value="lt">Fewer than</option><option value="lte">At most</option></select></label>
              <label className="type-label">Number<Input className="mt-1" type="number" min={0} value={value.count?.value ?? 1} onChange={(event) => onChange({ ...value, count: { operator: value.count?.operator || "gte", value: Number(event.target.value) } })} /></label>
            </div>
          )}
          <ConditionBuilder value={value.where} facts={allFacts.filter((fact) => fact.scopes.includes("each_item"))} allFacts={allFacts} depth={depth + 1} onChange={(where) => onChange({ ...value, where })} />
        </div>
      )}
    </div>
  )
}

function PredicateEditor({ value, facts, onChange }: { value: Extract<Condition, { type: "predicate" }>; facts: FactDefinition[]; onChange: (value: Condition) => void }) {
  const fact = facts.find((item) => item.path === value.fact) || facts[0]
  const operators = fact?.operators || ["eq"]
  const noValue = ["is_empty", "is_unknown"].includes(value.operator)
  return (
    <div className="mt-2 grid gap-2 lg:grid-cols-[1.2fr_1fr_1.4fr]">
      <select className="paper-inset rounded-lg p-2 text-sm" value={value.fact} onChange={(event) => { const selected = facts.find((item) => item.path === event.target.value); onChange({ type: "predicate", fact: event.target.value, operator: selected?.operators[0] || "eq", value: selected?.kind === "boolean" ? true : "" }) }}>
        {facts.map((item) => <option key={item.path} value={item.path}>{item.label}</option>)}
      </select>
      <select className="paper-inset rounded-lg p-2 text-sm" value={value.operator} onChange={(event) => onChange({ ...value, operator: event.target.value })}>
        {operators.map((operator) => <option key={operator} value={operator}>{OPERATOR_LABELS[operator] || operator}</option>)}
      </select>
      {!noValue && (fact?.kind === "boolean" || value.operator === "exists" ? (
        <select className="paper-inset rounded-lg p-2 text-sm" value={String(value.value ?? true)} onChange={(event) => onChange({ ...value, value: event.target.value === "true" })}><option value="true">Yes</option><option value="false">No</option></select>
      ) : (
        <div className="relative"><Input aria-label="Condition value" value={valueText(value.value)} onChange={(event) => onChange({ ...value, value: parseValue(event.target.value, value.operator, fact) })} />{fact?.unit && <span className="absolute right-2 top-2 text-xs text-muted-foreground">{fact.unit}</span>}</div>
      ))}
    </div>
  )
}

function OutputEditor({ nodes, facts, onChange }: { nodes: OutputNode[]; facts: FactDefinition[]; onChange: (nodes: OutputNode[]) => void }) {
  const replace = (index: number, node: OutputNode) => onChange(nodes.map((item, itemIndex) => itemIndex === index ? node : item))
  const scalarFacts = facts.filter((fact) => !["string_list", "object_list"].includes(fact.kind))
  const listFacts = facts.filter((fact) => fact.kind === "string_list")
  const numberFacts = facts.filter((fact) => ["integer", "number"].includes(fact.kind))
  return (
    <div className="space-y-2">
      {nodes.map((node, index) => (
        <div key={index} className="flex items-start gap-2 rounded-lg border border-border/70 bg-background/70 p-2">
          <div className="min-w-0 flex-1">
            {node.type === "text" && <textarea className="paper-inset min-h-24 w-full resize-y rounded-lg p-2 text-sm" value={node.value} onChange={(event) => replace(index, { ...node, value: event.target.value })} />}
            {node.type === "fact" && <div className="grid gap-2 sm:grid-cols-[1fr_auto_auto]"><select className="paper-inset rounded-lg p-2 text-sm" value={node.path} onChange={(event) => replace(index, { ...node, path: event.target.value })}>{scalarFacts.map((fact) => <option key={fact.path} value={fact.path}>{fact.label}</option>)}</select><select aria-label="Value format" className="paper-inset rounded-lg p-2 text-sm" value={node.formatter} onChange={(event) => replace(index, { ...node, formatter: event.target.value as typeof node.formatter })}><option value="text">As entered</option><option value="gene_symbol">Gene symbol</option><option value="upper">Uppercase</option><option value="lower">Lowercase</option></select><select aria-label="Missing value behavior" className="paper-inset rounded-lg p-2 text-sm" value={node.missing} onChange={(event) => replace(index, { ...node, missing: event.target.value as typeof node.missing })}><option value="error">Require value</option><option value="omit">Omit if missing</option></select></div>}
            {node.type === "list" && <div className="grid gap-2 sm:grid-cols-[1fr_9rem_auto]"><select className="paper-inset rounded-lg p-2 text-sm" value={node.path} onChange={(event) => replace(index, { ...node, path: event.target.value })}>{listFacts.map((fact) => <option key={fact.path} value={fact.path}>{fact.label}</option>)}</select><Input aria-label="List conjunction" value={node.conjunction} onChange={(event) => replace(index, { ...node, conjunction: event.target.value })} /><select aria-label="Missing list behavior" className="paper-inset rounded-lg p-2 text-sm" value={node.missing} onChange={(event) => replace(index, { ...node, missing: event.target.value as typeof node.missing })}><option value="error">Require list</option><option value="omit">Omit if missing</option></select></div>}
            {node.type === "number" && <div className="grid gap-2 sm:grid-cols-[1fr_7rem_7rem_auto]"><select className="paper-inset rounded-lg p-2 text-sm" value={node.path} onChange={(event) => replace(index, { ...node, path: event.target.value })}>{numberFacts.map((fact) => <option key={fact.path} value={fact.path}>{fact.label}</option>)}</select><label className="type-label">Decimals<Input className="mt-1" type="number" min={0} max={6} value={node.precision} onChange={(event) => replace(index, { ...node, precision: Number(event.target.value) })} /></label><label className="type-label">Unit<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={node.unit} onChange={(event) => replace(index, { ...node, unit: event.target.value as typeof node.unit })}><option value="">None</option><option value="%">%</option><option value="x">x</option></select></label><select aria-label="Missing number behavior" className="paper-inset self-end rounded-lg p-2 text-sm" value={node.missing} onChange={(event) => replace(index, { ...node, missing: event.target.value as typeof node.missing })}><option value="error">Require number</option><option value="omit">Omit if missing</option></select></div>}
            {node.type === "message" && <div className="grid gap-2"><select className="paper-inset rounded-lg p-2 text-sm" value={node.count_path} onChange={(event) => replace(index, { ...node, count_path: event.target.value })}>{numberFacts.map((fact) => <option key={fact.path} value={fact.path}>{fact.label}</option>)}</select><Input aria-label="Text when count is one" placeholder="Text when count is one" value={node.one} onChange={(event) => replace(index, { ...node, one: event.target.value })} /><Input aria-label="Text for other counts" placeholder="Text for other counts" value={node.other} onChange={(event) => replace(index, { ...node, other: event.target.value })} /></div>}
            {node.type === "renderer" && <select className="paper-inset w-full rounded-lg p-2 text-sm" value={node.name} onChange={(event) => replace(index, { type: "renderer", name: event.target.value as typeof node.name })}><option value="dna_report_intro">DNA analysis introduction</option><option value="tier_summary">Tiered variant summary</option><option value="fusion_summary">Fusion summary</option></select>}
            {node.type === "paragraph_break" && <p className="py-2 text-xs font-medium text-muted-foreground">Paragraph break</p>}
          </div>
          <Button type="button" variant="ghost" size="icon-sm" title="Remove output part" disabled={nodes.length === 1} onClick={() => onChange(nodes.filter((_, itemIndex) => itemIndex !== index))}><Trash2 /></Button>
        </div>
      ))}
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" size="sm" onClick={() => onChange([...nodes, { type: "text", value: "New report text" }])}><Plus /> Text</Button>
        <Button type="button" variant="outline" size="sm" disabled={!scalarFacts.length} onClick={() => onChange([...nodes, { type: "fact", path: scalarFacts[0]?.path || "finding.gene", formatter: "text", missing: "error" }])}><CirclePlus /> Value</Button>
        <Button type="button" variant="outline" size="sm" disabled={!listFacts.length} onClick={() => onChange([...nodes, { type: "list", path: listFacts[0]?.path || "finding.genes", conjunction: "and", formatter: "text", missing: "error" }])}><ListFilter /> List</Button>
        <Button type="button" variant="outline" size="sm" disabled={!numberFacts.length} onClick={() => onChange([...nodes, { type: "number", path: numberFacts[0]?.path || "aggregates.finding_count", precision: 0, unit: "", missing: "error" }])}><CirclePlus /> Number</Button>
        <Button type="button" variant="outline" size="sm" disabled={!numberFacts.length} onClick={() => onChange([...nodes, { type: "message", count_path: numberFacts[0]?.path || "aggregates.finding_count", one: "One finding", other: "Multiple findings" }])}><CirclePlus /> Singular / plural</Button>
        <Button type="button" variant="outline" size="sm" onClick={() => onChange([...nodes, { type: "paragraph_break" }])}><BookOpenCheck /> Paragraph</Button>
        <Button type="button" variant="outline" size="sm" onClick={() => onChange([...nodes, { type: "renderer", name: "tier_summary" }])}><ListFilter /> Structured summary</Button>
      </div>
    </div>
  )
}

function outputPreview(nodes: OutputNode[], facts: FactDefinition[]) {
  return nodes.map((node) => {
    if (node.type === "text") return node.value
    if (node.type === "paragraph_break") return "\n\n"
    if (node.type === "renderer") return `[${node.name.replaceAll("_", " ")}]`
    const path = "count_path" in node ? node.count_path : "path" in node ? node.path : ""
    return `[${facts.find((fact) => fact.path === path)?.label || path}]`
  }).join("")
}

function RuleEditor({ rule, block, facts, change }: { rule: ClinicalRule; block: RuleBlock; facts: FactDefinition[]; change: (rule: ClinicalRule) => void }) {
  const scopedFacts = facts.filter((fact) => fact.scopes.includes(block.evaluation.mode))
  return (
    <div className="space-y-5 p-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="type-label">Clinical rule name<Input className="mt-1" value={rule.name} onChange={(event) => change({ ...rule, name: event.target.value })} /></label>
        <label className="type-label">Rule identifier<Input className="mt-1" value={rule.rule_id} onChange={(event) => change({ ...rule, rule_id: event.target.value })} /></label>
      </div>
      <section><h3 className="type-section-title mb-2">When this text applies</h3>{rule.condition ? <ConditionBuilder value={rule.condition} facts={scopedFacts} allFacts={facts} onChange={(condition) => change({ ...rule, condition })} onRemove={() => change({ ...rule, condition: null })} /> : <Button type="button" variant="outline" onClick={() => change({ ...rule, condition: newPredicate(scopedFacts) })}><Plus /> Add condition</Button>}</section>
      <section><h3 className="type-section-title mb-2">Report text</h3><OutputEditor nodes={rule.output} facts={scopedFacts} onChange={(output) => change({ ...rule, output })} /></section>
      <label className="type-label block">Clinical rationale<textarea className="paper-inset mt-1 min-h-20 w-full rounded-lg p-2 text-sm" value={rule.rationale || ""} onChange={(event) => change({ ...rule, rationale: event.target.value || null })} /></label>
    </div>
  )
}

export function ClinicalRulesPage() {
  const queryClient = useQueryClient()
  const access = useCurrentUserAccess()
  const [search, setSearch] = useState("")
  const [status, setStatus] = useState("")
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [draft, setDraft] = useState<ClinicalRuleSet | null>(null)
  const [selectedBlock, setSelectedBlock] = useState(0)
  const [selectedRule, setSelectedRule] = useState(0)
  const [dirty, setDirty] = useState(false)
  const [creating, setCreating] = useState(false)
  const [newScope, setNewScope] = useState<NewRuleSetScope>(emptyRuleSetScope)
  const [newNameEdited, setNewNameEdited] = useState(false)
  const [ruleListCollapsed, setRuleListCollapsed] = useState(false)
  const [sectionsCollapsed, setSectionsCollapsed] = useState(false)
  const [ruleListWidth, setRuleListWidth] = useState(() => storedWidth("clinical-rules-width:Resize rule-set list", 272))
  const [sectionsWidth, setSectionsWidth] = useState(() => storedWidth("clinical-rules-width:Resize report sections", 208))
  const [previewWidth, setPreviewWidth] = useState(() => storedWidth("clinical-rules-width:Resize text preview", 380))
  const [historyOpen, setHistoryOpen] = useState(false)
  const [selectedRevision, setSelectedRevision] = useState<number | null>(null)
  const editGeneration = useRef(0)

  const listQuery = useQuery({ queryKey: ["clinical-rule-sets", search, status], queryFn: () => api.get<{ items: ClinicalRuleSet[] }>(`/admin/clinical-rule-sets?q=${encodeURIComponent(search)}${status ? `&status=${status}` : ""}`).then((response) => response.data) })
  const factsQuery = useQuery({ queryKey: ["clinical-rule-facts"], queryFn: () => api.get<{ items: FactDefinition[] }>("/admin/clinical-rule-sets/facts").then((response) => response.data) })
  const optionsQuery = useQuery({ queryKey: ["clinical-rule-authoring-options"], queryFn: () => api.get<{ assays: ClinicalRuleAssayOption[] }>("/admin/clinical-rule-sets/authoring-options").then((response) => response.data) })
  const versionQuery = useQuery({ queryKey: ["clinical-rule-set", selectedId], enabled: Boolean(selectedId), queryFn: () => api.get<ClinicalRuleSet>(`/admin/clinical-rule-sets/versions/${selectedId}`).then((response) => response.data) })
  const revisionsQuery = useQuery({ queryKey: ["clinical-rule-revisions", selectedId], enabled: Boolean(selectedId) && historyOpen, queryFn: () => api.get<{ items: ClinicalRuleRevision[] }>(`/admin/clinical-rule-sets/versions/${selectedId}/revisions`).then((response) => response.data) })
  useEffect(() => {
    if (selectedId && versionQuery.data?._id === selectedId) {
      setDraft(clone(versionQuery.data))
      setDirty(false)
      setSelectedBlock(0)
      setSelectedRule(0)
      setSelectedRevision(null)
    }
  }, [selectedId, versionQuery.data])
  const facts = useMemo(() => factsQuery.data?.items || [], [factsQuery.data?.items])

  const saveMutation = useMutation({
    mutationFn: ({ document, generation }: { document: ClinicalRuleSet; generation: number }) => api.patch<ClinicalRuleSet>(`/admin/clinical-rule-sets/drafts/${document._id}`, { revision: document.revision, name: document.name, analysis_declarations: document.analysis_declarations, terminology: document.terminology, blocks: document.blocks, test_cases: document.test_cases, references: document.references, change_summary: document.change_summary }).then((response) => ({ document: response.data, generation })),
    onSuccess: ({ document, generation }) => { setDraft((current) => generation === editGeneration.current ? clone(document) : current ? { ...current, revision: document.revision } : current); if (generation === editGeneration.current) setDirty(false); queryClient.invalidateQueries({ queryKey: ["clinical-rule-sets"] }); queryClient.invalidateQueries({ queryKey: ["clinical-rule-revisions", document._id] }) },
  })
  const saveDraft = saveMutation.mutate
  const savePending = saveMutation.isPending
  useEffect(() => {
    if (!dirty || draft?.status !== "draft" || savePending) return
    const generation = editGeneration.current
    const timer = window.setTimeout(() => saveDraft({ document: draft, generation }), 800)
    return () => window.clearTimeout(timer)
  }, [dirty, draft, saveDraft, savePending])

  const mutateDraft = (change: (document: ClinicalRuleSet) => void) => {
    setDraft((current) => { if (!current || current.status !== "draft") return current; const next = clone(current); change(next); return next })
    editGeneration.current += 1
    setDirty(true)
  }
  const block = draft?.blocks[selectedBlock]
  const rule = block?.rules[selectedRule]
  const can = (permission: string) => hasPermission(access.data, permission)
  const workflowReady = !dirty && !saveMutation.isPending

  const beginCreation = () => {
    setSelectedId(null)
    setDraft(null)
    setSelectedBlock(0)
    setSelectedRule(0)
    setNewScope(emptyRuleSetScope())
    setNewNameEdited(false)
    setCreating(true)
    setHistoryOpen(false)
  }
  const cancelCreation = () => {
    setCreating(false)
    setNewScope(emptyRuleSetScope())
    setNewNameEdited(false)
  }
  const openRuleSet = (documentId: string) => {
    setCreating(false)
    setDraft(null)
    setSelectedBlock(0)
    setSelectedRule(0)
    setSelectedId(documentId)
    setHistoryOpen(false)
    setSelectedRevision(null)
  }

  const actionMutation = useMutation({ mutationFn: ({ path, body = {} }: { path: string; body?: Record<string, unknown> }) => api.post<ClinicalRuleSet>(path, body).then((response) => response.data), onSuccess: (document) => { setSelectedId(document._id); setDraft(clone(document)); setDirty(false); setCreating(false); queryClient.invalidateQueries({ queryKey: ["clinical-rule-sets"] }); queryClient.invalidateQueries({ queryKey: ["clinical-rule-revisions", document._id] }) } })
  const createRevision = () => draft && actionMutation.mutate({ path: "/admin/clinical-rule-sets/drafts", body: { source_version_id: draft._id } })
  const createRuleSet = () => actionMutation.mutate({ path: "/admin/clinical-rule-sets/drafts", body: { scope: { asp_id: newScope.asp_id.trim(), subpanel_id: newScope.subpanel_id.trim(), analyte: newScope.analyte, language: newScope.language.trim() }, name: newScope.name.trim() } })
  const lifecycleAction = (action: string, body: Record<string, unknown> = { reason: draft?.change_summary || "Workflow transition" }) => draft && actionMutation.mutate({ path: `/admin/clinical-rule-sets/drafts/${draft._id}/${action}`, body })
  const retireRuleSet = () => draft && actionMutation.mutate({ path: `/admin/clinical-rule-sets/versions/${draft._id}/retire`, body: { reason: draft.change_summary || "Clinical rule set retired" } })

  const validationQuery = useQuery({ queryKey: ["clinical-rule-validation", draft?._id, draft?.revision], enabled: false, queryFn: () => api.post<{ valid: boolean; errors: string[]; warnings: string[] }>(`/admin/clinical-rule-sets/drafts/${draft?._id}/validate`).then((response) => response.data) })
  const selectedPreview = useMemo(() => rule ? outputPreview(rule.output, facts) : "Select a rule to preview its report text.", [rule, facts])
  const revisionItems = revisionsQuery.data?.items || []
  const historicalRevision = revisionItems.find((item) => item.revision === selectedRevision) || revisionItems[0]

  if (listQuery.isLoading || factsQuery.isLoading || optionsQuery.isLoading) return <PageShell eyebrow="Clinical reporting" title="Report Rules"><AppLoader label="Loading clinical rules" /></PageShell>
  return (
    <PageShell eyebrow="Clinical reporting" title="Report Rules" description="Author, review, validate, and publish governed report wording." actions={<>{dirty || saveMutation.isPending ? <Badge variant="outline"><Save /> {saveMutation.isPending ? "Saving" : "Unsaved"}</Badge> : draft?.status === "draft" ? <Badge variant="outline"><Check /> Saved</Badge> : null}{can("clinical_rules:test") && <Button variant="outline" nativeButton={false} render={<Link to="/admin/clinical-rules/testing" />}><Beaker /> Test rules</Button>}{can("clinical_rules:draft") && !creating && <Button variant="outline" disabled={!workflowReady} onClick={beginCreation}><Plus /> New rule set</Button>}{draft?.status !== "draft" && draft && can("clinical_rules:draft") && <Button onClick={createRevision}><CopyPlus /> Create revision</Button>}</>}>
      {creating && (
        <section className="surface-panel mb-3 p-4" aria-label="Create clinical rule set">
          <div className="grid gap-3 md:grid-cols-5">
            <label className="type-label">Assay<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={newScope.asp_id} onChange={(event) => { const assay = optionsQuery.data?.assays.find((item) => item.asp_id === event.target.value); setNewScope((current) => ({ ...current, asp_id: event.target.value, analyte: assay?.analyte || "dna", name: newNameEdited ? current.name : generatedRuleSetName(assay, current.subpanel_id) })) }}><option value="">Select assay</option>{(optionsQuery.data?.assays || []).map((assay) => <option key={assay.asp_id} value={assay.asp_id}>{assay.display_name} ({assay.asp_id})</option>)}</select></label>
            <label className="type-label">Subpanel<Input className="mt-1" value={newScope.subpanel_id} onChange={(event) => { const subpanelId = event.target.value; const assay = optionsQuery.data?.assays.find((item) => item.asp_id === newScope.asp_id); setNewScope((current) => ({ ...current, subpanel_id: subpanelId, name: newNameEdited ? current.name : generatedRuleSetName(assay, subpanelId) })) }} /></label>
            <label className="type-label">Analyte<Input className="mt-1 uppercase" value={newScope.analyte} readOnly /></label>
            <label className="type-label">Language<Input className="mt-1" value={newScope.language} onChange={(event) => setNewScope({ ...newScope, language: event.target.value })} /></label>
            <label className="type-label">Rule-set name<Input className="mt-1" value={newScope.name} onChange={(event) => { setNewNameEdited(true); setNewScope({ ...newScope, name: event.target.value }) }} /></label>
          </div>
          <div className="mt-3 flex justify-end gap-2"><Button variant="ghost" onClick={cancelCreation}>Cancel</Button><Button disabled={!newScope.asp_id.trim() || !newScope.subpanel_id.trim() || !newScope.name.trim() || actionMutation.isPending} onClick={createRuleSet}><CirclePlus /> Create draft</Button></div>
        </section>
      )}
      <div className={cn("clinical-rules-layout clinical-rules-workspace surface-panel overflow-hidden", ruleListCollapsed && "is-rule-list-collapsed")} style={{ "--rule-list-width": `${ruleListWidth}px`, "--preview-width": `${previewWidth}px` } as CSSProperties}>
        <aside className="flex min-h-0 min-w-0 flex-col border-b border-border xl:border-b-0">
          {ruleListCollapsed ? <button type="button" className="clinical-rules-rail" aria-label="Expand rule-set list" onClick={() => setRuleListCollapsed(false)}><PanelLeftOpen /><span>Rule sets</span></button> : <>
          <div className="space-y-2 border-b border-border p-3">
            <div className="flex items-center gap-1"><div className="relative min-w-0 flex-1"><Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" /><Input aria-label="Search clinical rules" className="pl-8" placeholder="Search rules" value={search} onChange={(event) => setSearch(event.target.value)} /></div><Button size="icon-sm" variant="ghost" title="Collapse rule-set list" aria-label="Collapse rule-set list" onClick={() => setRuleListCollapsed(true)}><PanelLeftClose /></Button></div>
            <select className="paper-inset w-full rounded-lg p-2 text-sm" value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All workflow states</option>{Object.entries(CLINICAL_RULE_STATUS_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
          </div>
          <nav className="min-h-0 flex-1 overflow-y-auto p-2" aria-label="Clinical rule sets">
            {(listQuery.data?.items || []).map((item) => <button type="button" key={item._id} disabled={!workflowReady} className={cn("mb-1 w-full rounded-lg p-3 text-left hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60", selectedId === item._id && "bg-primary/10 ring-1 ring-primary/30")} onClick={() => openRuleSet(item._id)}><span className="block truncate text-sm font-semibold">{item.name}</span><span className="mt-1 flex items-center justify-between gap-2 text-xs text-muted-foreground"><span>{item.scope.asp_id} · {item.scope.subpanel_id}</span><ClinicalRuleStatusBadge status={item.status} prefix={`v${item.content_version} `} /></span></button>)}
          </nav>
          </>}
        </aside>
        {!ruleListCollapsed && <ResizeDivider label="Resize rule-set list" width={ruleListWidth} setWidth={setRuleListWidth} min={210} max={440} />}
        <main className="grid min-h-0 min-w-0 grid-rows-[auto_minmax(0,1fr)] border-b border-border xl:border-b-0 xl:border-r">
          {!draft ? <div className="grid h-full place-items-center p-8 text-sm text-muted-foreground">Select a rule set to inspect or edit.</div> : <>
            <div className="border-b border-border bg-muted/35 p-3">
              <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0 flex-1">{draft.status === "draft" ? <Input aria-label="Rule-set name" className="max-w-xl font-semibold" value={draft.name} onChange={(event) => mutateDraft((document) => { document.name = event.target.value })} /> : <h2 className="font-semibold">{draft.name}</h2>}<p className="mt-1 text-xs text-muted-foreground">{draft.rule_set_id} · version {draft.content_version} · revision {draft.revision}</p></div><ClinicalRuleStatusBadge status={draft.status} /></div>
              {draft.status === "draft" && <div className="mt-3 flex flex-wrap gap-2"><Button size="sm" variant="outline" disabled={!workflowReady} onClick={() => validationQuery.refetch()}><FileCheck2 /> Validate</Button>{can("clinical_rules:submit") && <Button size="sm" disabled={!workflowReady} onClick={() => lifecycleAction("submit")}><Send /> Submit</Button>}</div>}
              {draft.status === "submitted" && can("clinical_rules:clinical_review") && <Button className="mt-3" size="sm" disabled={!workflowReady} onClick={() => lifecycleAction("start-clinical-review")}><ShieldCheck /> Start review</Button>}
              {draft.status === "in_clinical_review" && can("clinical_rules:clinical_review") && <div className="mt-3 flex gap-2"><Button size="sm" disabled={!workflowReady} onClick={() => lifecycleAction("clinical-review", { approve: true, reason: draft.change_summary || "Clinical content approved" })}><Check /> Approve</Button><Button size="sm" variant="outline" disabled={!workflowReady} onClick={() => lifecycleAction("clinical-review", { approve: false, reason: draft.change_summary || "Clinical changes required" })}>Reject</Button></div>}
              {draft.status === "approved" && can("clinical_rules:publish") && <Button className="mt-3" size="sm" onClick={() => lifecycleAction("publish")}><FileCheck2 /> Publish</Button>}
              {draft.status === "published" && can("clinical_rules:retire") && <Button className="mt-3" size="sm" variant="outline" onClick={retireRuleSet}><Trash2 /> Retire</Button>}
              {validationQuery.data && <div className={cn("mt-3 rounded-lg border p-2 text-xs", validationQuery.data.valid ? "border-success/40 bg-success/10" : "border-destructive/40 bg-destructive/10")}><strong>{validationQuery.data.valid ? "Ready for review" : "Validation requires attention"}</strong>{[...validationQuery.data.errors, ...validationQuery.data.warnings].map((message) => <p key={message} className="mt-1">{message}</p>)}</div>}
            </div>
            <div className={cn("clinical-rules-editor-layout min-h-0", sectionsCollapsed && "is-sections-collapsed")} style={{ "--sections-width": `${sectionsWidth}px` } as CSSProperties}>
              <aside className={cn("min-h-0 border-b border-border bg-muted/15 md:border-b-0", !sectionsCollapsed && "overflow-y-auto p-2")}>
                {sectionsCollapsed ? <div className="clinical-rules-section-rail"><Button type="button" variant="ghost" size="icon-sm" title="Expand report sections" aria-label="Expand report sections" onClick={() => setSectionsCollapsed(false)}><PanelLeftOpen /></Button><nav aria-label="Collapsed report sections">{draft.blocks.map((item, index) => { const tone = clinicalRuleSectionTone(index); return <button key={item.block_id} type="button" title={item.section} aria-label={`Select section ${item.section}`} className={cn("clinical-rules-section-tab", tone.rail, selectedBlock === index && "is-active")} onClick={() => { setSelectedBlock(index); setSelectedRule(0) }}><span>{item.section}</span></button> })}</nav></div> : <>
                <div className="mb-2 flex items-center justify-between gap-2"><span className="type-label">Sections</span><Button size="icon-sm" variant="ghost" title="Collapse report sections" aria-label="Collapse report sections" onClick={() => setSectionsCollapsed(true)}><PanelLeftClose /></Button></div>
                {draft.blocks.map((item, index) => { const tone = clinicalRuleSectionTone(index); return <div key={item.block_id} className="mb-1 flex items-center gap-1"><button type="button" className={cn("min-w-0 flex-1 rounded-md border p-2 text-left text-sm", selectedBlock === index ? tone.surface : "border-transparent hover:bg-muted")} onClick={() => { setSelectedBlock(index); setSelectedRule(0) }}><span className="block truncate font-medium">{item.section}</span><span className="text-xs text-muted-foreground">{item.rules.length} rules · {item.evaluation.mode.replaceAll("_", " ")}</span></button>{draft.status === "draft" && <Button type="button" variant="ghost" size="icon-sm" title="Remove section" onClick={() => mutateDraft((document) => { document.blocks.splice(index, 1); setSelectedBlock(Math.max(0, Math.min(selectedBlock, document.blocks.length - 1))); setSelectedRule(0) })}><Trash2 /></Button>}</div> })}
                {draft.status === "draft" && <Button className="mt-2 w-full" variant="outline" size="sm" onClick={() => mutateDraft((document) => document.blocks.push(newRuleBlock(document.blocks)))}><Plus /> Add section</Button>}
                </>}
              </aside>
              {!sectionsCollapsed && <ResizeDivider label="Resize report sections" width={sectionsWidth} setWidth={setSectionsWidth} min={160} max={360} />}
              <div className="min-h-0 min-w-0 overflow-y-auto">
                {block && <div className="space-y-3 border-b border-border p-3">
                  {draft.status === "draft" && <div className="grid gap-2 lg:grid-cols-5">
                    <label className="type-label">Section<Input className="mt-1" value={block.section} onChange={(event) => mutateDraft((document) => { document.blocks[selectedBlock].section = event.target.value; document.blocks[selectedBlock].name = event.target.value })} /></label>
                    <label className="type-label">Section identifier<Input className="mt-1" value={block.block_id} onChange={(event) => mutateDraft((document) => { document.blocks[selectedBlock].block_id = event.target.value })} /></label>
                    <label className="type-label">Analysis<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={block.analysis || ""} onChange={(event) => mutateDraft((document) => { document.blocks[selectedBlock].analysis = event.target.value || null })}><option value="">Whole report</option>{Object.keys(draft.analysis_declarations).map((analysis) => <option key={analysis} value={analysis}>{analysis}</option>)}</select></label>
                    <label className="type-label">Evaluate<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={block.evaluation.mode} onChange={(event) => mutateDraft((document) => { const mode = event.target.value as RuleBlock["evaluation"]["mode"]; document.blocks[selectedBlock].evaluation = mode === "each_item" ? { mode, collection: "findings" } : { mode, collection: null } })}><option value="once">Once per report</option><option value="each_finding">For each finding</option><option value="each_item">For each collection item</option></select></label>
                    <label className="type-label">Match behavior<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={block.match_strategy} onChange={(event) => mutateDraft((document) => { document.blocks[selectedBlock].match_strategy = event.target.value as RuleBlock["match_strategy"] })}><option value="first_match">First match</option><option value="all_matches">All matches</option><option value="exactly_one">Exactly one</option><option value="at_most_one">At most one</option></select></label>
                  </div>}
                  {draft.status === "draft" && block.evaluation.mode === "each_item" && <label className="type-label block max-w-xs">Collection<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={block.evaluation.collection || "findings"} onChange={(event) => mutateDraft((document) => { document.blocks[selectedBlock].evaluation.collection = event.target.value as NonNullable<RuleBlock["evaluation"]["collection"]> })}><option value="findings">Findings</option><option value="biomarkers">Biomarkers</option><option value="applied_gene_lists">Applied gene lists</option><option value="tier_summaries">Tier summaries</option></select></label>}
                  {draft.status === "draft" && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={block.show_heading} onChange={(event) => mutateDraft((document) => { document.blocks[selectedBlock].show_heading = event.target.checked })} /> Show section heading</label>}
                  <div className="flex gap-2 overflow-x-auto">{block.rules.map((item, index) => <div key={item.rule_id} className={cn("flex shrink-0 items-center rounded-md", selectedRule === index ? "bg-primary text-primary-foreground" : "bg-muted")}><button type="button" className="px-3 py-1.5 text-sm" onClick={() => setSelectedRule(index)}>{item.name}</button>{draft.status === "draft" && block.rules.length > 1 && <Button type="button" variant="ghost" size="icon-sm" title="Remove rule" onClick={() => mutateDraft((document) => { document.blocks[selectedBlock].rules.splice(index, 1); setSelectedRule(Math.max(0, Math.min(selectedRule, document.blocks[selectedBlock].rules.length - 1))) })}><Trash2 /></Button>}</div>)}{draft.status === "draft" && <Button className="shrink-0" variant="outline" size="sm" onClick={() => mutateDraft((document) => { const currentBlock = document.blocks[selectedBlock]; const allRuleIds = document.blocks.flatMap((item) => item.rules.map((itemRule) => itemRule.rule_id)); currentBlock.rules.push(newRule(currentBlock, allRuleIds)); setSelectedRule(currentBlock.rules.length - 1) })}><Plus /> Add rule</Button>}</div>
                </div>}
                {rule && block ? <RuleEditor rule={rule} block={block} facts={facts} change={(next) => mutateDraft((document) => { document.blocks[selectedBlock].rules[selectedRule] = next })} /> : <div className="p-8 text-sm text-muted-foreground">This rule set does not have an authored section yet.</div>}
              </div>
            </div>
          </>}
        </main>
        <ResizeDivider label="Resize text preview" width={previewWidth} setWidth={setPreviewWidth} min={280} max={720} direction={-1} />
        <aside className="min-h-0 min-w-0 overflow-y-auto bg-muted/10 p-4">
          <div className="flex items-center justify-between"><h2 className="type-section-title">Live text preview</h2><GitCompareArrows className="h-4 w-4 text-primary" /></div>
          <div className={cn("mt-3 whitespace-pre-wrap rounded-lg border p-4 text-sm leading-relaxed", clinicalRuleSectionTone(selectedBlock).surface)}>{selectedPreview}</div>
          {draft?.status === "draft" && <section className="mt-5 border-t border-border pt-4"><h2 className="type-section-title">Report analyses</h2><div className="mt-2 space-y-2">{ANALYSES[draft.scope.analyte].map((analysis) => <label key={analysis} className="flex items-center justify-between gap-3 text-sm"><span>{analysis}</span><select className="paper-inset rounded-lg p-1.5 text-xs" value={draft.analysis_declarations[analysis]?.narrative || "undeclared"} onChange={(event) => mutateDraft((document) => { if (event.target.value === "undeclared") delete document.analysis_declarations[analysis]; else document.analysis_declarations[analysis] = { narrative: event.target.value as "enabled" | "none" } })}><option value="undeclared">Not declared</option><option value="enabled">Generate text</option><option value="none">No narrative</option></select></label>)}</div></section>}
          {draft?.status === "draft" && <label className="type-label mt-5 block">Change summary<textarea className="paper-inset mt-1 min-h-24 w-full rounded-lg p-2 text-sm" value={draft.change_summary} onChange={(event) => mutateDraft((document) => { document.change_summary = event.target.value })} /></label>}
          {draft?.review?.clinical_reviewer && <div className="mt-5 border-t border-border pt-4 text-xs"><p className="font-semibold">Clinical review</p><p className="mt-1 text-muted-foreground">Reviewer: {draft.review.clinical_reviewer}</p>{draft.review.clinical_decision_reason && <p className="mt-1">{draft.review.clinical_decision_reason}</p>}</div>}
          {draft && <section className="mt-5 border-t border-border pt-4">
            <Button className="w-full justify-between" type="button" variant="outline" onClick={() => setHistoryOpen((current) => !current)}><span className="flex items-center gap-2"><History /> Revision history</span><span className="text-xs">r{draft.revision}</span></Button>
            {historyOpen && <div className="mt-3 space-y-3">
              {revisionsQuery.isLoading ? <AppLoader label="Loading revision history" /> : revisionItems.length === 0 ? <p className="text-xs text-muted-foreground">No immutable baseline has been captured for this version.</p> : <>
                <div className="flex gap-2 overflow-x-auto pb-1" aria-label="Rule-set revisions">{revisionItems.map((item) => <button type="button" key={item.revision} className={cn("shrink-0 rounded-md border px-2 py-1 text-xs", historicalRevision?.revision === item.revision ? "border-primary bg-primary/10 text-primary" : "border-border bg-background")} onClick={() => setSelectedRevision(item.revision)}>r{item.revision}</button>)}</div>
                {historicalRevision && <div className="rounded-lg border border-border bg-background p-3 text-xs">
                  <div className="flex flex-wrap items-center justify-between gap-2"><ClinicalRuleStatusBadge status={historicalRevision.document.status} /><time dateTime={historicalRevision.occurred_at}>{new Date(historicalRevision.occurred_at).toLocaleString()}</time></div>
                  <p className="mt-2 font-semibold">{historicalRevision.action.replaceAll("_", " ")}</p>
                  <p className="mt-1 text-muted-foreground">{historicalRevision.actor}</p>
                  {historicalRevision.reason && <p className="mt-2">{historicalRevision.reason}</p>}
                  <dl className="mt-3 grid grid-cols-[auto_minmax(0,1fr)] gap-x-2 gap-y-1 border-t border-border pt-3"><dt>Version</dt><dd>v{historicalRevision.content_version}, revision {historicalRevision.revision}</dd><dt>Hash</dt><dd className="truncate font-mono" title={historicalRevision.revision_hash}>{historicalRevision.revision_hash}</dd><dt>Previous</dt><dd className="truncate font-mono" title={historicalRevision.previous_revision_hash || "First preserved revision"}>{historicalRevision.previous_revision_hash || "First preserved revision"}</dd></dl>
                  <div className="mt-3 space-y-2 border-t border-border pt-3">{historicalRevision.document.blocks.length === 0 ? <p className="text-muted-foreground">No report sections in this revision.</p> : historicalRevision.document.blocks.map((historyBlock) => <div key={historyBlock.block_id}><p className="font-semibold">{historyBlock.section}</p>{historyBlock.rules.map((historyRule) => <div key={historyRule.rule_id} className="mt-1 rounded-md bg-muted/40 p-2"><p className="font-medium">{historyRule.name}</p><p className="mt-1 whitespace-pre-wrap text-muted-foreground">{outputPreview(historyRule.output, facts)}</p><details className="mt-2"><summary className="cursor-pointer text-primary">Condition and exact definition</summary><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-all rounded bg-muted p-2 font-mono text-xs">{JSON.stringify(historyRule, null, 2)}</pre></details></div>)}</div>)}</div>
                </div>}
              </>}
            </div>}
          </section>}
        </aside>
      </div>
    </PageShell>
  )
}
