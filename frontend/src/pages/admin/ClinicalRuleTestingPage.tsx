import { useMemo, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { Beaker, ChevronDown, ChevronUp, CircleCheck, CircleX, Search } from "lucide-react"

import { MarkdownText } from "@/components/comments/MarkdownText"
import { PageShell } from "@/components/layout/PageShell"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { cn } from "@/lib/utils"
import type { ClinicalRuleSet } from "./clinical-rules-types"
import { clinicalConditionTone, clinicalRuleSectionTone } from "./clinical-rules-visuals"
import { ClinicalRuleStatusBadge } from "./ClinicalRuleStatusBadge"

type TestSample = {
  id: string
  name: string
  asp_id?: string
  subpanel_id: string
  environment?: string
  omics_layer?: string
}

type ConditionTraceNode = {
  type: string
  label: string
  matched: boolean
  missing_facts: string[]
  children: ConditionTraceNode[]
}

type SamplePreview = {
  sample: TestSample
  rule_set: { rule_set_id: string; content_version: number; status: string }
  summary: string
  evaluation: {
    sections: Record<string, string[]>
    trace: Array<{
      block_id: string
      rule_id: string
      section: string
      matched: boolean
      item_identity?: string | null
      missing_facts: string[]
      rendered_text?: string | null
      condition_trace?: ConditionTraceNode | null
    }>
  }
  persisted: false
}

function ConditionTraceTree({ node }: { node: ConditionTraceNode }) {
  return (
    <div className={cn("mt-2 rounded-md border p-2", clinicalConditionTone(node.type))}>
      <div className="flex items-start gap-2 text-xs">
        {node.matched ? <CircleCheck className="clinical-trace-pass mt-0.5 h-3.5 w-3.5 shrink-0" /> : <CircleX className="clinical-trace-fail mt-0.5 h-3.5 w-3.5 shrink-0" />}
        <div><p className="font-medium">{node.label}</p>{node.missing_facts.length > 0 && <p className="mt-0.5 text-muted-foreground">Missing: {node.missing_facts.join(", ")}</p>}</div>
      </div>
      {node.children.length > 0 && <div className="ml-2 border-l border-current/20 pl-2">{node.children.map((child, index) => <ConditionTraceTree key={`${child.label}-${index}`} node={child} />)}</div>}
    </div>
  )
}

function RuleExecutionTrace({ preview }: { preview: SamplePreview }) {
  const sections = Array.from(new Set(preview.evaluation.trace.map((entry) => entry.section)))
  return (
    <div className="mt-3 space-y-3">
      {sections.map((section, sectionIndex) => {
        const entries = preview.evaluation.trace.filter((entry) => entry.section === section)
        const blocks = Array.from(new Set(entries.map((entry) => entry.block_id)))
        return (
          <section key={section} className={cn("rounded-lg border p-3", clinicalRuleSectionTone(sectionIndex).surface)}>
            <div className="flex items-center justify-between gap-3">
              <h3 className="font-semibold">{section}</h3>
              <span className="text-xs text-muted-foreground">{entries.filter((entry) => entry.matched).length}/{entries.length} matched</span>
            </div>
            {blocks.map((blockId) => (
              <div key={blockId} className="mt-3 border-l-2 border-current/20 pl-3">
                <p className="type-label text-muted-foreground">{blockId}</p>
                <div className="mt-1 space-y-1">
                  {entries.filter((entry) => entry.block_id === blockId).map((entry, index) => (
                    <div key={`${entry.rule_id}-${entry.item_identity || index}`} className="flex items-start gap-2 rounded-md bg-background/70 p-2 text-sm">
                      {entry.matched ? <CircleCheck className="clinical-trace-pass mt-0.5 h-4 w-4 shrink-0" /> : <CircleX className="clinical-trace-fail mt-0.5 h-4 w-4 shrink-0" />}
                      <div className="min-w-0">
                        <p className="font-medium">{entry.rule_id}{entry.item_identity ? ` · item ${entry.item_identity}` : ""}</p>
                        <p className="text-xs text-muted-foreground">{entry.matched ? "Condition passed" : entry.missing_facts.length ? `Missing: ${entry.missing_facts.join(", ")}` : "Condition did not match"}</p>
                        {entry.condition_trace && <ConditionTraceTree node={entry.condition_trace} />}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </section>
        )
      })}
    </div>
  )
}

export function ClinicalRuleTestingPage() {
  const [ruleId, setRuleId] = useState("")
  const [search, setSearch] = useState("")
  const [scope, setScope] = useState<"subpanel" | "assay">("subpanel")
  const [sampleId, setSampleId] = useState("")
  const [traceOpen, setTraceOpen] = useState(false)
  const [traceLoaded, setTraceLoaded] = useState(false)

  const rulesQuery = useQuery({
    queryKey: ["clinical-rule-sets", "testing"],
    queryFn: () => api.get<{ items: ClinicalRuleSet[] }>("/admin/clinical-rule-sets?per_page=200").then((response) => response.data),
  })
  const selectedRule = useMemo(
    () => rulesQuery.data?.items.find((item) => item._id === ruleId),
    [ruleId, rulesQuery.data?.items],
  )
  const samplesQuery = useQuery({
    queryKey: ["clinical-rule-test-samples", ruleId, scope, search],
    enabled: Boolean(ruleId),
    queryFn: () => api.get<{ items: TestSample[] }>(`/admin/clinical-rule-sets/versions/${ruleId}/test-samples?match_subpanel=${scope === "subpanel"}&q=${encodeURIComponent(search)}&per_page=10`).then((response) => response.data),
  })
  const previewMutation = useMutation({
    mutationFn: (includeConditionTrace: boolean) => api.post<SamplePreview>(`/admin/clinical-rule-sets/versions/${ruleId}/test-samples/${sampleId}/preview?include_condition_trace=${includeConditionTrace}`).then((response) => response.data),
    onSuccess: (_data, includeConditionTrace) => {
      setTraceLoaded(includeConditionTrace)
      setTraceOpen(includeConditionTrace)
    },
  })

  const resetPreview = () => {
    setTraceOpen(false)
    setTraceLoaded(false)
    previewMutation.reset()
  }

  return (
    <PageShell
      eyebrow="Clinical reporting"
      title="Rule Test Workspace"
      description="Evaluate a rule-set version against authorized sample data without changing the sample or saving a report."
    >
      <section className="surface-panel p-4">
        <div className="grid gap-3 lg:grid-cols-[minmax(18rem,1.4fr)_auto_minmax(16rem,1fr)_auto] lg:items-end">
          <label className="type-label">Rule set<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={ruleId} onChange={(event) => { setRuleId(event.target.value); setSampleId(""); resetPreview() }}><option value="">Select rule set</option>{(rulesQuery.data?.items || []).filter((rule) => rule.status !== "retired").map((rule) => <option key={rule._id} value={rule._id}>{rule.name} · v{rule.content_version} · {rule.status}</option>)}</select></label>
          <SegmentedControl ariaLabel="Sample matching scope" value={scope} onValueChange={(value) => { setScope(value); setSampleId(""); resetPreview() }} items={[{ value: "subpanel", label: "Assay + subpanel" }, { value: "assay", label: "Assay only" }]} />
          <label className="type-label">Search samples<div className="relative mt-1"><Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" /><Input className="pl-8" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Sample or case identifier" /></div></label>
          <Button disabled={!ruleId || !sampleId || previewMutation.isPending} onClick={() => previewMutation.mutate(false)}><Beaker /> {previewMutation.isPending && !traceOpen ? "Testing" : "Test rule set"}</Button>
        </div>
        {selectedRule && <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground"><ClinicalRuleStatusBadge status={selectedRule.status} /><span>Testing {selectedRule.scope.asp_id} · {selectedRule.scope.subpanel_id} · {selectedRule.scope.analyte.toUpperCase()}</span></div>}
        {rulesQuery.error && <p role="alert" className="mt-3 rounded-lg border border-warn/30 bg-warn/10 p-3 text-sm text-warn">{rulesQuery.error instanceof Error ? rulesQuery.error.message : "Unable to load clinical rule sets."}</p>}
      </section>

      <div className="grid gap-3 xl:grid-cols-[minmax(18rem,0.7fr)_minmax(30rem,1.3fr)]">
        <section className="surface-panel min-h-80 p-3">
          <div className="flex items-center justify-between gap-3"><h2 className="type-section-title">Compatible samples</h2><span className="text-xs text-muted-foreground">Latest 10</span></div>
          <div className="mt-3 space-y-1">
            {(samplesQuery.data?.items || []).map((sample) => <button key={sample.id} type="button" className={`w-full rounded-lg border p-3 text-left ${sampleId === sample.id ? "border-primary bg-primary/10" : "border-border hover:bg-muted"}`} onClick={() => { setSampleId(sample.id); resetPreview() }}><span className="block font-medium">{sample.name}</span><span className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground"><span>{sample.asp_id}</span><span>{sample.subpanel_id}</span><span>{sample.environment}</span></span></button>)}
            {ruleId && !samplesQuery.isLoading && !samplesQuery.error && !samplesQuery.data?.items.length && <p className="p-6 text-center text-sm text-muted-foreground">No compatible samples found.</p>}
            {samplesQuery.error && <p role="alert" className="rounded-lg border border-warn/30 bg-warn/10 p-3 text-sm text-warn">{samplesQuery.error instanceof Error ? samplesQuery.error.message : "Unable to search compatible samples."}</p>}
          </div>
        </section>
        <section className="surface-panel min-h-80 p-4">
          <div className="flex items-center justify-between gap-3"><h2 className="type-section-title">Generated report summary</h2>{previewMutation.data && <Badge variant="outline" className="badge-success">Read-only preview</Badge>}</div>
          {previewMutation.error && <p role="alert" className="mt-4 rounded-lg border border-warn/30 bg-warn/10 p-3 text-sm text-warn">{previewMutation.error instanceof Error ? previewMutation.error.message : "Unable to generate the rule-set preview."}</p>}
          {previewMutation.data ? <>
            <div className="mt-4 space-y-3">{Object.entries(previewMutation.data.evaluation.sections).map(([section, texts], sectionIndex) => <section key={section} className={cn("rounded-lg border p-4", clinicalRuleSectionTone(sectionIndex).surface)}><h3 className="mb-2 font-semibold">{section}</h3>{texts.map((text, index) => <MarkdownText key={index} text={text} />)}</section>)}{!Object.keys(previewMutation.data.evaluation.sections).length && <MarkdownText className="rounded-lg border border-border bg-background p-4" text={previewMutation.data.summary} />}</div>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2"><p className="text-xs text-muted-foreground">{previewMutation.data.evaluation.trace.filter((item) => item.matched).length} rules matched. No data was persisted.</p><Button variant="outline" size="sm" disabled={previewMutation.isPending} onClick={() => { if (traceOpen) setTraceOpen(false); else if (traceLoaded) setTraceOpen(true); else previewMutation.mutate(true) }}>{traceOpen ? <ChevronUp /> : <ChevronDown />} {previewMutation.isPending ? "Building trace" : traceOpen ? "Hide" : "Show"} execution trace</Button></div>
            {traceOpen && <RuleExecutionTrace preview={previewMutation.data} />}
          </> : !previewMutation.error && <div className="grid min-h-64 place-items-center text-sm text-muted-foreground">Select a sample and test the rule set to generate its report summary.</div>}
        </section>
      </div>
    </PageShell>
  )
}
