import { useEffect, useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"
import { Link, useParams } from "react-router-dom"
import { ArrowLeft, Download } from "lucide-react"

import { DataTable } from "@/components/data-table/DataTable"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { ReportHtmlFrame } from "@/components/reports/ReportHtmlFrame"
import { TableBadge } from "@/components/ui/table-badge"
import { api } from "@/lib/api"
import { humanRelativeDate } from "@/lib/detail-formatters"
import { apiPath } from "@/lib/runtime-paths"
import { TierBadge } from "@/lib/variant-ui"

type ReportFinding = Record<string, any>

type SavedReportContext = {
  sample_id: string
  report_id: string
  report_name?: string | null
  asp_id?: string | null
  subpanel_id?: string | null
  environment?: string | null
  author?: string | null
  time_created?: string | null
  finding_count: number
  analysis_counts: Record<string, number>
  findings: ReportFinding[]
}

function findingIdentity(finding: ReportFinding) {
  return finding.variant || finding.hgvsp || finding.hgvsc || finding.genomic || finding.simple_id || finding.cnv || finding.fusion || finding.translocation || "-"
}

function findingGenes(finding: ReportFinding) {
  const additionalGenes = Array.isArray(finding.genes)
    ? finding.genes
    : finding.genes
      ? [finding.genes]
      : []
  const genes = [finding.gene, ...additionalGenes, finding.gene1, finding.gene2].filter(Boolean)
  return Array.from(new Set(genes.map(String))).join(" / ") || "-"
}

export function SavedReportPage() {
  const { id = "", reportId = "" } = useParams()
  const [html, setHtml] = useState("")
  const [htmlError, setHtmlError] = useState("")
  const [htmlLoading, setHtmlLoading] = useState(true)

  const contextQuery = useQuery({
    queryKey: ["saved-report-context", id, reportId],
    queryFn: () => api.get<SavedReportContext>(`/samples/${id}/reports/${reportId}/context`).then((response) => response.data),
    enabled: Boolean(id && reportId),
  })

  useEffect(() => {
    let cancelled = false
    setHtmlLoading(true)
    setHtmlError("")
    fetch(apiPath(`/samples/${id}/reports/${reportId}/html`))
      .then(async (response) => {
        const text = await response.text()
        if (!response.ok) throw new Error(text || `Report request failed (${response.status})`)
        return text
      })
      .then((text) => {
        if (!cancelled) setHtml(text)
      })
      .catch((error) => {
        if (!cancelled) setHtmlError(error instanceof Error ? error.message : "Unable to load report")
      })
      .finally(() => {
        if (!cancelled) setHtmlLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [id, reportId])

  const columns = useMemo<ColumnDef<ReportFinding, any>[]>(() => [
    {
      id: "analysis_type",
      header: "Analysis",
      accessorFn: (row) => row.analysis_type || "OTHER",
      cell: ({ row }) => <TableBadge className="border-info/35 bg-info/10 text-info">{String(row.original.analysis_type || "OTHER").toUpperCase()}</TableBadge>,
    },
    { id: "genes", header: "Gene(s)", accessorFn: findingGenes },
    { id: "finding", header: "Reported finding", accessorFn: findingIdentity },
    {
      id: "tier",
      header: "Tier",
      accessorFn: (row) => row.tier ?? row.class ?? "-",
      cell: ({ row }) => <TierBadge tier={row.getValue("tier")} />,
    },
    {
      id: "text",
      header: "Report text",
      accessorFn: (row) => row.text || row.annotation || "",
      cell: ({ row }) => <span className="block max-w-[36rem] whitespace-normal">{row.original.text || row.original.annotation || "-"}</span>,
    },
  ], [])

  const loading = htmlLoading || contextQuery.isLoading
  const error = htmlError || (contextQuery.error instanceof Error ? contextQuery.error.message : contextQuery.error ? "Unable to load report findings" : "")
  const context = contextQuery.data

  return (
    <PageShell
      eyebrow="Report"
      title={context?.report_name || `${id} report ${reportId}`}
      description="Finalized report and the immutable clinical finding snapshot recorded when it was created."
      actions={
        <>
          <a
            href={apiPath(`/samples/${id}/reports/${reportId}/download`)}
            className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted"
          >
            <Download className="h-4 w-4" />
            Download
          </a>
          <Link to="/reports" className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted">
            <ArrowLeft className="h-4 w-4" />
            All reports
          </Link>
        </>
      }
    >
      {loading ? (
        <AppLoader label="Loading saved report" />
      ) : error ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">{error}</div>
      ) : (
        <div className="space-y-3">
          {context && (
            <section className="surface-panel p-3">
              <div className="mb-3 flex flex-wrap items-start justify-between gap-3 border-b border-border pb-3">
                <div>
                  <h2 className="text-base font-semibold">Reported findings</h2>
                  <p className="text-sm text-muted-foreground">
                    {context.asp_id || "-"} / {context.subpanel_id || "-"} / {context.environment || "-"}
                  </p>
                </div>
                <p className="text-sm text-muted-foreground">
                  Created by {context.author || "-"} {context.time_created ? humanRelativeDate(context.time_created) : ""}
                </p>
              </div>
              <DataTable
                columns={columns}
                data={context.findings || []}
                filename={`${id}_${reportId}_reported_findings.csv`}
                rowLabel="reported findings"
                stateKey={`saved-report-${reportId}`}
              />
            </section>
          )}
          <section className="surface-panel p-3">
            <h2 className="mb-3 border-b border-border pb-3 text-base font-semibold">Rendered report</h2>
            <ReportHtmlFrame title={`${id} saved report`} html={html} className="rounded-xl shadow-sm" />
          </section>
        </div>
      )}
    </PageShell>
  )
}
