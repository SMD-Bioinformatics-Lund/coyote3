import { FormEvent, useMemo, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { Link, useSearchParams } from "react-router-dom"
import { Activity, FileText, Save, Search } from "lucide-react"
import { ColumnDef } from "@tanstack/react-table"
import { api } from "@/lib/api"
import { DataTable } from "@/components/data-table/DataTable"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { ReportHtmlFrame } from "@/components/reports/ReportHtmlFrame"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { humanRelativeDate } from "@/lib/detail-formatters"
import { sampleDetailPath } from "@/lib/sample-routing"
import { sampleSubpanel } from "@/lib/sample-shape"

type ReportType = "dna" | "rna"

export function ReportsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialSampleId = searchParams.get("sample_id") || searchParams.get("sample") || ""
  const initialReportType = (searchParams.get("report_type") || "dna") as ReportType
  const [sampleIdInput, setSampleIdInput] = useState(initialSampleId)
  const [sampleId, setSampleId] = useState(initialSampleId)
  const [reportType, setReportType] = useState<ReportType>(initialReportType === "rna" ? "rna" : "dna")
  const [includeSnapshot, setIncludeSnapshot] = useState(true)
  const [message, setMessage] = useState("")

  const sampleLookup = useQuery({
    queryKey: ["report-sample-lookup", sampleIdInput],
    queryFn: () => {
      const params = new URLSearchParams()
      params.set("profile_scope", "all")
      params.set("per_page", "8")
      params.set("search_str", sampleIdInput.trim())
      return api.get(`/samples?${params.toString()}`).then((res) => res.data)
    },
    enabled: sampleIdInput.trim().length >= 2,
    staleTime: 30_000,
  })

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
    selectSample(sampleIdInput.trim())
  }

  const selectSample = (nextSampleId: string, nextReportType: ReportType = reportType) => {
    setMessage("")
    setSampleId(nextSampleId)
    setSampleIdInput(nextSampleId)
    const nextParams = new URLSearchParams(searchParams)
    if (nextSampleId) nextParams.set("sample_id", nextSampleId)
    else nextParams.delete("sample_id")
    nextParams.set("report_type", nextReportType)
    setSearchParams(nextParams, { replace: true })
  }

  const sampleOptions = sampleLookup.data?.live_samples || []
  const updateReportType = (nextType: ReportType) => {
    setReportType(nextType)
    if (sampleId) {
      const nextParams = new URLSearchParams(searchParams)
      nextParams.set("sample_id", sampleId)
      nextParams.set("report_type", nextType)
      setSearchParams(nextParams, { replace: true })
    }
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
        <form onSubmit={submit} className="grid gap-3 md:grid-cols-[minmax(20rem,1fr)_12rem_12rem_auto] md:items-end">
          <label className="relative space-y-1.5">
            <span className="text-xs font-bold uppercase text-muted-foreground">Sample ID</span>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <input
                value={sampleIdInput}
                onChange={(event) => setSampleIdInput(event.target.value)}
                className="h-10 w-full rounded-lg border border-input bg-background px-9 text-sm outline-none focus:ring-2 focus:ring-primary/40"
                placeholder="Search sample name, case id, or ObjectId"
              />
              {sampleLookup.isFetching && (
                <Activity className="absolute right-3 top-3 h-4 w-4 animate-spin text-muted-foreground" />
              )}
            </div>
            {sampleOptions.length > 0 && sampleIdInput.trim() !== sampleId && (
              <div className="absolute left-0 right-0 top-full z-30 mt-1 max-h-80 overflow-y-auto rounded-xl border border-border bg-popover p-1 shadow-xl">
                {sampleOptions.map((sample: any) => (
                  <button
                    key={String(sample._id)}
                    type="button"
                    onClick={() => selectSample(String(sample.name || sample.sample_name || sample._id))}
                    className="flex w-full items-start justify-between gap-3 rounded-lg px-3 py-2 text-left text-sm hover:bg-primary/10"
                  >
                    <span className="min-w-0">
                      <span className="block truncate font-bold text-foreground">{sample.name || sample.case_id || sample._id}</span>
                      <span className="mt-0.5 block truncate text-xs text-muted-foreground">
                        {sample.asp_id || "-"} / {sampleSubpanel(sample) || "-"} / {sample.environment || "-"}
                      </span>
                    </span>
                    <span className="shrink-0 text-xs font-semibold text-muted-foreground">
                      {humanRelativeDate(sample.time_added)}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </label>
          <label className="space-y-1.5">
            <span className="text-xs font-bold uppercase text-muted-foreground">Report type</span>
            <select
              value={reportType}
              onChange={(event) => updateReportType(event.target.value as ReportType)}
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
        {sampleId && (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="font-bold uppercase tracking-wide">Selected sample</span>
            <Link to={sampleDetailPath(data?.sample, sampleId)} className="rounded-full border border-primary/25 bg-primary/10 px-2.5 py-1 font-semibold text-primary hover:bg-primary/15">
              {data?.sample?.name || sampleId}
            </Link>
          </div>
        )}
      </section>

      {message && (
        <div className="glass-card rounded-lg p-3 text-sm font-semibold text-muted-foreground">{message}</div>
      )}

      {isLoading && <AppLoader label="Loading report preview" />}
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
              <ReportHtmlFrame
                title={`${sampleId} report preview`}
                html={data.report.html}
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
