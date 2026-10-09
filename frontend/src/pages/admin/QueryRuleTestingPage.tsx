import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link, useSearchParams } from "react-router-dom"
import { PageShell } from "@/components/layout/PageShell"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import { ClinicalRuleStatusBadge } from "./ClinicalRuleStatusBadge"
import { QueryRuleSampleTestPanel } from "./QueryRuleSampleTestPanel"
import type { Rule } from "./QueryRulesPage"

export function QueryRuleTestingPage() {
  const [params] = useSearchParams()
  const [selectedId, setSelectedId] = useState(params.get("version") ?? "")
  const versions = useQuery({
    queryKey: ["query-rules"],
    queryFn: () => api.get<{ items: Rule[] }>("/admin/query-rule-sets").then(result => result.data),
  })
  const selected = versions.data?.items.find(rule => rule._id === selectedId)
  return <PageShell eyebrow="Finding selection" title="Query Rule Testing"
    description="Compare saved query-rule versions against authorized samples without changing findings or publishing rules."
    actions={<Button variant="outline" nativeButton={false} render={<Link to="/admin/query-rules" />}>Query rule sets</Button>}>
    <section className="surface-panel space-y-3 p-4" aria-label="Query version selection">
      <label className="block type-label">Rule-set version
        <select className="paper-inset mt-2 w-full rounded-lg p-2 type-body" value={selectedId} onChange={event => setSelectedId(event.target.value)}>
          <option value="">Select a saved version</option>
          {versions.data?.items.map(rule => <option key={rule._id} value={rule._id}>{rule.name} · v{rule.version} · {rule.status}</option>)}
        </select>
      </label>
      {versions.isLoading && <p role="status">Loading versions…</p>}
      {versions.isError && <p role="alert">Unable to load query-rule versions. <Button variant="outline" onClick={() => void versions.refetch()}>Retry</Button></p>}
      {selected && <div className="flex flex-wrap items-center gap-2 type-body-sm"><ClinicalRuleStatusBadge status={selected.status} prefix={`v${selected.version} `} /><span>{selected.scope.assay_group ?? "All groups"} · {selected.scope.asp_id ?? "All assays"} · {selected.scope.subpanel_id ?? "All subpanels"}</span></div>}
      <p className="type-body-sm text-muted-foreground">Save draft changes in the editor before testing. Only ready samples within your assay and environment access are available.</p>
    </section>
    {selected ? <div className="mt-4"><QueryRuleSampleTestPanel key={`${selected._id}:${selected.revision}`} scope={selected.scope} content={selected.content} readOnly={selected.status !== "draft"} /></div> : <p className="mt-4 type-body-sm text-muted-foreground">Select a version to find and test samples.</p>}
  </PageShell>
}
