import { useMemo, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { ChevronDown, Search, X } from "lucide-react"
import { api } from "@/lib/api"
import { DataTable } from "@/components/data-table/DataTable"
import { ExpandableText } from "@/components/detail/ExpandableText"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { TierBadge } from "@/lib/variant-ui"
import { sampleDetailPath } from "@/lib/sample-routing"
import { shortCount } from "@/lib/detail-formatters"
import { ColumnDef } from "@tanstack/react-table"
import { useUrlTableState } from "@/hooks/useUrlTableState"
import { tieredVariantSearchState } from "@/lib/variant-routing"

const tierBarClasses = ["", "bg-tier1", "bg-tier2", "bg-tier3", "bg-tier4"]
const tierTextClasses = ["", "text-tier1", "text-tier2", "text-tier3", "text-tier4"]
const tierHeaderClasses = ["", "bg-tier-header1", "bg-tier-header2", "bg-tier-header3", "bg-tier-header4"]

function tierCount(stats: Record<string, unknown>, tier: number) {
  return Number(stats?.[`tier${tier}`] || 0)
}

function totalTierCount(stats: Record<string, unknown>) {
  return [1, 2, 3, 4].reduce((total, tier) => total + tierCount(stats, tier), 0)
}

export function TieredVariantSearch() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [initialSearchState] = useState(() => tieredVariantSearchState(searchParams))
  const [search, setSearch] = useState(initialSearchState.search)
  const [appliedSearch, setAppliedSearch] = useState(initialSearchState.search)
  const [mode, setMode] = useState(initialSearchState.mode)
  const [appliedMode, setAppliedMode] = useState(initialSearchState.mode)
  const [includeText, setIncludeText] = useState(initialSearchState.includeText)
  const [appliedIncludeText, setAppliedIncludeText] = useState(initialSearchState.includeText)
  const [selectedAssays, setSelectedAssays] = useState<string[]>(initialSearchState.assays)
  const [appliedAssays, setAppliedAssays] = useState<string[]>(initialSearchState.assays)
  const {
    sorting,
    setSorting,
    updateTableSearchParams,
  } = useUrlTableState({ prefix: "tiered_variants" })

  const { data, isLoading, error } = useQuery({
    queryKey: ["tiered-variant-search", appliedSearch, appliedMode, appliedIncludeText, appliedAssays],
    queryFn: () => {
      const params = new URLSearchParams()
      if (appliedSearch) params.set("search_str", appliedSearch)
      params.set("search_mode", appliedMode)
      params.set("include_annotation_text", String(appliedIncludeText))
      appliedAssays.forEach((assay) => params.append("assays", assay))
      return api.get(`/common/search/tiered_variants?${params.toString()}`).then((res) => res.data)
    },
  })
  const assayChoices = data?.assay_choices || []
  const assayStats = useMemo(() => {
    const byAssay = data?.tier_stats?.by_assay || {}
    return Object.entries(byAssay)
      .map(([assay, stats]) => ({
        assay,
        stats: stats as Record<string, unknown>,
        total: totalTierCount(stats as Record<string, unknown>),
      }))
      .filter((row) => row.total > 0)
      .sort((a, b) => b.total - a.total || a.assay.localeCompare(b.assay))
  }, [data?.tier_stats?.by_assay])

  const submitSearch = () => {
    const normalizedSearch = search.trim()
    setAppliedSearch(normalizedSearch)
    setAppliedMode(mode)
    setAppliedIncludeText(includeText)
    setAppliedAssays(selectedAssays)
    const params = new URLSearchParams(searchParams)
    params.delete("search_str")
    params.delete("search_mode")
    params.delete("include_annotation_text")
    params.delete("assays")
    if (normalizedSearch) params.set("search_str", normalizedSearch)
    params.set("search_mode", mode)
    if (includeText) params.set("include_annotation_text", "true")
    selectedAssays.forEach((assay) => params.append("assays", assay))
    setSearchParams(params, { replace: true })
  }

  const clearSearch = () => {
    setSearch("")
    setMode("variant")
    setIncludeText(false)
    setSelectedAssays([])
    setAppliedSearch("")
    setAppliedMode("variant")
    setAppliedIncludeText(false)
    setAppliedAssays([])
    const params = new URLSearchParams(searchParams)
    params.delete("search_str")
    params.delete("search_mode")
    params.delete("include_annotation_text")
    params.delete("assays")
    setSearchParams(params, { replace: true })
  }

  const columns: ColumnDef<any, any>[] = useMemo(() => [
    {
      id: "tier",
      header: "Tier",
      accessorFn: (row) => row.class ?? row.tier ?? row.classification?.class ?? 999,
      meta: { headerClassName: "w-14 min-w-14", cellClassName: "w-14 min-w-14" },
      cell: ({ row }) => <TierBadge tier={row.getValue("tier")} />,
    },
    {
      id: "gene",
      header: "Gene",
      accessorFn: (row) => row.gene || row.SYMBOL || row.variant_data?.gene || row.variant_data?.gene1 || "-",
      cell: ({ row }) => <span className="font-bold text-primary">{String(row.getValue("gene"))}</span>,
    },
    {
      id: "variant",
      header: "Variant",
      accessorFn: (row) => row.variant || row.hgvs || row.HGVSp || row.HGVSc || "-",
      meta: { headerClassName: "w-56 min-w-52", cellClassName: "w-56 min-w-52" },
      cell: ({ row }) => (
        <div className="w-52">
          <ExpandableText
            text={String(row.getValue("variant") || "-")}
            maxLength={34}
            className="text-xs font-mono text-foreground"
          />
        </div>
      ),
    },
    {
      id: "assay",
      header: "Assay",
      accessorFn: (row) => row.assay || row.assay_group || row.variant_data?.assay_group || "-",
      cell: ({ row }) => <span className="text-xs uppercase text-muted-foreground">{String(row.getValue("assay"))}</span>,
    },
    {
      id: "subpanel",
      header: "Subpanel",
      accessorFn: (row) => row.subpanel || row.diagnosis || "-",
      cell: ({ row }) => <span className="text-xs text-muted-foreground">{String(row.getValue("subpanel"))}</span>,
    },
    {
      id: "author",
      header: "Author",
      accessorFn: (row) => row.author || row.user || "-",
      cell: ({ row }) => <span className="text-xs">{String(row.getValue("author"))}</span>,
    },
    {
      id: "text",
      header: "Annotation",
      accessorFn: (row) => row.text || row.annotation_text || "",
      meta: { headerClassName: "w-[28rem] min-w-80", cellClassName: "w-[28rem] min-w-80" },
      cell: ({ row }) => (
        <div className="max-w-[28rem]">
          <ExpandableText
            text={String(row.getValue("text") || "-")}
            maxLength={120}
            className="text-xs leading-5 text-muted-foreground"
          />
        </div>
      ),
    },
    {
      id: "samples",
      header: "Samples",
      accessorFn: (row) => row.samples || {},
      cell: ({ row }) => {
        const samples = Object.values(row.original.samples || {}) as any[]
        if (!samples.length) return <span className="text-muted-foreground">-</span>
        return (
          <div className="flex max-w-sm flex-col gap-1">
            {samples.slice(0, 5).map((sample: any, index) => {
              const sampleId = sample.name || sample.sample_name || sample.sample_id || sample._id || sample.id || sample.sample_oid
              const sampleLabel = sample.sample_name || sample.name || "sample"
              return (
                <div key={sampleId || index} className="flex flex-wrap items-center gap-1">
                  <Link
                    to={sampleDetailPath(sample, sampleId)}
                    className="rounded-md bg-primary/10 px-1.5 py-0.5 text-[10px] font-bold text-primary hover:bg-primary/15 hover:underline"
                    title={[sampleLabel, sample.asp_id, sample.subpanel_id, sample.environment].filter(Boolean).join(" / ")}
                  >
                    {sampleLabel}
                  </Link>
                  {Object.entries(sample.report_oids || {}).map(([reportId, reportNum]) => (
                    <Link
                      key={reportId}
                      to={`${sampleDetailPath(sample, sampleId)}/reports/${reportId}`}
                      className="rounded-md bg-tier2 px-1.5 py-0.5 text-[10px] font-black text-white hover:bg-tier2/90"
                      title={`Report ${String(reportNum || reportId)}`}
                    >
                      {String(reportNum || reportId)}
                    </Link>
                  ))}
                </div>
              )
            })}
            {samples.length > 5 && <span className="text-[10px] font-bold text-muted-foreground">+{samples.length - 5}</span>}
          </div>
        )
      },
    },
  ], [])

  return (
    <PageShell
      eyebrow="Common"
      title="Tiered Variant Search"
      description="Search reported tiered variants and annotation text across samples and assays."
    >
      <div className="glass-card p-3">
        <form
          className="mb-3 flex flex-wrap items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            submitSearch()
          }}
        >
          <div className="relative w-full max-w-sm">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search gene, variant, annotation..."
              className="w-full rounded-lg border border-input bg-background py-2 pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-primary/40"
            />
          </div>
          <select
            value={mode}
            onChange={(event) => setMode(event.target.value)}
            className="rounded-lg border border-input bg-background px-3 py-2 text-sm"
          >
            <option value="variant">Variant (HGVSp / HGVSc / genomic)</option>
            <option value="gene">Gene symbol</option>
            <option value="hgvsp">HGVSp</option>
            <option value="hgvsc">HGVSc</option>
            <option value="genomic">Genomic</option>
            <option value="transcript">Transcript ID</option>
            <option value="subpanel">Subpanel</option>
            <option value="author">Author</option>
            <option value="annotation">Annotation text</option>
            <option value="all">All fields</option>
          </select>
          <label className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm">
            <input type="checkbox" checked={includeText} onChange={(event) => setIncludeText(event.target.checked)} />
            Include annotation text
          </label>
          <button type="submit" className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-bold text-primary-foreground shadow-sm hover:bg-primary/90">
            <Search className="h-4 w-4" />
            Search
          </button>
          <button type="button" onClick={clearSearch} className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-bold hover:bg-muted">
            <X className="h-4 w-4" />
            Clear
          </button>
        </form>

        {assayChoices.length > 0 && (
          <div className="mb-3 rounded-xl border border-border bg-background/70 p-3">
            <div className="mb-2 text-xs font-black uppercase tracking-wider text-muted-foreground">Assays</div>
            <div className="flex flex-wrap gap-2">
              {assayChoices.map((assay: string) => (
                <label key={assay} className="inline-flex items-center gap-2 rounded-lg border border-border bg-card/80 px-2.5 py-1.5 text-xs font-bold hover:bg-muted">
                  <input
                    type="checkbox"
                    checked={selectedAssays.includes(assay)}
                    onChange={(event) => {
                      setSelectedAssays((current) => event.target.checked ? [...current, assay] : current.filter((item) => item !== assay))
                    }}
                  />
                  {assay}
                </label>
              ))}
            </div>
          </div>
        )}

        {data?.tier_stats?.total && (
          <div className="mb-3 grid gap-2 text-sm sm:grid-cols-4">
            {[1, 2, 3, 4].map((tier) => (
              <div key={tier} className={`rounded-lg border border-border p-3 ${tierHeaderClasses[tier]}`}>
                <span className="font-bold">Tier {tier}</span>
                <span className="float-right font-mono">{data.tier_stats.total[`tier${tier}`] || 0}</span>
              </div>
            ))}
          </div>
        )}

        {assayStats.length > 0 && (
          <details className="group mb-3 overflow-hidden rounded-xl border border-border bg-card">
            <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-3 px-4 py-3 marker:hidden hover:bg-muted/30">
              <div>
                <div className="text-xs font-black uppercase tracking-wider text-muted-foreground">Assay distribution</div>
                <div className="text-xs text-muted-foreground">Unique tiered variants by assay for the current search.</div>
              </div>
              <div className="flex items-center gap-2 text-xs font-bold text-muted-foreground">
                <span>{assayStats.length} assay{assayStats.length === 1 ? "" : "s"}</span>
                <ChevronDown className="h-4 w-4 transition-transform duration-150 group-open:rotate-180" />
              </div>
            </summary>
            <div className="overflow-x-auto border-t border-border">
              <table className="w-full min-w-[42rem] border-collapse text-xs">
                <thead className="bg-muted/45 text-left uppercase text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2 font-black">Assay</th>
                    <th className="w-full min-w-48 px-4 py-2 font-black">Distribution</th>
                    {[1, 2, 3, 4].map((tier) => (
                      <th key={tier} className={`w-16 px-3 py-2 text-right font-black ${tierTextClasses[tier]}`}>
                        Tier {tier}
                      </th>
                    ))}
                    <th className="w-16 px-4 py-2 text-right font-black">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {assayStats.map(({ assay, stats, total }) => (
                    <tr key={assay} className="hover:bg-muted/25">
                      <th scope="row" className="max-w-48 truncate px-4 py-2.5 text-left font-black uppercase text-foreground" title={assay}>
                        {assay}
                      </th>
                      <td className="px-4 py-2.5">
                        <div
                          className="flex h-3 min-w-48 overflow-hidden rounded-full bg-muted"
                          aria-label={`${assay}: ${total} tiered variants`}
                        >
                          {[1, 2, 3, 4].map((tier) => (
                            tierCount(stats, tier) > 0 && (
                              <span
                                key={tier}
                                className={`${tierBarClasses[tier]} h-full border-r border-card/50 last:border-r-0`}
                                style={{ width: `${(tierCount(stats, tier) / total) * 100}%` }}
                                title={`Tier ${tier}: ${tierCount(stats, tier)}`}
                              />
                            )
                          ))}
                        </div>
                      </td>
                      {[1, 2, 3, 4].map((tier) => (
                        <td key={tier} className={`px-3 py-2.5 text-right font-bold tabular-nums ${tierTextClasses[tier]}`}>
                          {shortCount(tierCount(stats, tier))}
                        </td>
                      ))}
                      <td className="px-4 py-2.5 text-right text-sm font-black tabular-nums text-foreground" title={`${total} total variants`}>
                        {shortCount(total)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        )}

        {isLoading ? (
          <AppLoader label="Loading variant search" />
        ) : error ? (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
            {error instanceof Error ? error.message : "Unable to search tiered variants"}
          </div>
        ) : (
          <DataTable
            columns={columns}
            data={data?.docs || []}
            filename="tiered_variants.csv"
            stateKey="tiered_variants"
            sortingState={sorting}
            onSortingChange={(value) => {
              setSorting(value)
              updateTableSearchParams({ sorting: value })
            }}
          />
        )}
      </div>
    </PageShell>
  )
}
