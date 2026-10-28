import { useState } from "react"
import { useReportPreview } from "@/hooks/useReportPreview"
import { ReportDocumentPreview } from "@/components/reports/ReportDocumentPreview"
import { ReportReviewSummary } from "@/components/reports/ReportReviewSummary"
import { Link } from "react-router-dom"
import { Activity, AlertTriangle, CheckCircle2, Download, FileText, Save, Sparkles } from "lucide-react"

import { AppLoader } from "@/components/layout/AppLoader"
import {
  type ReportSnapshotRow,
  type ReportType,
} from "@/components/reports/report-snapshot"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { AnalysisTableCard } from "./AnalysisTableCard"
import { TryNewReport } from "./TryNewReport"
import "@/styles/report-workspace.css"

export function ReportsTab({ sampleId, reportType: fixedReportType }: { sampleId: string; reportType?: ReportType }) {
  const [selectedReportType, setSelectedReportType] = useState<ReportType>("dna")
  const [includeSnapshot, setIncludeSnapshot] = useState(true)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [tryingNewReport, setTryingNewReport] = useState(false)
  const [previewFormat, setPreviewFormat] = useState<"html" | "pdf">("html")
  const reportType = fixedReportType ?? selectedReportType
  const { data, isLoading, error, hasRenderedHtml, pdfPreview, saveReport, downloadPreviewPdf } = useReportPreview({
    sampleId, reportType, includeSnapshot, pdfEnabled: previewFormat === "pdf" && !tryingNewReport,
    onSaved: () => setConfirmOpen(false),
  })

  const templateStatus = data?.meta?.template_status
  const snapshotRows: ReportSnapshotRow[] = (data?.report?.snapshot_rows || []).filter(
    (row): row is ReportSnapshotRow => row !== null && typeof row === "object" && !Array.isArray(row),
  )
  const snapshotCount = data?.meta?.snapshot_count ?? snapshotRows.length
  const templateStatusMessage = typeof templateStatus?.message === "string"
    ? templateStatus.message : "Report preview has not been rendered yet."
  const sampleName = data?.sample?.name || sampleId
  if (tryingNewReport) return <TryNewReport key={`${sampleId}:${reportType}`} sampleId={sampleId} reportType={reportType} onClose={() => setTryingNewReport(false)} />

  return (
    <AnalysisTableCard className="report-workspace">
      <header className="report-toolbar">
        <div className="flex min-w-0 items-center gap-3">
          <span className="report-title-icon"><FileText className="size-5" aria-hidden="true" /></span>
          <div className="min-w-0 space-y-1">
            <h2 className="type-card-title text-foreground">Report preview</h2>
            <p className="type-body-sm text-muted-foreground">Review your document before saving</p>
            <span className="report-ready type-meta" data-state={isLoading ? "loading" : hasRenderedHtml ? "ready" : "unavailable"}>
              {isLoading ? <Activity className="size-3 motion-safe:animate-spin" aria-hidden="true" /> : hasRenderedHtml
                ? <CheckCircle2 className="size-3" aria-hidden="true" /> : <AlertTriangle className="size-3" aria-hidden="true" />}
              {isLoading ? "Preparing preview" : hasRenderedHtml ? "Ready to review" : "Preview unavailable"}
            </span>
          </div>
        </div>
        <div className="report-actions">
            <Button variant="outline" className="report-trial-action" onClick={() => setTryingNewReport(true)}>
              <Sparkles className="size-4" aria-hidden="true" />Try new report
            </Button>
            {!fixedReportType && (
              <SegmentedControl
                ariaLabel="Report type"
                value={reportType}
                onValueChange={setSelectedReportType}
                items={[{ value: "dna", label: "DNA" }, { value: "rna", label: "RNA" }]}
              />
            )}
            <Button
              type="button"
              variant="outline"
              onClick={() => downloadPreviewPdf.mutate()}
              disabled={!hasRenderedHtml || downloadPreviewPdf.isPending}
              title={hasRenderedHtml ? "Download preview PDF" : templateStatusMessage}
            >
              {downloadPreviewPdf.isPending ? <Activity className="size-4 animate-spin" /> : <Download className="size-4" />}
              Download PDF
            </Button>
            <Button
              variant="outline"
              nativeButton={false}
              render={<Link to={`/reports?sample_id=${encodeURIComponent(sampleId)}&report_type=${reportType}`} />}
            >
              <FileText className="size-4" aria-hidden="true" />
              Workspace
            </Button>
            <Button
              type="button"
              className="report-save"
              onClick={() => setConfirmOpen(true)}
              disabled={!hasRenderedHtml || !data?.meta?.preview_fingerprint || saveReport.isPending}
              title={hasRenderedHtml ? "Save this rendered report" : templateStatusMessage}
            >
              {saveReport.isPending ? <Activity className="size-4 animate-spin" /> : <Save className="size-4" />}
              Save report
            </Button>
        </div>
      </header>
      {typeof data?.report?.context?.reporting_warning === "string" && (
        <p role="alert" className="rounded-md border border-warning p-3 type-body text-foreground">
          <AlertTriangle className="mr-2 inline size-4 text-warning" />
          {data.report.context.reporting_warning}
        </p>
      )}

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
        <div className="report-layout">
          <ReportDocumentPreview reportType={reportType} sampleName={sampleName}
            hasRenderedHtml={hasRenderedHtml} html={data?.report?.html}
            templateStatusMessage={templateStatusMessage} format={previewFormat} onFormatChange={setPreviewFormat}
            pdfData={pdfPreview.data} pdfError={pdfPreview.error} onRetryPdf={() => void pdfPreview.refetch()} />

          <ReportReviewSummary reportType={reportType} snapshotRows={snapshotRows} snapshotCount={snapshotCount}
            includeSnapshot={includeSnapshot} onIncludeSnapshotChange={setIncludeSnapshot}
            evaluation={data?.report?.context?.clinical_rule_evaluation} />
        </div>
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
    </AnalysisTableCard>
  )
}
