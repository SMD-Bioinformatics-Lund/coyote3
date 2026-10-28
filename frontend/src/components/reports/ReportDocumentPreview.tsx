import { AlertTriangle, Clock3, FileCode2, FileText } from "lucide-react"
import { AppLoader } from "@/components/layout/AppLoader"
import { Button } from "@/components/ui/button"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { ReportHtmlFrame } from "./ReportHtmlFrame"
import { ReportPdfFrame } from "./ReportPdfFrame"
import type { ReportType } from "./report-snapshot"

export function ReportDocumentPreview({ reportType, sampleName, hasRenderedHtml, html,
  templateStatusMessage, format, onFormatChange, pdfData, pdfError, onRetryPdf }: {
  reportType: ReportType
  sampleName: string
  hasRenderedHtml: boolean
  html?: string | null
  templateStatusMessage: string
  format: "html" | "pdf"
  onFormatChange: (format: "html" | "pdf") => void
  pdfData?: Blob
  pdfError: Error | null
  onRetryPdf: () => void
}) {
  return (
    <section aria-label="Rendered report preview" className="report-document min-w-0">
      <div className="report-document-caption">
        <div className="min-w-0">
          <h3 className="type-card-title text-foreground">{reportType.toUpperCase()} report</h3>
          <p className="mt-1 break-words type-body-sm text-muted-foreground">{sampleName}</p>
        </div>
        <span className="report-preview-state type-meta"><Clock3 className="size-3.5" aria-hidden="true" />Unsaved preview</span>
      </div>
      {hasRenderedHtml && <div className="report-format-toolbar">
        <span className="type-meta text-muted-foreground">Document view</span>
        <SegmentedControl className="report-format-tabs type-body" ariaLabel="Report preview format" value={format} onValueChange={onFormatChange}
          items={[
            { value: "html", label: <><FileCode2 className="size-4" aria-hidden="true" />HTML preview</> },
            { value: "pdf", label: <><FileText className="size-4" aria-hidden="true" />PDF preview</> },
          ]} />
      </div>}
      {!hasRenderedHtml && (
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-warn/35 bg-warn/10 px-3 py-2 text-warn">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <p className="type-body-sm">{templateStatusMessage}</p>
        </div>
      )}
      <div className="report-paper-scroll" role="region" aria-label="Report document" tabIndex={0}>
        {format === "html" ? <ReportHtmlFrame
          title="Report preview"
          html={hasRenderedHtml ? html ?? "" : "<p>No report preview available.</p>"}
          className="report-paper"
        /> : pdfError ? <div role="alert" className="space-y-3 p-4 type-body-sm text-destructive">
          <p>{pdfError instanceof Error ? pdfError.message : "Unable to prepare PDF preview."}</p>
          <Button variant="outline" onClick={() => onRetryPdf()}>Retry PDF preview</Button>
        </div> : !pdfData ? <AppLoader label="Preparing PDF preview" /> :
          <ReportPdfFrame title="Report PDF preview" blob={pdfData} filename={`${sampleName}_${reportType}_preview.pdf`} />}
      </div>
    </section>
  )
}
