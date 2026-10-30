import { MarkdownText } from "@/components/comments/MarkdownText"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"
import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import type { ClinicalRuleSet, FactDefinition } from "./clinical-rules-types"
import { RuleCompositionPreview } from "./RuleCompositionPreview"
import { RuleHelp } from "./RuleHelp"

type Sample = { id: string; name: string; diagnosis_id: string }
type Preview = { summary: string; analysis_description: string; evaluation: { trace: { matched: boolean }[] } }

export function RuleSetPreview({ draft, facts, saved, canTest }: {
  draft: ClinicalRuleSet; facts: FactDefinition[]; saved: boolean; canTest: boolean
}) {
  const [sampleId, setSampleId] = useState("")
  const [search, setSearch] = useState("")
  const [matchDiagnosis, setMatchDiagnosis] = useState(draft.scope.diagnosis_id !== "base")
  const samples = useQuery({
    queryKey: ["clinical-rule-preview-samples", draft._id, search, matchDiagnosis],
    enabled: canTest,
    queryFn: ({ signal }) => api.get<{ items: Sample[] }>(`/admin/clinical-rule-sets/versions/${draft._id}/test-samples?match_diagnosis=${matchDiagnosis}&q=${encodeURIComponent(search)}&per_page=10`, { errorNotice: "inline", signal }).then(response => response.data.items),
    retry: false,
  })
  const result = useQuery({
    queryKey: ["clinical-rule-combined-preview", draft._id, draft.revision, sampleId],
    enabled: canTest && !!sampleId && saved,
    queryFn: ({ signal }) => api.post<Preview>(`/admin/clinical-rule-sets/versions/${draft._id}/test-samples/${sampleId}/preview?include_condition_trace=false`, undefined, { errorNotice: "inline", signal }).then(response => response.data),
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: Infinity,
  })
  return <section aria-label="Complete rule-set preview" className="space-y-3">
    <div className="flex items-center gap-2"><h2 className="type-section-title">Complete report text</h2><RuleHelp label="Composition or actual sample result">Without a sample, this panel shows all enabled alternatives and placeholder values, not a final report. Choose an authorized sample to evaluate the complete saved rule set. Disabled rules are excluded. Live preview does not save a report. Independent review is required before publication.</RuleHelp></div>
    {canTest ? <div className="space-y-2">
      <Input aria-label="Find preview sample" value={search} onChange={event => setSearch(event.target.value)} placeholder="Find a sample for actual values…" />
      <label className="flex items-center gap-2 type-body-sm"><input type="checkbox" checked={matchDiagnosis} onChange={event => { setMatchDiagnosis(event.target.checked); setSampleId("") }} /> Match rule-set diagnosis only</label>
      <label className="type-label block">Preview sample<select className="paper-inset mt-1 w-full rounded-lg p-2 type-body" value={sampleId} onChange={event => setSampleId(event.target.value)}><option value="">Composition only - choose a sample for actual results</option>{(samples.data || []).map(sample => <option key={sample.id} value={sample.id}>{sample.name} · {sample.diagnosis_id}</option>)}</select></label>
      {samples.error && <p role="alert" className="type-body-sm text-destructive">Unable to load authorized preview samples.</p>}
    </div> : <p className="type-body-sm text-muted-foreground">Sample evaluation requires the clinical rule testing permission.</p>}
    {sampleId && canTest ? <>
      {!saved ? <p role="status" className="type-body-sm text-muted-foreground">Waiting for valid edits to save before evaluating all conditions.</p>
        : result.isFetching ? <p role="status" className="type-body-sm">Evaluating the complete rule set…</p>
          : result.error ? <p role="alert" className="type-body-sm text-destructive">{result.error instanceof Error ? result.error.message : "Unable to evaluate this rule set."}</p>
            : result.data && <><div className="paper-inset space-y-3 rounded-lg p-3"><h3 className="type-section-title">Report summary</h3><MarkdownText text={result.data.summary || "No summary rules matched this sample."} /><h3 className="type-section-title">Analysis description</h3><MarkdownText text={result.data.analysis_description || "No analysis description rules matched this sample."} /></div><p className="type-meta text-muted-foreground">Actual sample values · saved revision {draft.revision} · {result.data.evaluation.trace.filter(item => item.matched).length} rules matched. No report is saved.</p></>}
    </> : <RuleCompositionPreview draft={draft} facts={facts} />}
  </section>
}
