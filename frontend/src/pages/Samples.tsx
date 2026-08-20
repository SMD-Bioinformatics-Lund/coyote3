import { useEffect, useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link, useSearchParams } from "react-router-dom"
import type { ColumnDef } from "@tanstack/react-table"
import { api } from "@/lib/api"
import { Badge } from "@/components/ui/badge"
import { TableBadge } from "@/components/ui/table-badge"
import { Button } from "@/components/ui/button"
import { FileText, ArrowRight, CalendarDays, Dna, Search as SearchIcon } from "lucide-react"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { Input } from "@/components/ui/input"
import { AppLoader } from "@/components/layout/AppLoader"
import { LayoutDiscoveryBanner } from "@/components/layout/LayoutDiscoveryBanner"
import { PageShell } from "@/components/layout/PageShell"
import { fullDateTime, humanRelativeDate, shortCount } from "@/lib/detail-formatters"
import { sampleDetailPath } from "@/lib/sample-routing"
import { sampleSubpanel } from "@/lib/sample-shape"
import { DataTable } from "@/components/data-table/DataTable"
import { valueBadgeClass } from "@/lib/badge-colors"
import { useUrlTableState } from "@/hooks/useUrlTableState"
import { DEFAULT_ENVIRONMENT } from "@/lib/application-constants"
import { useCurrentUserAccess } from "@/lib/access-control"
import {
  sampleListLayoutForUser,
  sampleListModernViewTriedForUser,
  useUpdateUiSettings,
  type SampleListLayout,
} from "@/lib/user-settings"

type SampleTab = "live" | "reported"
type DateRangePreset = "all" | "today" | "1d" | "3d" | "7d" | "30d" | "custom"

const DATE_RANGE_OPTIONS: Array<{ value: DateRangePreset; label: string }> = [
  { value: "all", label: "All dates" },
  { value: "today", label: "Today" },
  { value: "1d", label: "Last 24 hours" },
  { value: "3d", label: "Last 3 days" },
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "custom", label: "Custom range" },
]

const SAMPLE_LIMIT_OPTIONS = [25, 50, 100, 200]

const BOOLEAN_ANALYSIS_LABELS: Record<string, string> = {
  cov: "Cov",
  biomarkers: "Biomarkers",
  qc: "QC",
  classification: "Classification",
  rna_expr: "Expr",
  rna_expression: "Expr",
  rna_class: "Class",
  rna_classification: "Class",
  rna_qc: "QC",
}

function countBadges(sample: any) {
  const counts = sample?.data_counts || {}
  const numericBadges = [
    counts.snvs !== undefined ? { label: "SNV", value: shortCount(counts.snvs), className: "matte-badge-pass" } : null,
    counts.cnvs !== undefined ? { label: "CNV", value: shortCount(counts.cnvs), className: "matte-badge-pass" } : null,
    counts.fusions !== undefined ? { label: "Fusion", value: shortCount(counts.fusions), className: "matte-badge-pass" } : null,
    counts.translocations !== undefined ? { label: "SV", value: shortCount(counts.translocations), className: "matte-badge-pass" } : null,
  ].filter(Boolean)
  const booleanBadges = Object.entries(counts)
    .filter(([, value]) => typeof value === "boolean")
    .map(([key, value]) => ({
      label: BOOLEAN_ANALYSIS_LABELS[key] || key.replaceAll("_", " ").toUpperCase(),
      className: value ? "matte-badge-pass" : "matte-badge-fail",
    }))

  return [...numericBadges, ...booleanBadges]
}

function localDateBoundary(value: string, nextDay = false) {
  const [year, month, day] = value.split("-").map(Number)
  if (!year || !month || !day) return null
  const boundary = new Date(year, month - 1, day + (nextDay ? 1 : 0))
  return Number.isNaN(boundary.getTime()) ? null : boundary.toISOString()
}

function resolveDateRange(preset: DateRangePreset, customFrom: string, customUntil: string) {
  if (preset === "all") return { addedFrom: null, addedUntil: null }
  if (preset === "custom") {
    return {
      addedFrom: customFrom ? localDateBoundary(customFrom) : null,
      addedUntil: customUntil ? localDateBoundary(customUntil, true) : null,
    }
  }

  const now = new Date()
  if (preset === "today") {
    return {
      addedFrom: new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString(),
      addedUntil: null,
    }
  }
  const days = Number.parseInt(preset, 10)
  return {
    addedFrom: new Date(now.getTime() - days * 24 * 60 * 60 * 1000).toISOString(),
    addedUntil: null,
  }
}

function sampleFindingTotal(sample: any) {
  const counts = sample?.data_counts || {}
  return (
    Number(counts.snvs || 0) +
    Number(counts.cnvs || 0) +
    Number(counts.fusions || 0) +
    Number(counts.translocations || 0)
  )
}

export function Samples() {
  const [searchParams, setSearchParams] = useSearchParams()
  const currentUserQuery = useCurrentUserAccess()
  const updateUiSettings = useUpdateUiSettings()

  // Extract filters from URL
  const category = searchParams.get("panel_type") || searchParams.get("category")
  const assay = searchParams.get("assay")
  const panelTech = searchParams.get("panel_tech")
  const group = searchParams.get("assay_group") || searchParams.get("group")
  const profileScope = searchParams.get("profile_scope") === "all" ? "all" : DEFAULT_ENVIRONMENT
  const activeTab: SampleTab = searchParams.get("sample_tab") === "reported" ? "reported" : "live"
  const searchStr = searchParams.get("search_str") || ""
  const rawDateRange = searchParams.get("date_range") || "all"
  const dateRange: DateRangePreset = DATE_RANGE_OPTIONS.some(({ value }) => value === rawDateRange)
    ? rawDateRange as DateRangePreset
    : "all"
  const customDateFrom = searchParams.get("date_from") || ""
  const customDateUntil = searchParams.get("date_until") || ""
  const requestedLimit = Number(searchParams.get("sample_limit") || 50)
  const sampleLimit = SAMPLE_LIMIT_OPTIONS.includes(requestedLimit) ? requestedLimit : 50
  const sampleListLayout = sampleListLayoutForUser(currentUserQuery.data)
  const modernViewTried = sampleListModernViewTriedForUser(currentUserQuery.data)
  const { addedFrom, addedUntil } = useMemo(
    () => resolveDateRange(dateRange, customDateFrom, customDateUntil),
    [dateRange, customDateFrom, customDateUntil],
  )
  const {
    sorting,
    setSorting,
    updateTableSearchParams,
  } = useUrlTableState({ prefix: "samples" })

  const [searchInput, setSearchInput] = useState(searchStr)
  const [customDateFromDraft, setCustomDateFromDraft] = useState(customDateFrom)
  const [customDateUntilDraft, setCustomDateUntilDraft] = useState(customDateUntil)

  useEffect(() => {
    setCustomDateFromDraft(customDateFrom)
    setCustomDateUntilDraft(customDateUntil)
  }, [customDateFrom, customDateUntil])

  const { data, isLoading, error } = useQuery({
    queryKey: ['samples', category, panelTech, assay, group, profileScope, searchStr, addedFrom, addedUntil, sampleLimit],
    queryFn: () => {
      const params = new URLSearchParams()
      if (category) params.set("panel_type", category)
      if (panelTech) params.set("panel_tech", panelTech)
      if (assay) params.set("assay", assay)
      if (group) params.set("assay_group", group)
      params.set("profile_scope", profileScope)
      if (searchStr) params.set("search_str", searchStr)
      if (addedFrom) params.set("added_from", addedFrom)
      if (addedUntil) params.set("added_until", addedUntil)
      params.set("live_per_page", String(sampleLimit))
      params.set("done_per_page", String(sampleLimit))

      return api.get(`/samples?${params.toString()}`).then(res => res.data)
    }
  })

  const showAllProfiles = profileScope === "all"
  const setProfileScope = (nextScope: typeof DEFAULT_ENVIRONMENT | "all") => {
    const newParams = new URLSearchParams(searchParams)
    if (nextScope === "all") newParams.set("profile_scope", "all")
    else newParams.delete("profile_scope")
    setSearchParams(newParams)
  }
  const setSampleTab = (nextTab: SampleTab) => {
    const newParams = new URLSearchParams(searchParams)
    if (nextTab === "reported") newParams.set("sample_tab", "reported")
    else newParams.delete("sample_tab")
    setSearchParams(newParams)
  }
  const setSampleListLayout = (layout: SampleListLayout) => {
    if (layout === sampleListLayout || updateUiSettings.isPending) return
    updateUiSettings.mutate({
      sample_list_layout: layout,
      ...(layout === "modern" ? { sample_list_modern_view_tried: true } : {}),
    })
  }
  const updateSampleFilter = (key: string, value: string, defaultValue = "") => {
    const newParams = new URLSearchParams(searchParams)
    if (!value || value === defaultValue) newParams.delete(key)
    else newParams.set(key, value)
    setSearchParams(newParams)
  }
  const applyCustomDateRange = () => {
    const newParams = new URLSearchParams(searchParams)
    if (customDateFromDraft) newParams.set("date_from", customDateFromDraft)
    else newParams.delete("date_from")
    if (customDateUntilDraft) newParams.set("date_until", customDateUntilDraft)
    else newParams.delete("date_until")
    setSearchParams(newParams)
  }
  const customDateRangeInvalid = Boolean(
    customDateFromDraft && customDateUntilDraft && customDateFromDraft > customDateUntilDraft,
  )
  const columns = useMemo<ColumnDef<any, any>[]>(() => [
    {
      id: "sample",
      header: "Sample",
      accessorFn: (sample) => sample.name || sample.case_id || "",
      cell: ({ row }) => {
        const sample = row.original
        return (
          <Link to={sampleDetailPath(sample)} className="link-text flex items-center gap-2 font-medium">
            <div className="rounded-lg bg-primary/10 p-1.5 text-primary shadow-sm transition-colors duration-100 group-hover:bg-primary/15">
              <FileText className="h-4 w-4" />
            </div>
            {sample.name || sample.case_id}
          </Link>
        )
      },
      meta: {
        exportValue: (sample: any) => sample.name || sample.case_id || "",
        cellClassName: "min-w-[180px]",
      },
    },
    {
      id: "case_id",
      header: "Case ID",
      accessorFn: (sample) => sample.case_id || sample.case?.id || "",
      cell: ({ row }) => <span className="font-medium">{row.original.case_id || row.original.case?.id || "-"}</span>,
    },
    {
      id: "case_clarity",
      header: "Case Clarity",
      accessorFn: (sample) => sample.case?.clarity_id || "",
      cell: ({ row }) => <span className="text-muted-foreground">{row.original.case?.clarity_id || "-"}</span>,
    },
    {
      id: "control",
      header: "Control",
      accessorFn: (sample) => sample.control_id || sample.control?.id || "",
      cell: ({ row }) => <span className="font-medium">{row.original.control_id || row.original.control?.id || "-"}</span>,
    },
    {
      id: "control_clarity",
      header: "Control Clarity",
      accessorFn: (sample) => sample.control?.clarity_id || "",
      cell: ({ row }) => <span className="text-muted-foreground">{row.original.control?.clarity_id || "-"}</span>,
    },
    {
      id: "environment",
      header: "Profile",
      accessorFn: (sample) => sample.environment || "",
      cell: ({ row }) => (
        <TableBadge className={`${valueBadgeClass(row.original.environment || "")} uppercase`}>
          {row.original.environment[0] || "-"}
        </TableBadge>
      ),
    },
    {
      id: "asp_id",
      header: "Assay",
      accessorFn: (sample) => sample.asp_id || "",
      cell: ({ row }) => <span className="font-medium">{row.original.asp_id || "-"}</span>,
    },
    {
      id: "subpanel",
      header: "Subpanel",
      accessorFn: (sample) => sampleSubpanel(sample) || "",
      cell: ({ row }) => <span className="font-medium text-muted-foreground">{sampleSubpanel(row.original) || "-"}</span>,
    },
    {
      id: "pipeline",
      header: "Pipeline",
      accessorFn: (sample) =>
        [sample.pipeline, sample.pipeline_version].filter(Boolean).join(" "),
      cell: ({ row }) => {
        const { pipeline, pipeline_version: version } = row.original

        return (
          <span className="font-medium text-muted-foreground">
            {pipeline ? `${pipeline}${version ? ` (${version})` : ""}` : "-"}
          </span>
        )
      },
    },
    {
      id: "analysis",
      header: "Analysis",
      accessorFn: (sample) => sample.ingest_status || "",
      cell: ({ row }) => (
        <TableBadge
          className={
            row.original.ingest_status === "ready"
              ? "border-pass/30 bg-pass/15 text-pass hover:bg-pass/20"
              : "border-border bg-muted text-muted-foreground"
          }
        >
          {row.original.ingest_status || "-"}
        </TableBadge>
      ),
    },
    {
      id: "data",
      header: "Data",
      accessorFn: sampleFindingTotal,
      cell: ({ row }) => {
        const badges = countBadges(row.original)
        return (
          <div className="flex flex-wrap gap-1">
            {badges.length ? badges.map((item: any) => (
              <TableBadge key={item.label} className={item.className}>
                {item.value === undefined ? item.label : `${item.label} ${item.value}`}
              </TableBadge>
            )) : <span className="text-muted-foreground">-</span>}
          </div>
        )
      },
      meta: {
        exportValue: (sample: any) => {
          const counts = sample?.data_counts || {}
          return [
            counts.snvs !== undefined ? `SNV ${counts.snvs}` : "",
            counts.cnvs !== undefined ? `CNV ${counts.cnvs}` : "",
            counts.fusions !== undefined ? `Fusion ${counts.fusions}` : "",
            counts.translocations !== undefined ? `SV ${counts.translocations}` : "",
            ...Object.entries(counts)
              .filter(([, value]) => value === true)
              .map(([key]) => BOOLEAN_ANALYSIS_LABELS[key] || key.replaceAll("_", " ")),
          ].filter(Boolean).join("; ")
        },
        cellClassName: "min-w-[220px]",
      },
    },
    {
      id: "added",
      header: "Added",
      accessorFn: (sample) => sample.time_added ? new Date(sample.time_added).getTime() : 0,
      cell: ({ row }) => (
        <span className="whitespace-nowrap font-medium text-muted-foreground" title={fullDateTime(row.original.time_added)}>
          {humanRelativeDate(row.original.time_added)}
        </span>
      ),
      meta: {
        exportValue: (sample: any) => fullDateTime(sample.time_added),
        cellClassName: "whitespace-nowrap",
      },
    },
    {
      id: "actions",
      header: "Actions",
      enableSorting: false,
      cell: ({ row }) => (
        <Link to={sampleDetailPath(row.original)}>
          <Button variant="ghost" size="icon-xs" className="rounded-md shadow-sm hover:bg-primary hover:text-primary-foreground">
            <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
      ),
      meta: {
        headerClassName: "text-center",
        cellClassName: "text-center",
      },
    },
  ], [])
  const liveSamples = data?.live_samples || []
  const reportedSamples = data?.done_samples || []
  const samples = activeTab === "reported" ? reportedSamples : liveSamples

  const renderSampleTable = (rows: any[], state: SampleTab) => (
    <DataTable
      columns={columns}
      data={rows}
      filename={`${state}_samples.csv`}
      rowLabel="samples"
      totalCount={rows.length}
      hideSearch
      stateKey={`samples.${state}`}
      sortingState={sorting}
      onSortingChange={(value) => {
        setSorting(value)
        updateTableSearchParams({ sorting: value })
      }}
      getRowClassName={() => "group"}
      renderToolbar={() => rows.length === 0 ? (
        <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
          <Dna className="h-4 w-4 text-muted-foreground/50" />
          No samples found.
        </div>
      ) : null}
    />
  )

  if (isLoading) {
    return <AppLoader label="Loading samples" />
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-destructive/10 text-destructive border-l-4 border-destructive p-4 rounded">
          <p className="font-bold">Failed to load samples</p>
          <p>{error instanceof Error ? error.message : "Unknown error"}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col bg-muted/20">
      <PageShell
        eyebrow="Cases"
        title="Samples"
        description="Manage and analyze loaded genomic cases."
        actions={
          <div className="flex flex-wrap items-center justify-end gap-2">
            <SegmentedControl
              ariaLabel="Sample profile scope"
              value={showAllProfiles ? "all" : "production"}
              onValueChange={(scope) => setProfileScope(scope === "all" ? "all" : DEFAULT_ENVIRONMENT)}
              items={[
                { value: "production", label: "Production" },
                { value: "all", label: "All profiles" },
              ]}
            />
            <form
              onSubmit={(e) => {
                e.preventDefault()
                const newParams = new URLSearchParams(searchParams)
                if (searchInput) newParams.set("search_str", searchInput)
                else newParams.delete("search_str")
                setSearchParams(newParams)
              }}
              className="relative flex items-center gap-2"
            >
              <div className="relative">
                <SearchIcon className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-primary/75" />
                <Input
                  type="text"
                  placeholder="Search by Case ID..."
                  className="w-[220px] rounded-xl pl-9 lg:w-[320px]"
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                />
              </div>
              <Button type="submit">Search</Button>
            </form>
          </div>
        }
      >

        {/* Filters Summary */}
        {(category || assay || group || searchStr || showAllProfiles || dateRange !== "all") && (
          <div className="glass-card flex items-center gap-2 text-sm text-muted-foreground px-5 py-3">
            <span className="mr-2 text-xs font-semibold uppercase tracking-wider">Active Filters</span>
            <Badge variant="secondary" className="uppercase bg-primary/10 text-primary hover:bg-primary/20 rounded-md">{showAllProfiles ? "all profiles" : DEFAULT_ENVIRONMENT}</Badge>
            {searchStr && <Badge variant="secondary" className="bg-primary/10 text-primary hover:bg-primary/20 rounded-md">Search: {searchStr}</Badge>}
            {category && <Badge variant="secondary" className="uppercase bg-primary/20 text-primary hover:bg-primary/30 rounded-md">{category}</Badge>}
            {panelTech && <Badge variant="secondary" className="uppercase bg-primary/20 text-primary hover:bg-primary/30 rounded-md">{panelTech}</Badge>}
            {assay && <Badge variant="secondary" className="uppercase bg-primary/20 text-primary hover:bg-primary/30 rounded-md">{assay}</Badge>}
            {group && <Badge variant="secondary" className="uppercase bg-secondary text-secondary-foreground hover:bg-secondary/80 rounded-md shadow-sm">{group}</Badge>}
            {dateRange !== "all" && <Badge variant="secondary" className="bg-primary/10 text-primary hover:bg-primary/20 rounded-md">{DATE_RANGE_OPTIONS.find(({ value }) => value === dateRange)?.label}</Badge>}
            <Link to="/samples" className="text-xs font-bold text-destructive hover:underline ml-auto bg-destructive/10 px-3 py-1 rounded-md" onClick={() => setSearchInput("")}>Clear All</Link>
          </div>
        )}

        <div className="glass-card border-border/50 p-4">
          <div className="mb-3 flex flex-wrap items-end gap-3 border-b border-border/60 pb-3" aria-label="Sample date and limit filters">
            <div className="space-y-1">
              <label htmlFor="sample-date-range" className="block text-[11px] font-semibold text-muted-foreground">Date added</label>
              <div className="relative">
                <CalendarDays className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <select
                  id="sample-date-range"
                  className="paper-inset h-9 min-w-[165px] rounded-lg pl-9 pr-8 text-sm font-medium"
                  value={dateRange}
                  onChange={(event) => updateSampleFilter("date_range", event.target.value, "all")}
                >
                  {DATE_RANGE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </div>
            </div>
            {dateRange === "custom" && (
              <>
                <div className="space-y-1">
                  <label htmlFor="sample-date-from" className="block text-[11px] font-semibold text-muted-foreground">From</label>
                  <Input
                    id="sample-date-from"
                    type="date"
                    className="h-9 w-[155px]"
                    value={customDateFromDraft}
                    onChange={(event) => setCustomDateFromDraft(event.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <label htmlFor="sample-date-until" className="block text-[11px] font-semibold text-muted-foreground">Until</label>
                  <Input
                    id="sample-date-until"
                    type="date"
                    className="h-9 w-[155px]"
                    value={customDateUntilDraft}
                    onChange={(event) => setCustomDateUntilDraft(event.target.value)}
                    aria-invalid={customDateRangeInvalid || undefined}
                  />
                </div>
                <Button
                  type="button"
                  variant="secondary"
                  className="h-9"
                  disabled={customDateRangeInvalid}
                  onClick={applyCustomDateRange}
                >
                  Apply dates
                </Button>
              </>
            )}
            <div className="space-y-1">
              <label htmlFor="sample-row-limit" className="block text-[11px] font-semibold text-muted-foreground">Maximum rows</label>
              <select
                id="sample-row-limit"
                className="paper-inset h-9 min-w-[105px] rounded-lg px-3 text-sm font-medium"
                value={sampleLimit}
                onChange={(event) => updateSampleFilter("sample_limit", event.target.value, "50")}
              >
                {SAMPLE_LIMIT_OPTIONS.map((limit) => <option key={limit} value={limit}>{limit}</option>)}
              </select>
            </div>
            <div className="ml-auto space-y-1">
              <span className="block text-[11px] font-semibold text-muted-foreground">Layout</span>
              <SegmentedControl
                ariaLabel="Sample list layout"
                value={sampleListLayout}
                onValueChange={(value) => setSampleListLayout(value as SampleListLayout)}
                items={[
                  { value: "classic", label: "Classic" },
                  { value: "modern", label: "Modern" },
                ]}
              />
            </div>
            {customDateRangeInvalid && (
              <p className="w-full text-xs font-medium text-destructive" role="alert">
                The From date must be before or equal to the Until date.
              </p>
            )}
          </div>
          {sampleListLayout === "classic" && !modernViewTried && (
            <div className="mb-3">
              <LayoutDiscoveryBanner onTryModern={() => setSampleListLayout("modern")} />
            </div>
          )}
          {sampleListLayout === "modern" ? (
            <>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-3 border-b border-border/60 pb-3">
                <SegmentedControl
                  ariaLabel="Sample state"
                  value={activeTab}
                  onValueChange={setSampleTab}
                  items={[
                    { value: "live", label: <>Live samples <span className="ml-1.5 rounded-full bg-background/75 px-1.5 py-0.5 text-[10px] text-foreground">{shortCount(liveSamples.length)}</span></> },
                    { value: "reported", label: <>Reported samples <span className="ml-1.5 rounded-full bg-background/75 px-1.5 py-0.5 text-[10px] text-foreground">{shortCount(reportedSamples.length)}</span></> },
                  ]}
                />
                <p className="text-xs font-semibold text-muted-foreground">
                  {activeTab === "reported"
                    ? "Samples with saved clinical reports."
                    : "Samples awaiting review or active analysis."}
                </p>
              </div>
              {renderSampleTable(samples, activeTab)}
            </>
          ) : (
            <div className="space-y-5">
              <section aria-labelledby="live-samples-heading">
                <div className="mb-2 flex items-center justify-between border-b border-border/60 pb-2">
                  <div>
                    <h2 id="live-samples-heading" className="text-sm font-semibold">Live samples</h2>
                    <p className="text-xs text-muted-foreground">Samples awaiting review or active analysis.</p>
                  </div>
                  <Badge variant="secondary">{shortCount(liveSamples.length)}</Badge>
                </div>
                {renderSampleTable(liveSamples, "live")}
              </section>
              <section aria-labelledby="reported-samples-heading">
                <div className="mb-2 flex items-center justify-between border-b border-border/60 pb-2">
                  <div>
                    <h2 id="reported-samples-heading" className="text-sm font-semibold">Reported samples</h2>
                    <p className="text-xs text-muted-foreground">Samples with saved clinical reports.</p>
                  </div>
                  <Badge variant="secondary">{shortCount(reportedSamples.length)}</Badge>
                </div>
                {renderSampleTable(reportedSamples, "reported")}
              </section>
            </div>
          )}
        </div>
      </PageShell>
    </div>
  )
}
