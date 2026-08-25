import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { Activity, AlertTriangle, Download, Eye, FileText, Save, ShieldCheck, X } from "lucide-react"
import { api } from "@/lib/api"
import { apiPath } from "@/lib/runtime-paths"
import { DataTable } from "@/components/data-table/DataTable"
import { AppLoader } from "@/components/layout/AppLoader"
import { ReportHtmlFrame } from "@/components/reports/ReportHtmlFrame"
import { ColumnDef } from "@tanstack/react-table"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { Button } from "@/components/ui/button"
import { TierBadge } from "@/lib/variant-ui"

type ReportType = "dna" | "rna"

function formatSnapshotValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-"
  if (typeof value === "string") return value
  return JSON.stringify(value)
}

const snvSnapshotColumns: ColumnDef<any, any>[] = [
  {
    id: "gene",
    header: "Gene",
    accessorFn: (row) => row.gene || row.gene1 || row.hgnc_symbol || "-",
    cell: ({ row }) => <span className="font-bold text-primary">{String(row.getValue("gene"))}</span>,
  },
  {
    id: "variant",
    header: "Variant",
    accessorFn: (row) => row.variant || row.hgvs || row.variant_name || row.breakpoint || "-",
    cell: ({ row }) => <span className="text-xs">{String(row.getValue("variant"))}</span>,
  },
  {
    id: "classification",
    header: "Class",
    accessorFn: (row) => row.class || row.tier || row.classification || "-",
    cell: ({ row }) => <TierBadge tier={row.getValue("classification")} />,
  },
  {
    id: "text",
    header: "Text",
    accessorFn: (row) => row.text || row.description || row.comment || "",
    cell: ({ row }) => <span className="block max-w-[30rem] truncate text-xs">{String(row.getValue("text") || "-")}</span>,
  },
]

const rnaSnapshotColumns: ColumnDef<any, any>[] = [
  {
    id: "fusion",
    header: "Fusion",
    accessorFn: (row) => row.fusion ?? "-",
    cell: ({ row }) => <span className="font-bold text-link">{String(row.getValue("fusion"))}</span>,
  },
  {
    id: "breakpoints",
    header: "Breakpoints",
    accessorFn: (row) => [row.breakpoint_1, row.breakpoint_2].filter(Boolean).join(" / ") || "-",
    cell: ({ row }) => <span className="text-xs">{String(row.getValue("breakpoints"))}</span>,
  },
  {
    id: "effect",
    header: "Effect",
    accessorFn: (row) => row.effect ?? "-",
  },
  {
    id: "support",
    header: "Pairs / reads",
    accessorFn: (row) => `${row.spanning_pairs ?? "-"} / ${row.spanning_reads ?? "-"}`,
  },
  {
    id: "classification",
    header: "Classification",
    accessorFn: (row) => row.classification ?? "-",
    cell: ({ row }) => <TierBadge tier={row.getValue("classification")} />,
  },
  {
    id: "text",
    header: "Annotation",
    accessorFn: (row) => row.text ?? "",
    cell: ({ row }) => (
      <span
        className="block max-w-[34rem] truncate text-xs"
        title={String(row.getValue("text") || "")}
      >
        {String(row.getValue("text") || "-")}
      </span>
    ),
  },
]

const cnvSnapshotColumns: ColumnDef<any, any>[] = [
  {
    id: "genes",
    header: "Genes",
    accessorFn: (row) => row.gene || row.genes?.join(", ") || "-",
    cell: ({ row }) => <span className="font-semibold text-link">{String(row.getValue("genes"))}</span>,
  },
  { id: "region", header: "Region", accessorFn: (row) => row.region || "-" },
  { id: "size", header: "Size", accessorFn: (row) => row.size ?? "-" },
  { id: "type", header: "Type", accessorFn: (row) => row.cnv_type || "-" },
  { id: "ratio", header: "Ratio", accessorFn: (row) => row.ratio ?? "-" },
  {
    id: "callers",
    header: "Callers",
    accessorFn: (row) => Array.from(new Set(row.callers || [])).join(", ") || "-",
  },
]

const translocationSnapshotColumns: ColumnDef<any, any>[] = [
  { id: "gene1", header: "Gene 1", accessorFn: (row) => row.gene1 || "-" },
  { id: "gene2", header: "Gene 2", accessorFn: (row) => row.gene2 || "-" },
  { id: "breakpoint", header: "Breakpoint", accessorFn: (row) => row.breakpoint || "-" },
  { id: "hgvsc", header: "HGVS.c", accessorFn: (row) => row.hgvsc || "-" },
  { id: "hgvsp", header: "HGVS.p", accessorFn: (row) => row.hgvsp || "-" },
  { id: "effect", header: "Effect", accessorFn: (row) => row.effect || "-" },
]

const biomarkerSnapshotColumns: ColumnDef<any, any>[] = [
  { id: "biomarker", header: "Biomarker", accessorFn: (row) => row.biomarker || "-" },
  {
    id: "result",
    header: "Result",
    accessorFn: (row) => formatSnapshotValue(row.result),
    cell: ({ row }) => (
      <span className="block max-w-[54rem] truncate" title={String(row.getValue("result"))}>
        {String(row.getValue("result") || "-")}
      </span>
    ),
  },
]

const pgxSnapshotColumns: ColumnDef<any, any>[] = [
  { id: "gene", header: "Gene", accessorFn: (row) => row.gene || "-" },
  {
    id: "result",
    header: "Result",
    accessorFn: (row) => row.pgx_result || row.phenotype || row.diplotype || "-",
  },
  {
    id: "details",
    header: "Details",
    accessorFn: (row) =>
      [
        row.diplotype && `Diplotype: ${row.diplotype}`,
        row.phenotype && `Phenotype: ${row.phenotype}`,
        row.activity_score !== null && row.activity_score !== undefined
          ? `Activity score: ${formatSnapshotValue(row.activity_score)}`
          : null,
        row.recommendation ? `Recommendation: ${formatSnapshotValue(row.recommendation)}` : null,
      ]
        .filter(Boolean)
        .join("; ") || "-",
    cell: ({ row }) => (
      <span className="block max-w-[54rem] truncate" title={String(row.getValue("details"))}>
        {String(row.getValue("details") || "-")}
      </span>
    ),
  },
]

const snapshotSections = [
  { type: "SNV", label: "Small variants", columns: snvSnapshotColumns },
  { type: "CNV", label: "Copy-number variants", columns: cnvSnapshotColumns },
  { type: "TRANSLOCATION", label: "DNA fusions and translocations", columns: translocationSnapshotColumns },
  { type: "FUSION", label: "RNA fusions", columns: rnaSnapshotColumns },
  { type: "BIOMARKER", label: "Biomarkers", columns: biomarkerSnapshotColumns },
  { type: "PGX", label: "Pharmacogenomics", columns: pgxSnapshotColumns },
] as const

function snapshotAnalysisType(row: any, reportType: ReportType): string {
  const explicitType = String(row?.analysis_type || "").trim().toUpperCase()
  if (explicitType) return explicitType
  return reportType === "rna" ? "FUSION" : "SNV"
}

export function ReportsTab({
  sampleId,
  reportType: fixedReportType,
}: {
  sampleId: string
  reportType?: ReportType
}) {
  const queryClient = useQueryClient()
  const [selectedReportType, setSelectedReportType] = useState<ReportType>("dna")
  const reportType = fixedReportType ?? selectedReportType
  const [includeSnapshot, setIncludeSnapshot] = useState(true)
  const [confirmOpen, setConfirmOpen] = useState(false)

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["report-preview", sampleId, reportType, includeSnapshot],
    queryFn: () =>
      api
        .get(`/samples/${sampleId}/reports/${reportType}/preview?include_snapshot=${includeSnapshot}&save=false`)
        .then((res) => res.data),
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
    onError: (error) => {
      const sampleName = data?.sample?.name || sampleId
      notifyActionError("Unable to save report", error, "Reports", {
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
        { credentials: "same-origin" }
      )
      if (!response.ok) {
        const message = await response.text()
        throw new Error(message || `PDF request failed with ${response.status}`)
      }
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `${data?.sample?.name || sampleId}_${reportType}_preview.pdf`
      a.click()
      URL.revokeObjectURL(url)
    },
    onSuccess: () => {
      const sampleName = data?.sample?.name || sampleId
      notifySuccess("PDF generated", `The temporary ${reportType.toUpperCase()} report preview PDF for ${sampleName} was downloaded.`, "Reports", {
        type: "report",
        id: sampleId,
        name: `${sampleName} ${reportType.toUpperCase()} preview`,
        sampleName,
      })
    },
    onError: (error) => {
      const sampleName = data?.sample?.name || sampleId
      notifyActionError("Unable to generate PDF", error, "Reports", {
        type: "report",
        id: sampleId,
        name: `${sampleName} ${reportType.toUpperCase()} preview`,
        sampleName,
      })
    },
  })

  const templateStatus = data?.meta?.template_status
  const snapshotRows = data?.report?.snapshot_rows || []
  const visibleSnapshotSections = snapshotSections
    .map((section) => ({
      ...section,
      rows: snapshotRows.filter((row: any) => snapshotAnalysisType(row, reportType) === section.type),
    }))
    .filter((section) => section.rows.length > 0)
  const hasRenderedHtml = Boolean(templateStatus?.has_html && data?.report?.html)
  const templateStatusMessage = templateStatus?.message || "Report preview has not been rendered yet."

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-xl font-bold">Clinical Report Preview</h3>
          <p className="text-sm text-muted-foreground">
            Preview report context and snapshot rows generated by the backend report workflow.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {!fixedReportType && (
            <div className="inline-flex rounded-lg border border-border bg-background p-1">
              {(["dna", "rna"] as ReportType[]).map((type) => (
                <button
                  key={type}
                  onClick={() => setSelectedReportType(type)}
                  className={`rounded-md px-3 py-1.5 text-xs font-bold uppercase ${reportType === type ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}
                >
                  {type}
                </button>
              ))}
            </div>
          )}
          <label className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm">
            <input
              type="checkbox"
              checked={includeSnapshot}
              onChange={(event) => setIncludeSnapshot(event.target.checked)}
            />
            Snapshot
          </label>
          <Button
            type="button"
            variant="outline"
            onClick={() => downloadPreviewPdf.mutate()}
            disabled={!hasRenderedHtml || downloadPreviewPdf.isPending}
            title={hasRenderedHtml ? "Download preview PDF" : templateStatusMessage}
          >
            {downloadPreviewPdf.isPending ? <Activity className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            PDF
          </Button>
          <Button
            type="button"
            onClick={() => setConfirmOpen(true)}
            disabled={!hasRenderedHtml || saveReport.isPending}
            title={hasRenderedHtml ? "Save this rendered report" : templateStatusMessage}
          >
            {saveReport.isPending ? <Activity className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Save
          </Button>
          <Link
            to={`/reports?sample_id=${encodeURIComponent(sampleId)}&report_type=${reportType}`}
            className="inline-flex h-9 items-center gap-2 rounded-lg border border-border px-3 text-sm font-semibold hover:bg-muted"
          >
            Workspace
          </Link>
        </div>
      </div>

      {isLoading ? (
        <AppLoader label="Loading report preview" />
      ) : error ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          <div className="flex items-center gap-2 font-semibold"><AlertTriangle className="h-4 w-4" /> Error loading report preview</div>
          <p className="mt-1">{error instanceof Error ? error.message : "Unknown error"}</p>
        </div>
      ) : (
        <div className="space-y-4">
          <section className="glass-card p-4">
            <div className="mb-3 flex items-center gap-2">
              <FileText className="h-5 w-5 text-primary" />
              <h4 className="font-semibold">{data?.sample?.name || sampleId} {reportType.toUpperCase()} report</h4>
              <span
                className={`rounded-full px-2 py-1 text-xs font-semibold ${
                  templateStatus?.status === "ready"
                    ? "bg-pass/10 text-pass"
                    : "bg-warn/10 text-warn"
                }`}
              >
                {templateStatus?.status === "ready" ? "template ready" : "template unavailable"}
              </span>
              <span className="ml-auto rounded-full bg-muted px-2 py-1 text-xs font-semibold text-muted-foreground">
                {data?.meta?.snapshot_count || 0} snapshot row(s)
              </span>
            </div>
            {templateStatus?.status !== "ready" && (
              <div className="mb-3 rounded-lg border border-warn/30 bg-warn/10 px-3 py-2 text-sm text-warn">
                {templateStatusMessage}
              </div>
            )}
            {visibleSnapshotSections.length > 0 ? (
              <div className="divide-y divide-border">
                {visibleSnapshotSections.map((section) => (
                  <div key={section.type} className="py-4 first:pt-0 last:pb-0">
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <h5 className="font-semibold">{section.label}</h5>
                      <span className="rounded-full bg-muted px-2 py-1 text-xs font-semibold text-muted-foreground">
                        {section.rows.length} finding(s)
                      </span>
                    </div>
                    <DataTable
                      columns={section.columns as ColumnDef<any, any>[]}
                      data={section.rows}
                      filename={`${sampleId}_${reportType}_${section.type.toLowerCase()}_snapshot.csv`}
                    />
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-lg border border-border px-4 py-8 text-center text-sm text-muted-foreground">
                No reportable findings are included in this snapshot.
              </div>
            )}
          </section>
          <section className="glass-card p-4">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <Eye className="h-5 w-5 text-primary" />
              <h4 className="font-semibold">Rendered report preview</h4>
              <span className="rounded-full bg-muted px-2 py-1 text-xs font-semibold text-muted-foreground">
                Temporary until saved
              </span>
            </div>
            <ReportHtmlFrame
              title="Report preview"
              html={hasRenderedHtml ? data?.report?.html : "<p>No report preview available.</p>"}
            />
          </section>
        </div>
      )}
      {confirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4">
          <div className="w-full max-w-lg rounded-xl border border-border bg-card p-4 shadow-lg">
            <div className="mb-3 flex items-start gap-3">
              <div className="rounded-full bg-primary/10 p-2 text-primary">
                <ShieldCheck className="h-5 w-5" />
              </div>
              <div>
                <h4 className="font-semibold">Confirm report save</h4>
                <p className="mt-1 text-sm text-muted-foreground">
                  This saves the current backend-rendered preview as HTML and PDF, and persists the
                  reported finding snapshot rows for this report.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setConfirmOpen(false)}
                className="ml-auto rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                title="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="rounded-lg border border-border bg-muted/40 p-3 text-sm">
              <div className="flex justify-between gap-3">
                <span className="text-muted-foreground">Report</span>
                <span className="font-semibold">{reportType.toUpperCase()}</span>
              </div>
              <div className="mt-1 flex justify-between gap-3">
                <span className="text-muted-foreground">Snapshot rows</span>
                <span className="font-semibold">{data?.meta?.snapshot_count || 0}</span>
              </div>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setConfirmOpen(false)}>
                Cancel
              </Button>
              <Button type="button" onClick={() => saveReport.mutate()} disabled={saveReport.isPending}>
                {saveReport.isPending ? <Activity className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                Confirm save
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
