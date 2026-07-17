import { FormEvent, useMemo, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { Activity, FileText, Save } from "lucide-react"
import { ColumnDef } from "@tanstack/react-table"
import { api } from "@/lib/api"
import { DataTable } from "@/components/data-table/DataTable"
import { PageShell } from "@/components/layout/PageShell"
import { notifyActionError, notifySuccess } from "@/lib/notifications"

type ReportType = "dna" | "rna"

export function ReportsPage() {
  const [sampleIdInput, setSampleIdInput] = useState("")
  const [sampleId, setSampleId] = useState("")
  const [reportType, setReportType] = useState<ReportType>("dna")
  const [includeSnapshot, setIncludeSnapshot] = useState(true)
  const [message, setMessage] = useState("")

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["report-workspace", sampleId, reportType, includeSnapshot],
    queryFn: () => api.get(`/samples/${sampleId}/reports/${reportType}/preview?include_snapshot=${includeSnapshot}`).then((res) => res.data),
    enabled: Boolean(sampleId),
    retry: false,
  })

  const saveReport = useMutation({
    mutationFn: () => api.post(`/samples/${sampleId}/reports/${reportType}`, {
      html: data?.report?.html || "",
      snapshot_rows: data?.report?.snapshot_rows || [],
    }),
    onSuccess: (res) => {
      const reportId = res.data?.report?.id || res.data?.report_id || "created"
      setMessage(`Report saved: ${reportId}`)
      notifySuccess("Report saved", `Report ${reportId} was saved.`, "Reports")
    },
    onError: (err) => {
      setMessage(err instanceof Error ? err.message : "Unable to save report.")
      notifyActionError("Unable to save report", err, "Reports")
    },
  })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    setMessage("")
    setSampleId(sampleIdInput.trim())
  }

  const snapshotRows = useMemo(() => data?.report?.snapshot_rows || [], [data?.report?.snapshot_rows])
  const templateStatus = data?.meta?.template_status
  const hasRenderedHtml = Boolean(templateStatus?.has_html && data?.report?.html)
  const templateStatusMessage = templateStatus?.message || "Report preview has not been rendered yet."
  const snapshotColumns: ColumnDef<any, any>[] = useMemo(() => {
    const keys = Array.from(new Set<string>(snapshotRows.flatMap((row: any) => Object.keys(row || {})))).slice(0, 12)
    return keys.map((key) => ({
      id: key,
      header: key.replaceAll("_", " "),
      accessorFn: (row: any) => row?.[key] ?? "",
      cell: ({ row }) => <span className="block max-w-[18rem] truncate text-xs" title={String(row.original?.[key] ?? "")}>{String(row.original?.[key] ?? "-")}</span>,
    }))
  }, [snapshotRows])

  return (
    <PageShell
      eyebrow="Reports"
      title="Report Workspace"
      description="Preview and finalize DNA/RNA reports using the migrated report API."
      actions={
        <button
          onClick={() => refetch()}
          disabled={!sampleId || isLoading}
          className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted disabled:opacity-50"
        >
          <FileText className="h-4 w-4" />
          Refresh Preview
        </button>
      }
    >
      <section className="surface-panel border-t-4 border-t-tier3 p-4">
        <form onSubmit={submit} className="grid gap-3 md:grid-cols-[1fr_12rem_12rem_auto] md:items-end">
          <label className="space-y-1.5">
            <span className="text-xs font-bold uppercase text-muted-foreground">Sample ID</span>
            <input
              value={sampleIdInput}
              onChange={(event) => setSampleIdInput(event.target.value)}
              className="h-10 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/40"
              placeholder="CASE_DEMO"
            />
          </label>
          <label className="space-y-1.5">
            <span className="text-xs font-bold uppercase text-muted-foreground">Report type</span>
            <select
              value={reportType}
              onChange={(event) => setReportType(event.target.value as ReportType)}
              className="h-10 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/40"
            >
              <option value="dna">DNA</option>
              <option value="rna">RNA</option>
            </select>
          </label>
          <label className="flex h-10 items-center gap-2 rounded-lg border border-input bg-background px-3 text-sm font-semibold">
            <input type="checkbox" checked={includeSnapshot} onChange={(event) => setIncludeSnapshot(event.target.checked)} />
            Include snapshot
          </label>
          <button type="submit" className="h-10 rounded-lg bg-primary px-4 text-sm font-bold text-primary-foreground">
            Preview
          </button>
        </form>
      </section>

      {message && (
        <div className="rounded-lg border border-border bg-card p-3 text-sm font-semibold text-muted-foreground">{message}</div>
      )}

      {isLoading && <div className="flex justify-center p-10"><Activity className="animate-spin text-muted-foreground" /></div>}
      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          {error instanceof Error ? error.message : "Unable to load report preview"}
        </div>
      )}
      {data && (
        <div className="grid gap-3 xl:grid-cols-[1fr_26rem]">
          <section className="surface-panel border-t-4 border-t-tier2 p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="text-lg font-bold">{sampleId} {reportType.toUpperCase()} Preview</h2>
                <p className="text-sm text-muted-foreground">Rendered report HTML and report context from the backend workflow.</p>
              </div>
              <span
                className={`rounded-full px-2 py-1 text-xs font-semibold ${
                  templateStatus?.status === "ready"
                    ? "bg-pass/10 text-pass"
                    : "bg-warn/10 text-warn"
                }`}
              >
                {templateStatus?.status === "ready" ? "template ready" : "template unavailable"}
              </span>
              <button
                onClick={() => saveReport.mutate()}
                disabled={saveReport.isPending || !hasRenderedHtml}
                title={hasRenderedHtml ? "Finalize this rendered report" : templateStatusMessage}
                className="inline-flex items-center gap-2 rounded-lg bg-pass px-3 py-2 text-sm font-bold text-white disabled:opacity-50"
              >
                {saveReport.isPending ? <Activity className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                Finalize
              </button>
            </div>
            {templateStatus?.status !== "ready" && (
              <div className="mb-3 rounded-lg border border-warn/30 bg-warn/10 px-3 py-2 text-sm text-warn">
                {templateStatusMessage}
              </div>
            )}
            {hasRenderedHtml ? (
              <iframe
                title={`${sampleId} report preview`}
                srcDoc={data.report.html}
                className="h-[42rem] w-full rounded-lg border border-border bg-white"
              />
            ) : (
              <div className="rounded-lg border border-dashed border-border bg-muted/25 p-6 text-sm text-muted-foreground">
                No rendered report HTML was returned for this preview.
              </div>
            )}
          </section>
          <aside className="space-y-3">
            <section className="surface-panel border-t-4 border-t-tier4 p-3">
              <h2 className="mb-2 text-sm font-bold uppercase tracking-wider text-muted-foreground">Snapshot Rows</h2>
              <DataTable columns={snapshotColumns} data={snapshotRows} filename={`${sampleId}_${reportType}_snapshot.csv`} />
            </section>
          </aside>
        </div>
      )}
    </PageShell>
  )
}
