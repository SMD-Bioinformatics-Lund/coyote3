import { useEffect, useState } from "react"
import { Download, ExternalLink, FileText, LoaderCircle, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { buttonVariants } from "@/components/ui/button-variants"
import { downloadBlob } from "@/lib/browser-download"

export function ReportPdfFrame({ blob, title, filename }: {
  blob: Blob
  title: string
  filename: string
}) {
  const [source, setSource] = useState<{ blob: Blob; url: string } | null>(null)
  const [generation, setGeneration] = useState(0)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const supported = navigator.pdfViewerEnabled !== false
  const url = source?.blob === blob ? source.url : null

  useEffect(() => {
    const nextUrl = URL.createObjectURL(blob)
    setLoading(true)
    setFailed(false)
    setSource({ blob, url: nextUrl })
    return () => {
      URL.revokeObjectURL(nextUrl)
    }
  }, [blob, generation])

  useEffect(() => {
    if (!url || !loading || !supported) return
    const timeout = window.setTimeout(() => { setLoading(false); setFailed(true) }, 15000)
    return () => window.clearTimeout(timeout)
  }, [url, loading, supported])

  return <div className="report-pdf-viewer">
    <div className="report-viewer-toolbar">
      <span className="report-viewer-label type-body-sm"><FileText className="size-4" aria-hidden="true" />PDF document</span>
      <div className="report-viewer-actions">
        <Button variant="ghost" size="icon" aria-label="Reload PDF viewer" title="Reload PDF viewer" onClick={() => setGeneration(value => value + 1)}>
          <RefreshCw className="size-4" aria-hidden="true" />
        </Button>
        {url && <a className={buttonVariants({ variant: "outline" })} href={url} target="_blank" rel="noopener noreferrer">
          <ExternalLink className="size-4" aria-hidden="true" />Open PDF
        </a>}
        <Button variant="outline" onClick={() => downloadBlob(blob, filename)}>
          <Download className="size-4" aria-hidden="true" />Download this PDF
        </Button>
      </div>
    </div>
    {(!supported || failed) && <p role="status" className="rounded-lg border border-border p-4 type-body-sm">
      {!supported ? "This browser does not support embedded PDF previews." : "The PDF viewer could not finish loading."} Use Open PDF or Download this PDF, or reload the viewer.
    </p>}
    {supported && <>
      {loading && <p role="status" aria-live="polite" className="flex items-center gap-2 type-body-sm text-muted-foreground">
        <LoaderCircle className="size-4 motion-safe:animate-spin" aria-hidden="true" />Loading PDF viewer
      </p>}
      {url && <iframe key={url} title={title} src={url}
        onLoad={() => { setLoading(false); setFailed(false) }} onError={() => { setLoading(false); setFailed(true) }}
        className="report-pdf-canvas" />}
    </>}
    <p className="report-viewer-help type-meta text-muted-foreground">If the embedded viewer stays blank, open the PDF in a new tab or download it.</p>
  </div>
}
