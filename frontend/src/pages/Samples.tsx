import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link, useSearchParams } from "react-router-dom"
import type { ColumnDef } from "@tanstack/react-table"
import { api } from "@/lib/api"
import { Badge } from "@/components/ui/badge"
import { TableBadge } from "@/components/ui/table-badge"
import { Button } from "@/components/ui/button"
import { FileText, ArrowRight, Dna, Search as SearchIcon } from "lucide-react"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { Input } from "@/components/ui/input"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { fullDateTime, humanRelativeDate, shortCount } from "@/lib/detail-formatters"
import { sampleDetailPath } from "@/lib/sample-routing"
import { sampleReported, sampleSubpanel } from "@/lib/sample-shape"
import { DataTable } from "@/components/data-table/DataTable"
import { valueBadgeClass } from "@/lib/badge-colors"
import { useUrlTableState } from "@/hooks/useUrlTableState"
import { DEFAULT_ENVIRONMENT } from "@/lib/application-constants"

type SampleTab = "live" | "reported"

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
    counts.snvs !== undefined ? { label: "SNV", value: shortCount(counts.snvs), className: "border-primary/30 bg-primary/10 text-primary" } : null,
    counts.cnvs !== undefined ? { label: "CNV", value: shortCount(counts.cnvs), className: "border-tier3/30 bg-tier3/10 text-tier3" } : null,
    counts.fusions !== undefined ? { label: "Fusion", value: shortCount(counts.fusions), className: "border-rna/30 bg-rna/10 text-rna" } : null,
    counts.translocations !== undefined ? { label: "SV", value: shortCount(counts.translocations), className: "border-tier2/30 bg-tier2/10 text-tier2" } : null,
  ].filter(Boolean)
  const booleanBadges = Object.entries(counts)
    .filter(([, value]) => value === true)
    .map(([key]) => ({
      label: BOOLEAN_ANALYSIS_LABELS[key] || key.replaceAll("_", " ").toUpperCase(),
      className: "matte-badge-pass",
    }))

  return [...numericBadges, ...booleanBadges]
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

  // Extract filters from URL
  const category = searchParams.get("panel_type") || searchParams.get("category")
  const assay = searchParams.get("assay")
  const panelTech = searchParams.get("panel_tech")
  const group = searchParams.get("assay_group") || searchParams.get("group")
  const profileScope = searchParams.get("profile_scope") === "all" ? "all" : DEFAULT_ENVIRONMENT
  const activeTab: SampleTab = searchParams.get("sample_tab") === "reported" ? "reported" : "live"
  const searchStr = searchParams.get("search_str") || ""
  const {
    sorting,
    setSorting,
    updateTableSearchParams,
  } = useUrlTableState({ prefix: "samples" })

  const [searchInput, setSearchInput] = useState(searchStr)

  const { data, isLoading, error } = useQuery({
    queryKey: ['samples', category, panelTech, assay, group, profileScope, searchStr],
    queryFn: () => {
      const params = new URLSearchParams()
      if (category) params.set("panel_type", category)
      if (panelTech) params.set("panel_tech", panelTech)
      if (assay) params.set("assay", assay)
      if (group) params.set("assay_group", group)
      params.set("profile_scope", profileScope)
      if (searchStr) params.set("search_str", searchStr)

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
  const columns = useMemo<ColumnDef<any, any>[]>(() => [
    {
      id: "sample",
      header: "Sample",
      accessorFn: (sample) => sample.name || sample.case_id || "",
      cell: ({ row }) => {
        const sample = row.original
        return (
          <Link to={sampleDetailPath(sample)} className="link-text flex items-center gap-2 font-bold">
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
      cell: ({ row }) => <span className="font-semibold">{row.original.case_id || row.original.case?.id || "-"}</span>,
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
      cell: ({ row }) => <span className="font-semibold">{row.original.control_id || row.original.control?.id || "-"}</span>,
    },
    {
      id: "control_clarity",
      header: "Control Clarity",
      accessorFn: (sample) => sample.control?.clarity_id || "",
      cell: ({ row }) => <span className="text-muted-foreground">{row.original.control?.clarity_id || "-"}</span>,
    },
    {
      id: "environment",
      header: "Environment",
      accessorFn: (sample) => sample.environment || "",
      cell: ({ row }) => (
        <TableBadge className={`${valueBadgeClass(row.original.environment || "")} uppercase`}>
          {row.original.environment || "-"}
        </TableBadge>
      ),
    },
    {
      id: "asp_id",
      header: "ASP",
      accessorFn: (sample) => sample.asp_id || "",
      cell: ({ row }) => <span className="font-semibold">{row.original.asp_id || "-"}</span>,
    },
    {
      id: "subpanel",
      header: "Subpanel",
      accessorFn: (sample) => sampleSubpanel(sample) || "",
      cell: ({ row }) => <span className="font-medium text-muted-foreground">{sampleSubpanel(row.original) || "-"}</span>,
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
              : "border-warn/30 bg-warn/15 text-warn hover:bg-warn/20"
          }
        >
          {row.original.ingest_status || "-"}
        </TableBadge>
      ),
    },
    {
      id: "report",
      header: "Report",
      accessorFn: (sample) => sampleReported(sample) ? 1 : 0,
      cell: ({ row }) => (
        <TableBadge
          className={sampleReported(row.original) ? "border-primary/30 bg-primary/10 text-primary" : "border-warn/30 bg-warn/10 text-warn"}
        >
          {sampleReported(row.original) ? "reported" : "unreported"}
        </TableBadge>
      ),
      meta: {
        exportValue: (sample: any) => sampleReported(sample) ? "reported" : "unreported",
      },
    },
    {
      id: "counts",
      header: "Counts",
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
        {(category || assay || group || searchStr || showAllProfiles) && (
          <div className="glass-card flex items-center gap-2 text-sm text-muted-foreground px-5 py-3">
            <span className="font-bold uppercase tracking-wider text-xs mr-2">Active Filters</span>
            <Badge variant="secondary" className="uppercase bg-primary/10 text-primary hover:bg-primary/20 rounded-md">{showAllProfiles ? "all profiles" : DEFAULT_ENVIRONMENT}</Badge>
            {searchStr && <Badge variant="secondary" className="bg-primary/10 text-primary hover:bg-primary/20 rounded-md">Search: {searchStr}</Badge>}
            {category && <Badge variant="secondary" className="uppercase bg-primary/20 text-primary hover:bg-primary/30 rounded-md">{category}</Badge>}
            {panelTech && <Badge variant="secondary" className="uppercase bg-primary/20 text-primary hover:bg-primary/30 rounded-md">{panelTech}</Badge>}
            {assay && <Badge variant="secondary" className="uppercase bg-primary/20 text-primary hover:bg-primary/30 rounded-md">{assay}</Badge>}
            {group && <Badge variant="secondary" className="uppercase bg-secondary text-secondary-foreground hover:bg-secondary/80 rounded-md shadow-sm">{group}</Badge>}
            <Link to="/samples" className="text-xs font-bold text-destructive hover:underline ml-auto bg-destructive/10 px-3 py-1 rounded-md" onClick={() => setSearchInput("")}>Clear All</Link>
          </div>
        )}

        <div className="glass-card border-border/50 p-4">
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
          <DataTable
            columns={columns}
            data={samples}
            filename={`${activeTab}_samples.csv`}
            rowLabel="samples"
            totalCount={samples.length}
            hideSearch
            stateKey={`samples.${activeTab}`}
            sortingState={sorting}
            onSortingChange={(value) => {
              setSorting(value)
              updateTableSearchParams({ sorting: value })
            }}
            getRowClassName={() => "group"}
            renderToolbar={() => samples.length === 0 ? (
              <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
                <Dna className="h-4 w-4 text-muted-foreground/50" />
                No samples found.
              </div>
            ) : null}
          />
        </div>
      </PageShell>
    </div>
  )
}
