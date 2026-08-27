import { useMemo, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { ChevronDown, Search, X } from "lucide-react"
import { api } from "@/lib/api"
import { DataTable } from "@/components/data-table/DataTable"
import { TableBadge } from "@/components/ui/table-badge"
import { ExpandableText } from "@/components/detail/ExpandableText"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { TierBadge } from "@/lib/variant-ui"
import { sampleDetailPath } from "@/lib/sample-routing"
import { shortCount } from "@/lib/detail-formatters"
import { valueBadgeClass } from "@/lib/badge-colors"
import { ColumnDef } from "@tanstack/react-table"
import { useUrlTableState } from "@/hooks/useUrlTableState"
import { tieredVariantSearchState } from "@/lib/variant-routing"
import { NOMENCLATURE_CODES, nomenclatureLabel } from "@/lib/application-constants"

const tierBarClasses = ["", "bg-tier1", "bg-tier2", "bg-tier3", "bg-tier4"]
const tierTextClasses = ["", "text-tier1", "text-tier2", "text-tier3", "text-tier4"]
const tierHeaderClasses = ["", "bg-tier-header1", "bg-tier-header2", "bg-tier-header3", "bg-tier-header4"]

function tierCount(stats: Record<string, unknown>, tier: number) {
  return Number(stats?.[`tier${tier}`] || 0)
}

function totalTierCount(stats: Record<string, unknown>) {
  return [1, 2, 3, 4].reduce((total, tier) => total + tierCount(stats, tier), 0)
}

export function normalizeTieredSearch(value: string, mode: string) {
  const normalized = value.trim()
  if (mode === "gene") return normalized.toUpperCase()
  if (mode === "subpanel") return normalized.toLowerCase()
  return normalized
}

function findingVariantText(row: any) {
  const isSmallVariant = ["p", "c", "g"].includes(String(row.nomenclature || "").toLowerCase())
    || String(row.analysis_type || row.finding_type || "").toUpperCase() === "SNV"
  if (!isSmallVariant) return row.variant || row.identity || row.hgvsp || row.hgvsc || "-"
  return [row.hgvsc, row.hgvsp || row.variant].filter(Boolean).join("\n") || row.variant || "-"
}

function findingScopeValues(
  row: any,
  listKey: "assay_groups" | "subpanels",
  sampleKey: "assay_group" | "subpanel_id",
) {
  const scalarKey = listKey === "assay_groups" ? "assay_group" : "subpanel"
  return Array.from(new Set([
    ...(Array.isArray(row[listKey]) ? row[listKey] : []),
    row[scalarKey],
    ...Object.values(row.samples || {}).map((sample: any) => sample?.[sampleKey]),
  ].map((value) => String(value || "").trim()).filter(Boolean)))
}

export function TieredFindingSamplesCell({ samplesById }: { samplesById: Record<string, any> }) {
  const [expanded, setExpanded] = useState(false)
  const samples = (Object.values(samplesById || {}) as any[]).sort((left, right) =>
    String(left.sample_name || left.name || "").localeCompare(String(right.sample_name || right.name || "")),
  )
  if (!samples.length) return <span className="text-muted-foreground">-</span>

  const visible = expanded ? samples : samples.slice(0, 5)
  return (
    <div className="flex min-w-52 flex-col gap-1.5">
      {visible.map((sample: any, index) => {
        const sampleId = sample.name || sample.sample_name || sample.sample_id || sample._id || sample.id || sample.sample_oid
        const sampleLabel = sample.sample_name || sample.name || "sample"
        const latestReportNumber = sample.latest_report_num
        return (
          <Link
            key={sampleId || index}
            to={sampleDetailPath(sample, sampleId)}
            className="link-text block truncate"
            title={[sampleLabel, latestReportNumber != null ? `latest report ${latestReportNumber}` : null].filter(Boolean).join(": ")}
          >
            {sampleLabel}{latestReportNumber != null ? `: ${latestReportNumber}` : ""}
          </Link>
        )
      })}
      {samples.length > 5 && (
        <button
          type="button"
          className="w-fit text-left type-meta text-link hover:underline"
          onClick={() => setExpanded((current) => !current)}
        >
          {expanded ? "Show fewer" : `Show ${samples.length - 5} more`}
        </button>
      )}
    </div>
  )
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
  const [selectedNomenclatures, setSelectedNomenclatures] = useState<string[]>(initialSearchState.nomenclatures)
  const [appliedNomenclatures, setAppliedNomenclatures] = useState<string[]>(initialSearchState.nomenclatures)
  const {
    sorting,
    setSorting,
    updateTableSearchParams,
  } = useUrlTableState({ prefix: "tiered_variants" })

  const { data, isLoading, error } = useQuery({
    queryKey: ["tiered-variant-search", appliedSearch, appliedMode, appliedIncludeText, appliedAssays, appliedNomenclatures],
    queryFn: () => {
      const params = new URLSearchParams()
      if (appliedSearch) params.set("search_str", appliedSearch)
      params.set("search_mode", appliedMode)
      params.set("include_annotation_text", String(appliedIncludeText))
      appliedAssays.forEach((assay) => params.append("assays", assay))
      appliedNomenclatures.forEach((value) => params.append("nomenclatures", value))
      return api.get(`/common/search/tiered_variants?${params.toString()}`).then((res) => res.data)
    },
  })
  const assayChoices = data?.assay_choices || []
  const nomenclatureChoices = data?.nomenclature_choices || NOMENCLATURE_CODES
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
    const normalizedSearch = normalizeTieredSearch(search, mode)
    setSearch(normalizedSearch)
    setAppliedSearch(normalizedSearch)
    setAppliedMode(mode)
    setAppliedIncludeText(includeText)
    setAppliedAssays(selectedAssays)
    setAppliedNomenclatures(selectedNomenclatures)
    const params = new URLSearchParams(searchParams)
    params.delete("search_str")
    params.delete("search_mode")
    params.delete("include_annotation_text")
    params.delete("assays")
    params.delete("nomenclatures")
    if (normalizedSearch) params.set("search_str", normalizedSearch)
    params.set("search_mode", mode)
    if (includeText) params.set("include_annotation_text", "true")
    selectedAssays.forEach((assay) => params.append("assays", assay))
    selectedNomenclatures.forEach((value) => params.append("nomenclatures", value))
    setSearchParams(params, { replace: true })
  }

  const clearSearch = () => {
    setSearch("")
    setMode("variant")
    setIncludeText(false)
    setSelectedAssays([])
    setSelectedNomenclatures([])
    setAppliedSearch("")
    setAppliedMode("variant")
    setAppliedIncludeText(false)
    setAppliedAssays([])
    setAppliedNomenclatures([])
    const params = new URLSearchParams(searchParams)
    params.delete("search_str")
    params.delete("search_mode")
    params.delete("include_annotation_text")
    params.delete("assays")
    params.delete("nomenclatures")
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
      id: "analysis_type",
      header: "Type",
      accessorFn: (row) => row.analysis_type || row.finding_type || "FINDING",
      cell: ({ row }) => (
        <TableBadge className={valueBadgeClass(String(row.getValue("analysis_type")))}>
          {String(row.getValue("analysis_type"))}
        </TableBadge>
      ),
    },
    {
      id: "genes",
      header: "Gene(s)",
      accessorFn: (row) => (row.genes || [row.gene, row.gene1, row.gene2].filter(Boolean)).join(" / ") || "-",
      cell: ({ row }) => {
        const genes = Array.from(new Set(
          (row.original.genes || [row.original.gene, row.original.gene1, row.original.gene2])
            .map((gene: unknown) => String(gene || "").trim())
            .filter(Boolean),
        )) as string[]
        if (!genes.length) return <span className="text-muted-foreground">-</span>
        return (
          <div className="flex flex-wrap items-center gap-x-1">
            {genes.map((gene, index) => (
              <span key={gene} className="inline-flex items-center gap-x-1">
                {index > 0 && <span className="text-muted-foreground">/</span>}
                <Link to={`/public/gene/${encodeURIComponent(gene)}/info`} className="link-text font-semibold">
                  {gene}
                </Link>
              </span>
            ))}
          </div>
        )
      },
    },
    {
      id: "variant",
      header: "Variant",
      accessorFn: findingVariantText,
      meta: { headerClassName: "w-56 min-w-52", cellClassName: "w-56 min-w-52" },
      cell: ({ row }) => (
        <div className="w-52 space-y-0.5">
          {String(row.getValue("variant") || "-").split("\n").map((value, index) => (
            <ExpandableText
              key={`${value}-${index}`}
              text={value}
              maxLength={34}
              className={index === 0 ? "type-meta text-muted-foreground" : "type-table-cell text-foreground"}
            />
          ))}
        </div>
      ),
    },
    {
      id: "nomenclature",
      header: "Nomenclature",
      accessorFn: (row) => row.nomenclature || "-",
      cell: ({ row }) => <TableBadge className="badge-neutral">{nomenclatureLabel(row.getValue("nomenclature"))}</TableBadge>,
    },
    {
      id: "genomic",
      header: "Genomic",
      accessorFn: (row) => row.genomic || "-",
      cell: ({ row }) => <ExpandableText text={String(row.getValue("genomic"))} maxLength={32} className="type-meta text-muted-foreground" />,
    },
    {
      id: "transcript",
      header: "Transcript",
      accessorFn: (row) => row.transcript || "-",
      cell: ({ row }) => <span className="text-xs text-muted-foreground">{String(row.getValue("transcript"))}</span>,
    },
    {
      id: "assay_group",
      header: "Assay group",
      accessorFn: (row) => findingScopeValues(row, "assay_groups", "assay_group").join(", ") || "-",
      cell: ({ row }) => (
        <div className="flex flex-wrap gap-1">
          {findingScopeValues(row.original, "assay_groups", "assay_group").map((value) => (
            <TableBadge key={value} className={valueBadgeClass(value)}>{value}</TableBadge>
          ))}
        </div>
      ),
    },
    {
      id: "subpanel",
      header: "Subpanel",
      accessorFn: (row) => findingScopeValues(row, "subpanels", "subpanel_id").join(", ") || "-",
      cell: ({ row }) => (
        <div className="flex flex-wrap gap-1">
          {findingScopeValues(row.original, "subpanels", "subpanel_id").map((value) => (
            <TableBadge key={value} className="badge-neutral">{value}</TableBadge>
          ))}
        </div>
      ),
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
      cell: ({ row }) => <TieredFindingSamplesCell samplesById={row.original.samples || {}} />,
    },
  ], [])

  return (
    <PageShell
      eyebrow="Common"
      title="Tiered Variant Search"
      description="Search tiered SNVs, CNVs, fusions, translocations, and annotation text across reports and assays."
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
              placeholder="Search gene, finding, annotation..."
              className="w-full rounded-lg border border-input bg-background py-2 pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-primary/40"
            />
          </div>
          <select
            value={mode}
            onChange={(event) => setMode(event.target.value)}
            className="rounded-lg border border-input bg-background px-3 py-2 text-sm"
          >
            <option value="variant">Finding identity</option>
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
            <div className="mb-2 type-label text-muted-foreground">Assay groups</div>
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

        {nomenclatureChoices.length > 0 && (
          <div className="mb-3 rounded-xl border border-border bg-background/70 p-3">
            <div className="mb-2 type-label text-muted-foreground">Nomenclature</div>
            <div className="flex flex-wrap gap-2">
              {nomenclatureChoices.map((value: string) => (
                <label key={value} className="inline-flex items-center gap-2 rounded-lg border border-border bg-card/80 px-2.5 py-1.5 type-body-sm hover:bg-surface-hover">
                  <input
                    type="checkbox"
                    checked={selectedNomenclatures.includes(value)}
                    onChange={(event) => setSelectedNomenclatures((current) => event.target.checked
                      ? [...current, value]
                      : current.filter((item) => item !== value))}
                  />
                  {nomenclatureLabel(value)}
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
                <span className="float-right ">{data.tier_stats.total[`tier${tier}`] || 0}</span>
              </div>
            ))}
          </div>
        )}

        {assayStats.length > 0 && (
          <details className="group mb-3 overflow-hidden rounded-xl border border-border bg-card">
            <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-3 px-4 py-3 marker:hidden hover:bg-muted/30">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Assay distribution</div>
                <div className="text-xs text-muted-foreground">Tiered clinical findings by assay for the current search.</div>
              </div>
              <div className="flex items-center gap-2 text-xs font-bold text-muted-foreground">
                <span>{assayStats.length} assay{assayStats.length === 1 ? "" : "s"}</span>
                <ChevronDown className="h-4 w-4 transition-transform duration-150 group-open:rotate-180" />
              </div>
            </summary>
            <div className="overflow-x-auto border-t border-border">
              <table className="type-table-cell w-full min-w-[42rem] border-collapse">
                <thead className="type-table-header bg-muted/45 text-left text-muted-foreground">
                  <tr>
                    <th className="px-4 py-2 font-medium">Assay</th>
                    <th className="w-full min-w-48 px-4 py-2 font-medium">Distribution</th>
                    {[1, 2, 3, 4].map((tier) => (
                      <th key={tier} className={`w-16 px-3 py-2 text-right font-medium ${tierTextClasses[tier]}`}>
                        Tier {tier}
                      </th>
                    ))}
                    <th className="w-16 px-4 py-2 text-right font-medium">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {assayStats.map(({ assay, stats, total }) => (
                    <tr key={assay} className="hover:bg-muted/25">
                      <th scope="row" className="max-w-48 truncate px-4 py-2.5 text-left font-semibold uppercase text-foreground" title={assay}>
                        {assay}
                      </th>
                      <td className="px-4 py-2.5">
                        <div
                          className="flex h-3 min-w-48 overflow-hidden rounded-full bg-muted"
                          aria-label={`${assay}: ${total} tiered findings`}
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
                        <td key={tier} className={`px-3 py-2.5 text-right font-bold type-numeric ${tierTextClasses[tier]}`}>
                          {shortCount(tierCount(stats, tier))}
                        </td>
                      ))}
                      <td className="px-4 py-2.5 text-right text-sm font-semibold type-numeric text-foreground" title={`${total} total findings`}>
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
          <AppLoader label="Loading tiered finding search" />
        ) : error ? (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
            {error instanceof Error ? error.message : "Unable to search tiered findings"}
          </div>
        ) : (
          <DataTable
            columns={columns}
            data={data?.docs || []}
            filename="tiered_findings.csv"
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
