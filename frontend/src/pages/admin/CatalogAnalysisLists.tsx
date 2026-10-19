import { useMemo, useState } from "react"
import { Input } from "@/components/ui/input"
import type { Category, SourceOptions } from "./catalog-types"

export function CatalogAnalysisLists({ entry, sources, onChange }: {
  entry: Category; sources: SourceOptions; onChange: (entry: Category) => void
}) {
  const [search, setSearch] = useState("")
  const group = sources.asps.find((assay) => assay.asp_id === entry.asp_id)?.group
  const eligible = useMemo(() => sources.gene_lists.filter((list) =>
    list.asp_ids.includes(entry.asp_id || "")
    && (!list.asp_groups?.length || list.asp_groups.includes(group || ""))),
  [sources.gene_lists, entry.asp_id, group])
  const visible = eligible.filter((list) => `${list.label} ${list.isgl_id}`.toLowerCase().includes(search.toLowerCase()))
  const genes = entry.gene_lists || []
  const toggle = (analysis: string, id: string) => {
    const existing = genes.find((list) => (list.isgl_id || list.key) === id)
    const selected = existing?.analysis?.includes(analysis)
    const source = eligible.find((list) => list.isgl_id === id)!
    const next = { ...existing, isgl_id: id, key: id, label: existing?.label || source.label,
      analysis: selected ? existing!.analysis!.filter((item) => item !== analysis)
        : [...(existing?.analysis || []), analysis] }
    onChange({ ...entry, no_gene_list: (entry.no_gene_list || []).filter((item) => item !== analysis),
      gene_lists: [...genes.filter((list) => (list.isgl_id || list.key) !== id), ...(next.analysis.length ? [next] : [])] })
  }
  return <section aria-label="Gene lists by analysis" className="space-y-3 border-t border-border pt-4">
    <div><h3 className="type-body font-semibold">Gene lists by analysis</h3>
      <p className="type-body-sm text-muted-foreground">Choose one or more lists for each analysis, or explicitly select No gene list.</p></div>
    <Input aria-label="Search eligible gene lists" placeholder="Search gene lists" value={search} onChange={(event) => setSearch(event.target.value)} />
    {genes.some((list) => !list.analysis?.length) && <p role="status" className="type-body-sm text-muted-foreground">Some existing gene lists have no analysis assignment. Assign them below or remove them from Selected gene-list descriptions before submitting.</p>}
    {genes.some((list) => !eligible.some((source) => source.isgl_id === (list.isgl_id || list.key))) && <p role="alert" className="type-body-sm text-destructive">A selected list is no longer eligible for this assay and group. Remove it from Selected gene-list descriptions and review its analysis assignments.</p>}
    {!entry.analysis?.length && <p className="type-body-sm text-muted-foreground">Select the available analyses above.</p>}
    <div className="grid gap-3 lg:grid-cols-2">
      {(entry.analysis || []).map((analysis) => {
        const selected = genes.filter((list) => list.analysis?.includes(analysis))
        const none = entry.no_gene_list?.includes(analysis) || false
        return <fieldset key={analysis} className="min-w-0 space-y-3 rounded-xl border border-border bg-card p-3">
          <legend className="px-1 type-label">{analysis}</legend>
          <div className="flex flex-wrap items-center justify-between gap-2 type-body-sm">
            <span className="text-muted-foreground">{none ? "No gene list" : `${selected.length} selected`}</span>
            <label className="flex items-center gap-2"><input type="checkbox" checked={none}
              onChange={() => onChange({ ...entry,
                no_gene_list: none ? entry.no_gene_list!.filter((item) => item !== analysis) : [...(entry.no_gene_list || []), analysis],
                gene_lists: none ? genes : genes.flatMap((list) => {
                  if (!list.analysis?.includes(analysis)) return [list]
                  const remaining = list.analysis.filter((item) => item !== analysis)
                  return remaining.length ? [{ ...list, analysis: remaining }] : []
                }),
              })} />No gene list for {analysis}</label>
          </div>
          {!none && <div className="max-h-52 space-y-1 overflow-y-auto">
            {visible.map((list) => <label key={list.isgl_id} className="flex cursor-pointer items-start gap-2 rounded-lg p-2 type-body-sm hover:bg-muted">
              <input type="checkbox" className="mt-1" checked={selected.some((item) => (item.isgl_id || item.key) === list.isgl_id)} onChange={() => toggle(analysis, list.isgl_id)} />
              <span className="min-w-0"><span className="block break-words">{list.label}</span><span className="type-meta text-muted-foreground">{list.isgl_id}</span></span>
            </label>)}
            {!visible.length && <p className="type-body-sm text-muted-foreground">{eligible.length ? "No matching gene lists." : "No active public gene lists are linked to this assay and group."}</p>}
          </div>}
          {!none && !selected.length && <p className="type-body-sm text-muted-foreground">Choose a list or No gene list before submitting.</p>}
        </fieldset>
      })}
    </div>
  </section>
}
