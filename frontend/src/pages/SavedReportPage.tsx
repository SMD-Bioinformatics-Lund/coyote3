import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { Activity, ArrowLeft, Download } from "lucide-react"
import { PageShell } from "@/components/layout/PageShell"
import { ReportHtmlFrame } from "@/components/reports/ReportHtmlFrame"
import { apiPath } from "@/lib/runtime-paths"

export function SavedReportPage() {
  const { id = "", reportId = "" } = useParams()
  const [html, setHtml] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError("")
    fetch(apiPath(`/samples/${id}/reports/${reportId}/html`))
      .then(async (response) => {
        const text = await response.text()
        if (!response.ok) throw new Error(text || `Report request failed (${response.status})`)
        return text
      })
      .then((text) => {
        if (!cancelled) setHtml(text)
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unable to load report")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [id, reportId])

  return (
    <PageShell
      eyebrow="Report"
      title={`${id} report ${reportId}`}
      description="Saved report view migrated from the historical report file route."
      actions={
        <>
          <a
            href={apiPath(`/samples/${id}/reports/${reportId}/download`)}
            className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted"
          >
            <Download className="h-4 w-4" />
            Download
          </a>
          <Link to={`/samples/${id}?tab=reports`} className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted">
            <ArrowLeft className="h-4 w-4" />
            Sample
          </Link>
        </>
      }
    >
      {loading ? (
        <div className="flex justify-center p-10"><Activity className="animate-spin text-muted-foreground" /></div>
      ) : error ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">{error}</div>
      ) : (
        <ReportHtmlFrame title={`${id} saved report`} html={html} className="rounded-xl shadow-sm" />
      )}
    </PageShell>
  )
}
