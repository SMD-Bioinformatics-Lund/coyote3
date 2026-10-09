import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { notifyActionError } from "@/lib/notifications"

type Scope = { assay_group: string | null; asp_id: string | null; subpanel_id: string | null; analysis: string; intent: string }
type Sample = { id: string; name: string; asp_id?: string; subpanel_id?: string }
type SearchResult = { items: Sample[]; total: number; page: number; per_page: number }
type Result = {
  sample: Sample; published_count: number; draft_count: number; added_count: number; removed_count: number
  unchanged_count: number; added: { id: string; label: string }[]; removed: { id: string; label: string }[]
  display_limit: number; persisted: false
  draft_policy: { lineage: { source: string; version?: number | null }[] }
  published_query: Record<string, unknown>; draft_query: Record<string, unknown>; post_filters: string[]
}

export function QueryRuleSampleTestPanel({ scope, content, readOnly = false }: { scope: Scope; content: unknown; readOnly?: boolean }) {
  const [search, setSearch] = useState("")
  const fingerprint = JSON.stringify({ scope, content })
  const searchKey = JSON.stringify({ scope, search })
  const samples = useMutation({
    mutationFn: async (page: number) => ({ key: searchKey, data: (await api.post<SearchResult>("/admin/query-rule-sets/test-samples", { scope, search, page })).data }),
    onError: error => notifyActionError("Unable to find test samples", error, "Query rules"),
  })
  const test = useMutation({
    mutationFn: async (sample: Sample) => ({ key: fingerprint, data: (await api.post<Result>(`/admin/query-rule-sets/test-samples/${encodeURIComponent(sample.id)}/preview`, { scope, content })).data }),
    onError: error => notifyActionError("Sample query-rule test failed", error, "Query rules"),
  })
  const page = samples.data?.key === searchKey ? samples.data.data : undefined
  const result = test.data?.key === fingerprint ? test.data.data : undefined
  return <section className="surface-panel space-y-4 rounded-lg border p-4" aria-label="Test with a sample">
    <h2 className="type-section-title">Test with a sample</h2>
    <p className="text-muted-foreground type-supporting">Compare the live policy with {readOnly ? "this selected version" : "this draft"} using a ready sample’s saved filters and ASPC. More-specific published rules still apply. Testing does not change data.</p>
    {scope.analysis === "snv" && scope.intent === "germline" && <p className="type-supporting text-muted-foreground">This test evaluates germline exceptions within the combined somatic SNV workflow, using the sample’s somatic filters.</p>}
    <div className="grid gap-4 xl:grid-cols-2">
    <section className="min-w-0 space-y-3 rounded-lg border bg-background p-4" aria-label="Sample selection">
    <h3 className="type-section-title">1. Select a sample</h3>
    <form className="flex flex-wrap gap-2" onSubmit={event => { event.preventDefault(); if (!samples.isPending && scope.assay_group !== "") samples.mutate(1) }}><Input className="min-w-0 flex-1" aria-label="Search query-rule test samples" placeholder="Sample name or identifier" value={search} onChange={event => setSearch(event.target.value)} /><Button type="submit" variant="outline" disabled={samples.isPending || scope.assay_group === ""}>Find samples</Button></form>
    {!page && <p className="type-supporting text-muted-foreground">Search for ready samples within this rule’s scope, then select Test to compare finding selection.</p>}
    {page && <>
      <p className="type-supporting">{page.total} samples · page {page.page}</p>
      {page.items.length === 0 && <p>No ready samples match this scope and your access.</p>}
      <ul className="space-y-2">{page.items.map(sample => <li key={sample.id} className="flex flex-wrap items-center justify-between gap-3 rounded border p-3"><div className="min-w-0 break-words"><strong>{sample.name}</strong><p className="type-supporting text-muted-foreground">{sample.asp_id} · {sample.subpanel_id}</p></div><Button type="button" variant="outline" aria-label={`Test ${sample.name}`} disabled={test.isPending} onClick={() => test.mutate(sample)}>Test sample</Button></li>)}</ul>
      <div className="flex gap-2"><Button type="button" variant="outline" disabled={samples.isPending || page.page <= 1} onClick={() => samples.mutate(page.page - 1)}>Previous samples</Button><Button type="button" variant="outline" disabled={samples.isPending || page.page * page.per_page >= page.total} onClick={() => samples.mutate(page.page + 1)}>Next samples</Button></div>
    </>}
    </section>
    <section className="min-w-0 space-y-3 rounded-lg border bg-background p-4" aria-label="Sample comparison">
    <h3 className="type-section-title">2. Review results</h3>
    {!result && !test.isPending && <p className="type-supporting text-muted-foreground">Select a sample to compare the published policy with this draft. Results appear here; no data is saved.</p>}
    {test.isPending && <p role="status">Comparing sample findings…</p>}
    {result && !test.isPending && !test.isError && <div className="space-y-3" aria-live="polite">
      <h3 className="type-section-title">{result.sample.name}</h3>
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">{[{ label: "Published", count: result.published_count }, { label: "Draft", count: result.draft_count }, { label: "Added", count: result.added_count }, { label: "Removed", count: result.removed_count }, { label: "Unchanged", count: result.unchanged_count }].map(item => <div key={item.label} className="rounded border p-3"><dt className="type-supporting text-muted-foreground">{item.label}</dt><dd className="font-semibold">{item.count}</dd></div>)}</dl>
      <p className="text-muted-foreground type-supporting">Counts cover retrieval selection, before report eligibility and browser search. Up to {result.display_limit} identities are shown per change category.</p>
      {[{ label: "Added findings", rows: result.added }, { label: "Removed findings", rows: result.removed }].map(group => <details key={group.label} open={group.rows.length > 0}><summary className="cursor-pointer type-label">{group.label}</summary><ul className="space-y-1">{group.rows.map(row => <li key={row.id} className="break-words">{row.label} <span className="text-muted-foreground">({row.id})</span></li>)}</ul></details>)}
      <details><summary className="cursor-pointer type-label">Effective draft inheritance</summary><ol>{result.draft_policy.lineage.map((row, index) => <li key={index}>{row.source}{row.version ? ` · version ${row.version}` : ""}</li>)}</ol></details>
    </div>}
    </section>
    </div>
    {result && !test.isPending && !test.isError && result.draft_query && <section className="space-y-3 border-t border-border pt-4" aria-label="Final MongoDB queries">
      <h3 className="type-section-title">Final MongoDB queries · {result.sample.name}</h3>
      <p className="type-supporting text-muted-foreground">Complete predicates used for this comparison, including sample scope, base evidence, resolved filters and applicable inherited rules. These are read-only query previews.</p>
      <div className="grid min-w-0 gap-3 lg:grid-cols-2">{[{ title: "Currently published", query: result.published_query }, { title: readOnly ? "Selected version" : "With draft changes", query: result.draft_query }].map(item => <details key={item.title} open className="min-w-0 rounded-lg border bg-background p-3"><summary className="cursor-pointer type-label">{item.title}</summary><pre className="mt-3 max-h-96 overflow-auto rounded bg-muted/30 p-3 type-supporting"><code>{JSON.stringify(item.query, null, 2)}</code></pre></details>)}</div>
      {!!result.post_filters?.length && <div className="rounded-lg border bg-muted/20 p-3"><h4 className="type-label">Additional selection after MongoDB retrieval</h4><ul className="mt-2 list-disc space-y-1 pl-5 type-supporting">{result.post_filters.map(note => <li key={note}>{note}</li>)}</ul></div>}
    </section>}
  </section>
}
