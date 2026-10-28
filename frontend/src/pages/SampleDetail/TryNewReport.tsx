import { useEffect, useState } from "react"
import { ArrowLeft, Download, FileCode2, FileText, RefreshCw, Sparkles } from "lucide-react"
import { AppLoader } from "@/components/layout/AppLoader"
import { ReportHtmlFrame } from "@/components/reports/ReportHtmlFrame"
import { ReportPdfFrame } from "@/components/reports/ReportPdfFrame"
import type { ReportType } from "@/components/reports/report-snapshot"
import { Button } from "@/components/ui/button"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { api } from "@/lib/api"
import type { ReportTrialPayload } from "@/lib/generated"
import { downloadBlob, downloadText } from "@/lib/browser-download"
import { validateReportPdf } from "@/lib/report-pdf"
import { AnalysisTableCard } from "./AnalysisTableCard"

type Trial = ReportTrialPayload
type PreparedTrial = Trial & { pdf: Blob }

export function TryNewReport({ sampleId, reportType, onClose }: {
  sampleId: string
  reportType: ReportType
  onClose: () => void
}) {
  const [data, setData] = useState<PreparedTrial | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [format, setFormat] = useState<"html" | "pdf">("html")
  const [generation, setGeneration] = useState(0)

  useEffect(() => {
    const request = new AbortController()
    setData(null)
    setError(null)
    api.get<Trial>(`/samples/${encodeURIComponent(sampleId)}/reports/${reportType}/try-new`, {
      signal: request.signal, cache: "no-store",
    }).then(async response => {
      if (request.signal.aborted) return
      const bytes = Uint8Array.from(atob(response.data.pdf_base64), character => character.charCodeAt(0))
      const pdf = await validateReportPdf(new Blob([bytes], { type: "application/pdf" }))
      if (!request.signal.aborted) setData({ ...response.data, pdf })
    }).catch(failure => {
      if (!request.signal.aborted) setError(failure instanceof Error ? failure.message : "Unable to prepare the report.")
    })
    return () => request.abort()
  }, [sampleId, reportType, generation])

  return <AnalysisTableCard className="report-workspace">
    <header className="report-toolbar">
      <div className="flex min-w-0 items-center gap-3">
        <span className="report-title-icon"><Sparkles className="size-5" aria-hidden="true" /></span>
        <div className="space-y-1">
          <h2 className="type-card-title">Try new report</h2>
          <p className="type-body-sm text-muted-foreground">The current clinical content in an alternate layout. Preview or download locally; no report is saved.</p>
        </div>
      </div>
      <div className="report-actions">
        <Button variant="outline" className="report-trial-action" onClick={onClose}><ArrowLeft className="size-4" />Current report</Button>
        <Button variant="outline" onClick={() => setGeneration(value => value + 1)} disabled={!data && !error}><RefreshCw className="size-4" />Refresh</Button>
        <Button variant="outline" disabled={!data} onClick={() => data && downloadText(data.html, `${data.filename}.html`, "text/html;charset=utf-8")}><Download className="size-4" />Download HTML</Button>
        <Button variant="outline" disabled={!data} onClick={() => data && downloadBlob(data.pdf, `${data.filename}.pdf`)}><Download className="size-4" />Download PDF</Button>
      </div>
    </header>
    <p className="type-meta text-muted-foreground">Temporary preview · {sampleId}{data ? ` · ${data.snapshot_count} included findings` : ""}</p>
    {data?.reporting_warning && <p role="alert" className="rounded-md border border-warning p-3 type-body">{data.reporting_warning}</p>}
    {error ? <p role="alert" className="text-destructive type-body-sm">{error}</p> : !data ? <AppLoader label="Preparing HTML and PDF preview" /> : <>
      <section aria-label="Temporary report preview" className="report-document min-w-0">
        <div className="report-format-toolbar">
          <span className="type-meta text-muted-foreground">Document view</span>
          <SegmentedControl className="report-format-tabs type-body" ariaLabel="New report preview format" value={format} onValueChange={setFormat}
            items={[
              { value: "html", label: <><FileCode2 className="size-4" aria-hidden="true" />HTML preview</> },
              { value: "pdf", label: <><FileText className="size-4" aria-hidden="true" />PDF preview</> },
            ]} />
        </div>
        <div className="report-paper-scroll" role="region" aria-label="New report document" tabIndex={0}>
          {format === "html" ? <ReportHtmlFrame title="New report HTML preview" html={data.html} className="report-paper" /> :
            <ReportPdfFrame title="New report PDF preview" blob={data.pdf} filename={`${data.filename}.pdf`} />}
        </div>
      </section>
    </>}
  </AnalysisTableCard>
}
