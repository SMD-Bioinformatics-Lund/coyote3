import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { Activity, AlertTriangle, CheckCircle2, ChevronDown, Download, FileText, Save } from "lucide-react"

import { AppLoader } from "@/components/layout/AppLoader"
import { ReportFindings } from "@/components/reports/ReportFindings"
import { ReportHtmlFrame } from "@/components/reports/ReportHtmlFrame"
import {
  REPORT_SNAPSHOT_SECTIONS,
  isCompactReportBiomarker,
  reportSnapshotAnalysisType,
  type ReportSnapshotRow,
  type ReportType,
} from "@/components/reports/report-snapshot"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { api } from "@/lib/api"
import { downloadBlob } from "@/lib/browser-download"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { apiPath } from "@/lib/runtime-paths"
import { AnalysisTableCard } from "./AnalysisTableCard"
import "@/styles/report-workspace.css"

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
    mutationFn: () => api.post(`/samples/${sampleId}/reports/${reportType}`, {
      preview_fingerprint: data?.meta?.preview_fingerprint,
    }),
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
  const ruleSource = data?.report?.context?.clinical_rule_evaluation?.source

  return (
    <AnalysisTableCard className="report-workspace">
      <header className="report-toolbar">
        <div className="flex min-w-0 items-center gap-3">
          <span className="report-title-icon"><FileText className="size-5" aria-hidden="true" /></span>
          <div className="min-w-0 space-y-1">
            <h2 className="type-card-title text-foreground">Report preview</h2>
            <p className="type-body-sm text-muted-foreground">Review your document before saving</p>
          </div>
        </div>
        <div className="report-actions">
            <span className="report-ready type-meta">
              {isLoading ? <Activity className="size-3 animate-spin" /> : hasRenderedHtml
                ? <CheckCircle2 className="size-3 text-pass" /> : <AlertTriangle className="size-3 text-warn" />}
              {isLoading ? "Preparing preview" : hasRenderedHtml ? "Ready to review" : "Preview unavailable"}
            </span>
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
              variant="ghost"
              onClick={() => downloadPreviewPdf.mutate()}
              disabled={!hasRenderedHtml || downloadPreviewPdf.isPending}
              title={hasRenderedHtml ? "Download preview PDF" : templateStatusMessage}
            >
              {downloadPreviewPdf.isPending ? <Activity className="size-4 animate-spin" /> : <Download className="size-4" />}
              Download PDF
            </Button>
            <Button
              variant="ghost"
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
          <section aria-label="Rendered report preview" className="report-document min-w-0">
              <div className="report-document-caption">
                <div className="min-w-0">
                  <h3 className="type-card-title text-foreground">{reportType.toUpperCase()} report</h3>
                  <p className="mt-1 break-words type-body-sm text-muted-foreground">{sampleName}</p>
                </div>
                <span className="report-preview-state type-meta"><span className="size-1.5 rounded-full bg-warn" aria-hidden="true" />Unsaved preview</span>
              </div>
              {!hasRenderedHtml && (
                <div className="mb-4 flex items-start gap-2 rounded-lg border border-warn/35 bg-warn/10 px-3 py-2 text-warn">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                  <p className="type-body-sm">{templateStatusMessage}</p>
                </div>
              )}
              <div className="report-paper-scroll" role="region" aria-label="Report document" tabIndex={0}>
                <ReportHtmlFrame
                  title="Report preview"
                  html={hasRenderedHtml ? data?.report?.html : "<p>No report preview available.</p>"}
                  className="report-paper"
                />
              </div>
          </section>

            <aside className="report-inspector" aria-label="Report review">
              <div className="report-inspector-heading">
                <div className="min-w-0">
                  <h3 className="type-card-title text-foreground">Review summary</h3>
                  <p className="mt-1 type-body-sm text-muted-foreground">
                    {includeSnapshot
                      ? `${snapshotCount} included ${snapshotCount === 1 ? "finding" : "findings"}`
                      : "Finding snapshot off"}
                  </p>
                </div>
                <label className="report-snapshot-toggle type-body-sm">
                  <span>Include findings</span>
                  <input type="checkbox" role="switch" aria-label="Include finding snapshot"
                    checked={includeSnapshot} onChange={(event) => setIncludeSnapshot(event.target.checked)} />
                </label>
              </div>
              <div className="report-inspector-body">
              <div className="report-findings-list">
                {includeSnapshot && visibleSnapshotSections.length > 0 ? visibleSnapshotSections.map((section) => isCompactReportBiomarker(section.type) ? (
                  <section key={section.type} aria-label={`${section.label} included findings`} className="report-finding-section report-biomarker-section">
                    <h4 className="font-semibold type-body-sm">{section.label}</h4>
                    <div className="pt-3">
                      <ReportFindings analysisType={section.type} columns={section.columns} rows={section.rows} />
                    </div>
                  </section>
                ) : (
                  <details key={section.type} open className="report-finding-section report-record-section group/report-section">
                    <summary className="interaction-transition flex cursor-pointer list-none items-center gap-2 rounded-md py-1 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                      <span className="font-semibold type-body-sm text-foreground">{section.label}</span>
                      <span className="ml-auto type-meta text-muted-foreground">{section.rows.length}</span>
                      <ChevronDown className="size-3.5 text-muted-foreground transition-transform group-open/report-section:rotate-180" aria-hidden="true" />
                    </summary>
                    <div className="pt-3">
                      <ReportFindings
                        analysisType={section.type}
                        columns={section.columns}
                        rows={section.rows}
                      />
                    </div>
                  </details>
                )) : (
                  <div className="py-4 type-body-sm text-muted-foreground">
                    {includeSnapshot ? "No reportable findings are included in this snapshot." : "The finding snapshot is turned off for this preview."}
                  </div>
                )}
              </div>
              <p className="report-save-note type-meta text-muted-foreground">This preview is temporary. Save report to preserve the document and its findings.</p>
              {ruleSource && <details className="report-rule-details type-meta text-muted-foreground">
                <summary className="w-fit cursor-pointer rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">Report rule details</summary>
                <p className="mt-2 break-words">
                  {ruleSource.rule_set_id} · v{ruleSource.content_version} · {ruleSource.language}
                  {ruleSource.resolved_subpanel_id === "base" && ruleSource.requested_subpanel_id !== "base" ? " · Assay Base scope" : " · Exact scope"}
                </p>
              </details>}
              </div>
            </aside>
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
