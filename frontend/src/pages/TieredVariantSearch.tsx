import { useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { Search, X } from "lucide-react"
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

const tierHeaderClasses = ["", "bg-tier-header1", "bg-tier-header2", "bg-tier-header3", "bg-tier-header4"]
const tierDotClasses = ["", "bg-tier1", "bg-tier2", "bg-tier3", "bg-tier4"]

function tierCount(stats: Record<string, unknown>, tier: number) {
  return Number(stats?.[`tier${tier}`] || 0)
}

function totalTierCount(stats: Record<string, unknown>) {
  return [1, 2, 3, 4].reduce((total, tier) => total + tierCount(stats, tier), 0)
}

export function TieredVariantSearch() {
  const [search, setSearch] = useState("")
  const [appliedSearch, setAppliedSearch] = useState("")
  const [mode, setMode] = useState("variant")
  const [appliedMode, setAppliedMode] = useState("variant")
  const [includeText, setIncludeText] = useState(false)
  const [appliedIncludeText, setAppliedIncludeText] = useState(false)
  const [selectedAssays, setSelectedAssays] = useState<string[]>([])
  const [appliedAssays, setAppliedAssays] = useState<string[]>([])
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
    setAppliedSearch(search.trim())
    setAppliedMode(mode)
    setAppliedIncludeText(includeText)
    setAppliedAssays(selectedAssays)
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
          <div className="mb-3 rounded-xl border border-border bg-background/70 p-3">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="text-xs font-black uppercase tracking-wider text-muted-foreground">Assay distribution</div>
                <div className="text-xs text-muted-foreground">Unique tiered variants by assay for the current search.</div>
              </div>
              <span className="rounded-full border border-border bg-card px-2.5 py-1 text-xs font-black text-foreground">
                {assayStats.length} assay{assayStats.length === 1 ? "" : "s"}
              </span>
            </div>
            <div className="grid gap-2 lg:grid-cols-2 2xl:grid-cols-3">
              {assayStats.map(({ assay, stats, total }) => (
                <div key={assay} className="glass-card rounded-lg px-3 py-2">
                  <div className="mb-2 flex min-w-0 items-center justify-between gap-2">
                    <span className="truncate text-xs font-black uppercase text-foreground" title={assay}>
                      {assay}
                    </span>
                    <span className="rounded-md bg-muted px-2 py-0.5 text-[0.72rem] font-black text-muted-foreground">
                      {shortCount(total)}
                    </span>
                  </div>
                  <div className="grid grid-cols-4 gap-1.5">
                    {[1, 2, 3, 4].map((tier) => (
                      <div key={tier} className="rounded-md border border-border bg-background px-2 py-1">
                        <div className="flex items-center gap-1.5 text-[0.68rem] font-black uppercase text-muted-foreground">
                          <span className={`h-2 w-2 rounded-full ${tierDotClasses[tier]}`} />
                          T{tier}
                        </div>
                        <div className="text-sm font-black text-foreground">{shortCount(tierCount(stats, tier))}</div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
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
