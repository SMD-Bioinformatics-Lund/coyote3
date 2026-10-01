import { DataTable } from "@/components/data-table/DataTable"
import { PageSizeSelect } from "@/components/data-table/PageSizeSelect"
import { useTablePreferences } from "@/components/data-table/table-preferences"
import {
  DateRangeFilter,
} from "@/components/filters/DateRangeFilter"
import {
  dateRangeLabel,
  parseDateRangePreset,
  resolveDateRange,
} from "@/components/filters/date-range"
import { AppLoader } from "@/components/layout/AppLoader"
import { LayoutDiscoveryBanner } from "@/components/layout/LayoutDiscoveryBanner"
import { PageShell } from "@/components/layout/PageShell"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { useUrlTableState } from "@/hooks/useUrlTableState"
import { useCurrentUserAccess } from "@/lib/access-control"
import { api } from "@/lib/api"
import { DEFAULT_ENVIRONMENT } from "@/lib/application-constants"
import { shortCount } from "@/lib/detail-formatters"
import {
  sampleListLayoutForUser,
  sampleListModernViewTriedForUser,
  TABLE_PAGE_SIZE_OPTIONS,
  useUpdateUiSettings,
  type SampleListLayout,
} from "@/lib/user-settings"
import { useQuery } from "@tanstack/react-query"
import { Dna, Search as SearchIcon } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { DEFAULT_LIVE_SORTING, DEFAULT_REPORTED_SORTING, positivePage, resetSamplePagination, type SampleTab } from "./sample-list-presentation"
import { useSampleColumns, useSampleExportColumns } from "./useSampleColumns"

export function Samples() {
  const [searchParams, setSearchParams] = useSearchParams()
  const currentUserQuery = useCurrentUserAccess()
  const updateUiSettings = useUpdateUiSettings()
  const { pageSize: preferredPageSize, setPageSize: persistPageSize } = useTablePreferences()

  // Extract filters from URL
  const category = searchParams.get("panel_type") || searchParams.get("category")
  const assay = searchParams.get("assay")
  const panelTech = searchParams.get("panel_tech")
  const group = searchParams.get("assay_group") || searchParams.get("group")
  const profileScope = searchParams.get("profile_scope") === "all" ? "all" : DEFAULT_ENVIRONMENT
  const activeTab: SampleTab = searchParams.get("sample_tab") === "reported" ? "reported" : "live"
  const searchStr = searchParams.get("search_str") || ""
  const dateRange = parseDateRangePreset(searchParams.get("date_range"))
  const customDateFrom = searchParams.get("date_from") || ""
  const customDateUntil = searchParams.get("date_until") || ""
  const requestedPageSize = Number(searchParams.get("sample_per_page") || preferredPageSize)
  const samplePageSize = TABLE_PAGE_SIZE_OPTIONS.includes(requestedPageSize as typeof TABLE_PAGE_SIZE_OPTIONS[number])
    ? requestedPageSize
    : preferredPageSize
  const livePage = positivePage(searchParams.get("live_page"))
  const reportedPage = positivePage(searchParams.get("reported_page"))
  const sampleListLayout = sampleListLayoutForUser(currentUserQuery.data)
  const modernViewTried = sampleListModernViewTriedForUser(currentUserQuery.data)
  const { addedFrom, addedUntil } = useMemo(
    () => resolveDateRange(dateRange, customDateFrom, customDateUntil),
    [dateRange, customDateFrom, customDateUntil],
  )
  const liveTableState = useUrlTableState({ prefix: "live" })
  const reportedTableState = useUrlTableState({ prefix: "reported" })
  const liveSorting = liveTableState.sorting.length ? liveTableState.sorting : DEFAULT_LIVE_SORTING
  const reportedSorting = reportedTableState.sorting.length
    ? reportedTableState.sorting
    : DEFAULT_REPORTED_SORTING
  const liveSortParam = liveTableState.sortParam || "added:desc"
  const reportedSortParam = reportedTableState.sortParam || "latest_reported:desc"

  const [searchInput, setSearchInput] = useState(searchStr)
  const [customDateFromDraft, setCustomDateFromDraft] = useState(customDateFrom)
  const [customDateUntilDraft, setCustomDateUntilDraft] = useState(customDateUntil)

  useEffect(() => {
    setCustomDateFromDraft(customDateFrom)
    setCustomDateUntilDraft(customDateUntil)
  }, [customDateFrom, customDateUntil])

  const { data, isLoading, error } = useQuery({
    queryKey: ['samples', category, panelTech, assay, group, profileScope, searchStr, addedFrom, addedUntil, livePage, reportedPage, samplePageSize, liveSortParam, reportedSortParam],
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
      params.set("live_page", String(livePage))
      params.set("done_page", String(reportedPage))
      params.set("live_per_page", String(samplePageSize))
      params.set("done_per_page", String(samplePageSize))
      params.set("live_sort", liveSortParam)
      params.set("reported_sort", reportedSortParam)

      return api.get(`/samples?${params.toString()}`).then(res => res.data)
    }
  })

  const showAllProfiles = profileScope === "all"
  const setProfileScope = (nextScope: typeof DEFAULT_ENVIRONMENT | "all") => {
    const newParams = new URLSearchParams(searchParams)
    if (nextScope === "all") newParams.set("profile_scope", "all")
    else newParams.delete("profile_scope")
    resetSamplePagination(newParams)
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
    resetSamplePagination(newParams)
    setSearchParams(newParams)
  }
  const applyCustomDateRange = () => {
    const newParams = new URLSearchParams(searchParams)
    if (customDateFromDraft) newParams.set("date_from", customDateFromDraft)
    else newParams.delete("date_from")
    if (customDateUntilDraft) newParams.set("date_until", customDateUntilDraft)
    else newParams.delete("date_until")
    resetSamplePagination(newParams)
    setSearchParams(newParams)
  }
  const setSamplePage = (state: SampleTab, pageNumber: number) => {
    const newParams = new URLSearchParams(searchParams)
    const key = state === "live" ? "live_page" : "reported_page"
    if (pageNumber <= 1) newParams.delete(key)
    else newParams.set(key, String(pageNumber))
    setSearchParams(newParams)
  }
  const columns = useSampleColumns()
  const liveColumns = useMemo(
    () => columns.filter((column) => column.id !== "latest_reported"),
    [columns],
  )
  const liveSamples = useMemo<any[]>(() => data?.live_samples ?? [], [data?.live_samples])
  const reportedSamples = useMemo<any[]>(() => data?.done_samples ?? [], [data?.done_samples])
  const liveTotal = Number(data?.live_total ?? liveSamples.length)
  const reportedTotal = Number(data?.done_total ?? reportedSamples.length)
  const samples = activeTab === "reported" ? reportedSamples : liveSamples
  const sampleExportColumns = useSampleExportColumns(liveSamples, reportedSamples)

  const renderSampleTable = (rows: any[], state: SampleTab) => (
    <DataTable
      columns={state === "reported" ? columns : liveColumns}
      data={rows}
      filename={`${state}_samples.csv`}
      exportColumns={sampleExportColumns}
      rowLabel="samples"
      totalCount={state === "live" ? liveTotal : reportedTotal}
      page={state === "live" ? livePage : reportedPage}
      perPage={samplePageSize}
      hasNext={Boolean(state === "live" ? data?.has_next_live : data?.has_next_done)}
      hasPrevious={(state === "live" ? livePage : reportedPage) > 1}
      onPageChange={(nextPage) => setSamplePage(state, nextPage)}
      hideSearch
      stateKey={`samples.${state}`}
      sortingState={state === "reported" ? reportedSorting : liveSorting}
      manualSorting
      onSortingChange={(value) => {
        const tableState = state === "reported" ? reportedTableState : liveTableState
        tableState.setSorting(value)
        tableState.updateTableSearchParams({ page: 1, sorting: value })
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
                resetSamplePagination(newParams)
                setSearchParams(newParams)
              }}
              className="relative flex items-center gap-2"
            >
              <div className="relative">
                <SearchIcon className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-primary/75" />
                <Input
                  type="text"
                  placeholder="Search samples..."
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
            {dateRange !== "all" && <Badge variant="secondary" className="bg-primary/10 text-primary hover:bg-primary/20 rounded-md">{dateRangeLabel(dateRange)}</Badge>}
            <Link to="/samples" className="text-xs font-bold text-destructive hover:underline ml-auto bg-destructive/10 px-3 py-1 rounded-md" onClick={() => setSearchInput("")}>Clear All</Link>
          </div>
        )}

        <div className="glass-card border-border/50 p-4">
          <div className="mb-3 flex flex-wrap items-end gap-3 border-b border-border/60 pb-3" aria-label="Sample date and limit filters">
            <DateRangeFilter
              idPrefix="sample-date"
              preset={dateRange}
              from={customDateFromDraft}
              until={customDateUntilDraft}
              onPresetChange={(preset) => updateSampleFilter("date_range", preset, "all")}
              onFromChange={setCustomDateFromDraft}
              onUntilChange={setCustomDateUntilDraft}
              onApply={applyCustomDateRange}
            />
            <div className="space-y-1">
              <label htmlFor="sample-page-size" className="block type-meta font-semibold text-muted-foreground">Maximum rows per page</label>
              <PageSizeSelect
                id="sample-page-size"
                className="h-9 min-w-[105px] px-3 text-sm font-medium"
                value={samplePageSize}
                onValueChange={(nextPageSize) => {
                  persistPageSize(nextPageSize)
                  updateSampleFilter("sample_per_page", String(nextPageSize), String(preferredPageSize))
                }}
              />
            </div>
            <div className="ml-auto space-y-1">
              <span className="block type-meta font-semibold text-muted-foreground">Layout</span>
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
                    { value: "live", label: <>Live samples <span className="ml-1.5 rounded-full bg-background/75 px-1.5 py-0.5 type-label text-foreground">{shortCount(liveTotal)}</span></> },
                    { value: "reported", label: <>Reported samples <span className="ml-1.5 rounded-full bg-background/75 px-1.5 py-0.5 type-label text-foreground">{shortCount(reportedTotal)}</span></> },
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
                  <Badge variant="secondary">{shortCount(liveTotal)}</Badge>
                </div>
                {renderSampleTable(liveSamples, "live")}
              </section>
              <section aria-labelledby="reported-samples-heading">
                <div className="mb-2 flex items-center justify-between border-b border-border/60 pb-2">
                  <div>
                    <h2 id="reported-samples-heading" className="text-sm font-semibold">Reported samples</h2>
                    <p className="text-xs text-muted-foreground">Samples with saved clinical reports.</p>
                  </div>
                  <Badge variant="secondary">{shortCount(reportedTotal)}</Badge>
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
