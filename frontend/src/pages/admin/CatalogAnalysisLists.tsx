import { useMemo, useState } from "react"
import { SearchInput } from "@/components/ui/search-input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { icon } from "@/lib/assets"
import { valueBadgeClass } from "@/lib/badge-colors"
import type { Category, SourceOptions } from "./catalog-types"

export function CatalogAnalysisLists({ entry, sources, onChange }: {
  entry: Category; sources: SourceOptions; onChange: (entry: Category) => void
}) {
  const [search, setSearch] = useState("")
  const group = sources.asps.find((assay) => assay.asp_id === entry.asp_id)?.group
  const eligible = useMemo(() => sources.gene_lists.filter((list) =>
    list.asp_ids.includes(entry.asp_id || "")
    && (!list.asp_groups?.length || list.asp_groups.includes(group || ""))
    && (!list.diagnosis.length || list.diagnosis.includes(entry.diagnosis_id || "base"))),
  [sources.gene_lists, entry.asp_id, entry.diagnosis_id, group])
  const visible = eligible.filter((list) => `${list.label} ${list.isgl_id}`.toLowerCase().includes(search.toLowerCase()))
  const genes = entry.gene_lists || []
  const toggle = (analysis: string, id: string) => {
    const existing = genes.find((list) => (list.isgl_id || list.key) === id)
    const selected = existing?.analysis?.includes(analysis)
    const source = eligible.find((list) => list.isgl_id === id)!
    const next = { ...existing, isgl_id: id, key: id, label: existing?.label || source?.label || id,
      analysis: selected ? existing!.analysis!.filter((item) => item !== analysis)
        : [...(existing?.analysis || []), analysis] }
    onChange({ ...entry, no_gene_list: (entry.no_gene_list || []).filter((item) => item !== analysis),
      gene_lists: [...genes.filter((list) => (list.isgl_id || list.key) !== id), ...(next.analysis.length ? [next] : [])] })
  }
  const picker = (analysis?: string) => {
    const selected = analysis ? genes.filter(list => list.analysis?.includes(analysis)) : genes
    const options = (analysis ? visible.filter(list => list.list_type?.includes(analysis.toLowerCase())) : visible)
      .filter(list => !selected.some(gene => (gene.isgl_id || gene.key) === list.isgl_id))
    return <div className="space-y-3">
      <label className="grid gap-1 type-label">{analysis ? `Add gene list for ${analysis}` : "Add gene list"}
        <select aria-label={analysis ? `Add gene list for ${analysis}` : "Add gene list"} value=""
          className="form-control w-full rounded-lg p-2 type-body" disabled={!options.length}
          onChange={event => {
            const id = event.target.value
            if (!id) return
            if (analysis) toggle(analysis, id)
            else {
              const source = eligible.find(list => list.isgl_id === id)
              if (source) onChange({ ...entry, gene_lists: [...genes,
                { isgl_id: id, key: id, label: source.label, analysis: [] }] })
            }
          }}>
          <option value="">{options.length ? "Select gene list" : "No additional matching gene lists"}</option>
          {options.map(list => <option key={list.isgl_id} value={list.isgl_id}>{list.label}</option>)}
        </select>
      </label>
      <div className="flex flex-wrap gap-2">{selected.map(list => {
        const id = list.isgl_id || list.key || ""
        const name = list.label || id
        return <Badge key={id} variant="outline" className={`max-w-full whitespace-normal ${analysis ? valueBadgeClass(analysis) : ""}`}>
          <span className="min-w-0 break-words">{name}</span>
          <Button variant="ghost" size="icon-xs" aria-label={`Remove ${name}${analysis ? ` from ${analysis}` : ""}`}
            onClick={() => analysis ? toggle(analysis, id)
              : onChange({ ...entry, gene_lists: genes.filter(gene => (gene.isgl_id || gene.key) !== id) })}>
            <icon.x className="size-3" />
          </Button>
        </Badge>
      })}</div>
    </div>
  }
  return <section aria-label="Gene lists by analysis" className="space-y-3 border-t border-border pt-4">
    <div><h3 className="type-body font-semibold">Gene lists by analysis</h3>
      <p className="type-body-sm text-muted-foreground">Choose one or more lists for each analysis, or explicitly select No gene list.</p></div>
    <SearchInput aria-label="Search eligible gene lists" placeholder="Search gene lists" value={search} onChange={(event) => setSearch(event.target.value)} />
    {Boolean(entry.analysis?.length) && genes.some((list) => !list.analysis?.length) && <p role="status" className="type-body-sm text-muted-foreground">Some existing gene lists have no analysis assignment. Assign them below or remove them from Selected gene-list descriptions before submitting.</p>}
    {genes.some((list) => !eligible.some((source) => source.isgl_id === (list.isgl_id || list.key))) && <p role="alert" className="type-body-sm text-destructive">A selected list is no longer eligible for this assay and group. Remove it from Selected gene-list descriptions and review its analysis assignments.</p>}
    {!entry.analysis?.length && <fieldset className="space-y-2 rounded-lg border border-border p-3">
      <legend className="type-label">General gene lists</legend>
      <p className="type-body-sm text-muted-foreground">Used when this entry and its parents define no analyses. Child entries inherit these references unless overridden.</p>
      {picker()}
    </fieldset>}
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
          {!none && picker(analysis)}
          {!none && !selected.length && <p className="type-body-sm text-muted-foreground">Choose a list or No gene list before submitting.</p>}
        </fieldset>
      })}
    </div>
  </section>
}
