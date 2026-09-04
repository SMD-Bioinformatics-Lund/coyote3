import { useEffect, useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"
import { Download, FileText } from "lucide-react"
import { Link } from "react-router-dom"

import { DataTable } from "@/components/data-table/DataTable"
import { useTablePreferences } from "@/components/data-table/table-preferences"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { TableBadge } from "@/components/ui/table-badge"
import { TimeDisplay } from "@/components/ui/time-display"
import { DetailNavigationButton } from "@/components/data-table/DetailNavigationButton"
import { api } from "@/lib/api"
import { apiPath } from "@/lib/runtime-paths"

type ReportLibraryItem = {
  oid: string
  report_id: string
  report_name?: string | null
  sample_id: string
  asp_id?: string | null
  subpanel_id?: string | null
  environment?: string | null
  author?: string | null
  time_created?: string | null
  finding_count: number
  analysis_counts: Record<string, number>
  has_pdf: boolean
}

type ReportLibraryPayload = {
  reports: ReportLibraryItem[]
  total: number
  page: number
  per_page: number
  has_next: boolean
}

function findingSummary(row: ReportLibraryItem) {
  return Object.entries(row.analysis_counts || {})
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([analysisType, count]) => `${analysisType} ${count}`)
    .join(" | ")
}

export function ReportsPage() {
  const { pageSize: preferredPageSize } = useTablePreferences()
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(preferredPageSize)
  const [search, setSearch] = useState("")

  useEffect(() => {
    setPerPage(preferredPageSize)
    setPage(1)
  }, [preferredPageSize])

  const query = useQuery({
    queryKey: ["saved-report-library", page, perPage, search],
    queryFn: () => {
      const params = new URLSearchParams({ page: String(page), per_page: String(perPage) })
      if (search.trim()) params.set("search", search.trim())
      return api.get<ReportLibraryPayload>(`/reports?${params.toString()}`).then((response) => response.data)
    },
    placeholderData: (previous) => previous,
  })

  const columns = useMemo<ColumnDef<ReportLibraryItem, any>[]>(() => [
    {
      id: "report",
      header: "Report",
      accessorFn: (row) => `${row.report_id} ${row.report_name || ""}`,
      cell: ({ row }) => (
        <div className="flex min-w-0 items-center gap-2">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <FileText className="size-4" />
          </span>
          <div className="min-w-0">
            <Link
              to={`/samples/${encodeURIComponent(row.original.sample_id)}/reports/${encodeURIComponent(row.original.report_id)}`}
              className="type-body-sm text-link hover:underline"
            >
              {row.original.report_id}
            </Link>
            {row.original.report_name && row.original.report_name !== row.original.report_id ? (
              <p className="max-w-64 truncate type-label text-muted-foreground" title={row.original.report_name}>
                {row.original.report_name}
              </p>
            ) : null}
          </div>
        </div>
      ),
    },
    {
      id: "sample",
      header: "Sample",
      accessorKey: "sample_id",
      cell: ({ row }) => (
        <Link
          to={`/samples/${encodeURIComponent(row.original.sample_id)}?tab=reports`}
          className="inline-flex rounded-full border border-primary/25 bg-primary/10 px-2 py-1 type-meta text-primary hover:bg-primary/15"
        >
          {row.original.sample_id}
        </Link>
      ),
    },
    {
      id: "assay",
      header: "Assay",
      accessorFn: (row) => [row.asp_id, row.subpanel_id, row.environment].filter(Boolean).join(" / "),
      cell: ({ row }) => (
        <div className="space-y-0.5">
          <p className="type-table-cell text-foreground">
            {[row.original.asp_id, row.original.subpanel_id].filter(Boolean).join(" / ") || "-"}
          </p>
          {row.original.environment ? (
            <p className="type-label capitalize text-muted-foreground">{row.original.environment}</p>
          ) : null}
        </div>
      ),
    },
    {
      id: "findings",
      header: "Reported findings",
      accessorFn: findingSummary,
      enableSorting: false,
      cell: ({ row }) => (
        <div className="flex flex-wrap gap-1">
          {Object.entries(row.original.analysis_counts || {}).length ? (
            Object.entries(row.original.analysis_counts)
              .sort(([left], [right]) => left.localeCompare(right))
              .map(([analysisType, count]) => (
                <TableBadge key={analysisType} className="border-info/35 bg-info/10 text-info">
                  {analysisType} {count}
                </TableBadge>
              ))
          ) : (
            <span className="text-muted-foreground">No snapshot findings</span>
          )}
        </div>
      ),
    },
    { id: "author", header: "Created by", accessorFn: (row) => row.author || "-" },
    {
      id: "created",
      header: "Created",
      accessorFn: (row) => row.time_created || "",
      cell: ({ row }) => <TimeDisplay value={row.original.time_created} />,
    },
    {
      id: "actions",
      header: "Actions",
      enableSorting: false,
      cell: ({ row }) => (
        <div className="flex items-center gap-1.5">
          <DetailNavigationButton
            to={`/samples/${encodeURIComponent(row.original.sample_id)}/reports/${encodeURIComponent(row.original.report_id)}`}
            label={`Open report ${row.original.report_id}`}
            description="Open the saved report and its reported findings."
          />
          <a
            href={apiPath(`/samples/${encodeURIComponent(row.original.sample_id)}/reports/${encodeURIComponent(row.original.report_id)}/download`)}
            className="paper-raised-control inline-flex h-8 w-8 items-center justify-center rounded-lg"
            title="Download saved report"
            aria-label={`Download report ${row.original.report_id}`}
          >
            <Download className="h-4 w-4" />
          </a>
        </div>
      ),
    },
  ], [])

  return (
    <PageShell
      eyebrow="Reports"
      title="Saved Reports"
      description="Review finalized clinical reports and the immutable findings recorded with each report."
      actions={
        <Link to="/samples" className="paper-raised-control inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold">
          <FileText className="h-4 w-4" />
          Open samples
        </Link>
      }
    >
      {query.isLoading && <AppLoader label="Loading saved reports" />}
      {query.error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          {query.error instanceof Error ? query.error.message : "Unable to load saved reports"}
        </div>
      )}
      {query.data && (
        <section className="surface-panel p-3">
          <DataTable
            columns={columns}
            data={query.data.reports}
            filename="saved_reports.csv"
            rowLabel="reports"
            totalCount={query.data.total}
            page={query.data.page}
            perPage={query.data.per_page}
            hasPrevious={query.data.page > 1}
            hasNext={query.data.has_next}
            onPageChange={setPage}
            onPerPageChange={(value) => {
              setPerPage(value)
              setPage(1)
            }}
            searchValue={search}
            onSearchChange={(value) => {
              setSearch(value)
              setPage(1)
            }}
            searchPlaceholder="Search reports, samples, assays, or authors..."
            stateKey="saved-reports"
          />
        </section>
      )}
    </PageShell>
  )
}
