import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"
import { Link } from "react-router-dom"
import { Activity, AlertTriangle, CheckCircle2, ChevronDown, Download, Eye, FileText, Layers3, Save } from "lucide-react"

import { DataTable } from "@/components/data-table/DataTable"
import { AppLoader } from "@/components/layout/AppLoader"
import { ReportHtmlFrame } from "@/components/reports/ReportHtmlFrame"
import {
  REPORT_SNAPSHOT_SECTIONS,
  reportSnapshotAnalysisType,
  type ReportSnapshotRow,
  type ReportType,
} from "@/components/reports/report-snapshot"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { api } from "@/lib/api"
import { downloadBlob } from "@/lib/browser-download"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { apiPath } from "@/lib/runtime-paths"

export function ReportsTab({ sampleId, reportType: fixedReportType }: { sampleId: string; reportType?: ReportType }) {
  const queryClient = useQueryClient()
  const [selectedReportType, setSelectedReportType] = useState<ReportType>("dna")
  const [includeSnapshot, setIncludeSnapshot] = useState(true)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const reportType = fixedReportType ?? selectedReportType

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["report-preview", sampleId, reportType, includeSnapshot],
    queryFn: () =>
      api
        .get(`/samples/${sampleId}/reports/${reportType}/preview?include_snapshot=${includeSnapshot}&save=false`)
        .then((response) => response.data),
    retry: false,
    refetchOnMount: "always",
  })

  const saveReport = useMutation({
    mutationFn: () => api.post(`/samples/${sampleId}/reports/${reportType}`),
    onSuccess: () => {
      const sampleName = data?.sample?.name || sampleId
      setConfirmOpen(false)
      refetch()
      queryClient.invalidateQueries({ queryKey: ["samples"] })
      queryClient.invalidateQueries({ queryKey: ["sample-navigation-counts"] })
      notifySuccess("Report saved", `${reportType.toUpperCase()} report was saved for ${sampleName}.`, "Reports", {
        type: "report",
        id: sampleId,
        name: `${sampleName} ${reportType.toUpperCase()}`,
        sampleName,
      })
    },
    onError: (mutationError) => {
      const sampleName = data?.sample?.name || sampleId
      notifyActionError("Unable to save report", mutationError, "Reports", {
        type: "report",
        id: sampleId,
        name: `${sampleName} ${reportType.toUpperCase()}`,
        sampleName,
      })
    },
  })

  const downloadPreviewPdf = useMutation({
    mutationFn: async () => {
      const response = await fetch(
        apiPath(`/samples/${sampleId}/reports/${reportType}/preview/pdf?include_snapshot=${includeSnapshot}`),
        { credentials: "same-origin" },
      )
      if (!response.ok) {
        const message = await response.text()
        throw new Error(message || `PDF request failed with ${response.status}`)
      }
      downloadBlob(await response.blob(), `${data?.sample?.name || sampleId}_${reportType}_preview.pdf`)
    },
    onSuccess: () => {
      const sampleName = data?.sample?.name || sampleId
      notifySuccess(
        "PDF generated",
        `The temporary ${reportType.toUpperCase()} report preview PDF for ${sampleName} was downloaded.`,
        "Reports",
        { type: "report", id: sampleId, name: `${sampleName} ${reportType.toUpperCase()} preview`, sampleName },
      )
    },
    onError: (mutationError) => {
      const sampleName = data?.sample?.name || sampleId
      notifyActionError("Unable to generate PDF", mutationError, "Reports", {
        type: "report",
        id: sampleId,
        name: `${sampleName} ${reportType.toUpperCase()} preview`,
        sampleName,
      })
    },
  })

  const templateStatus = data?.meta?.template_status
  const snapshotRows: ReportSnapshotRow[] = data?.report?.snapshot_rows || []
  const snapshotCount = data?.meta?.snapshot_count ?? snapshotRows.length
  const visibleSnapshotSections = REPORT_SNAPSHOT_SECTIONS
    .map((section) => ({
      ...section,
      rows: snapshotRows.filter((row) => reportSnapshotAnalysisType(row, reportType) === section.type),
    }))
    .filter((section) => section.rows.length > 0)
  const hasRenderedHtml = Boolean(templateStatus?.has_html && data?.report?.html)
  const templateStatusMessage = templateStatus?.message || "Report preview has not been rendered yet."
  const sampleName = data?.sample?.name || sampleId

  return (
    <div className="space-y-4">
      <Card size="sm">
        <CardHeader className="border-b">
          <CardTitle className="flex items-center gap-2">
            <FileText className="size-4 text-primary" aria-hidden="true" />
            Clinical Report Preview
          </CardTitle>
          <CardDescription>Review the rendered document and the findings preserved with this report.</CardDescription>
          <CardAction className="flex flex-wrap items-center justify-end gap-2">
            {!fixedReportType && (
              <SegmentedControl
                ariaLabel="Report type"
                value={reportType}
                onValueChange={setSelectedReportType}
                items={[{ value: "dna", label: "DNA" }, { value: "rna", label: "RNA" }]}
              />
            )}
            <button
              type="button"
              role="switch"
              aria-checked={includeSnapshot}
              aria-label="Include finding snapshot"
              onClick={() => setIncludeSnapshot((current) => !current)}
              className="paper-raised-control interaction-transition inline-flex h-9 items-center gap-2 rounded-lg px-3 type-body-sm font-semibold"
            >
              <Layers3 className="size-4 text-primary" aria-hidden="true" />
              Include findings
              <Badge variant={includeSnapshot ? "default" : "secondary"}>{includeSnapshot ? "On" : "Off"}</Badge>
            </button>
            <Button
              type="button"
              variant="outline"
              onClick={() => downloadPreviewPdf.mutate()}
              disabled={!hasRenderedHtml || downloadPreviewPdf.isPending}
              title={hasRenderedHtml ? "Download preview PDF" : templateStatusMessage}
            >
              {downloadPreviewPdf.isPending ? <Activity className="size-4 animate-spin" /> : <Download className="size-4" />}
              PDF
            </Button>
            <Button
              variant="outline"
              render={<Link to={`/reports?sample_id=${encodeURIComponent(sampleId)}&report_type=${reportType}`} />}
            >
              <FileText className="size-4" aria-hidden="true" />
              Workspace
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">{sampleName}</Badge>
          <Badge variant="outline">{reportType.toUpperCase()}</Badge>
          <Badge variant={templateStatus?.status === "ready" ? "secondary" : "destructive"}>
            {templateStatus?.status === "ready" ? <CheckCircle2 className="size-3" /> : <AlertTriangle className="size-3" />}
            {templateStatus?.status === "ready" ? "Template ready" : "Template unavailable"}
          </Badge>
          <span className="type-meta ml-auto text-muted-foreground">
            {snapshotCount} included finding{snapshotCount === 1 ? "" : "s"}
          </span>
        </CardContent>
      </Card>

      {isLoading ? (
        <Card><CardContent><AppLoader label="Loading report preview" /></CardContent></Card>
      ) : error ? (
        <Card className="border-destructive/40">
          <CardContent className="flex items-start gap-3 text-destructive">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <div>
              <p className="font-semibold">Error loading report preview</p>
              <p className="mt-1 type-body-sm">{error instanceof Error ? error.message : "Unknown error"}</p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <>
          <Card>
            <CardHeader className="border-b">
              <CardTitle className="flex items-center gap-2">
                <Eye className="size-4 text-primary" aria-hidden="true" />
                Rendered report preview
              </CardTitle>
              <CardDescription>The preview remains temporary until it is saved.</CardDescription>
              <CardAction>
                <Button
                  type="button"
                  size="lg"
                  onClick={() => setConfirmOpen(true)}
                  disabled={!hasRenderedHtml || saveReport.isPending}
                  title={hasRenderedHtml ? "Save this rendered report" : templateStatusMessage}
                >
                  {saveReport.isPending ? <Activity className="size-4 animate-spin" /> : <Save className="size-4" />}
                  Save report
                </Button>
              </CardAction>
            </CardHeader>
            <CardContent>
              {!hasRenderedHtml && (
                <div className="mb-4 flex items-start gap-2 rounded-lg border border-warn/35 bg-warn/10 px-3 py-2 text-warn">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                  <p className="type-body-sm">{templateStatusMessage}</p>
                </div>
              )}
              <div className="rounded-lg bg-muted/35 p-2 sm:p-3">
                <ReportHtmlFrame
                  title="Report preview"
                  html={hasRenderedHtml ? data?.report?.html : "<p>No report preview available.</p>"}
                  className="shadow-surface-sm"
                />
              </div>
            </CardContent>
          </Card>

          {includeSnapshot && (
            <Card>
              <CardHeader className="border-b">
                <CardTitle className="flex items-center gap-2">
                  <Layers3 className="size-4 text-primary" aria-hidden="true" />
                  Included findings
                </CardTitle>
                <CardDescription>These rows are preserved with the saved report.</CardDescription>
                <CardAction><Badge variant="secondary">{snapshotCount}</Badge></CardAction>
              </CardHeader>
              <CardContent className="divide-y divide-border px-0">
                {visibleSnapshotSections.length > 0 ? visibleSnapshotSections.map((section) => (
                  <details key={section.type} open className="group/report-section px-(--card-spacing) py-3 first:pt-0 last:pb-0">
                    <summary className="interaction-transition flex cursor-pointer list-none items-center gap-2 rounded-md py-1 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                      <ChevronDown className="size-4 text-muted-foreground transition-transform group-open/report-section:rotate-180" aria-hidden="true" />
                      <span className="type-section-title text-foreground">{section.label}</span>
                      <Badge variant="outline" className="ml-auto">{section.rows.length}</Badge>
                    </summary>
                    <div className="pt-3">
                      <DataTable
                        columns={section.columns as ColumnDef<ReportSnapshotRow, any>[]}
                        data={section.rows}
                        filename={`${sampleId}_${reportType}_${section.type.toLowerCase()}_snapshot.csv`}
                      />
                    </div>
                  </details>
                )) : (
                  <div className="px-(--card-spacing) py-10 text-center type-body-sm text-muted-foreground">
                    No reportable findings are included in this snapshot.
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </>
      )}

      <ConfirmationDialog
        open={confirmOpen}
        title="Confirm report save"
        description={
          <div className="space-y-3">
            <p>Save this rendered {reportType.toUpperCase()} report and preserve its included finding snapshot.</p>
            <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 rounded-lg border border-border bg-muted/40 p-3">
              <dt>Sample</dt><dd className="font-semibold text-foreground">{sampleName}</dd>
              <dt>Included findings</dt><dd className="type-numeric font-semibold text-foreground">{snapshotCount}</dd>
            </dl>
          </div>
        }
        confirmLabel="Confirm save"
        isPending={saveReport.isPending}
        onConfirm={() => saveReport.mutate()}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  )
}
