import { useQuery } from "@tanstack/react-query"
import type { ReactNode } from "react"
import type { ColumnDef } from "@tanstack/react-table"
import { AlertTriangle, BarChart3, Dna } from "lucide-react"

import { DataTable } from "@/components/data-table/DataTable"
import { AppLoader } from "@/components/layout/AppLoader"
import { ResizableSplitPane } from "@/components/layout/ResizableSplitPane"
import { AppTooltip } from "@/components/ui/app-tooltip"
import { api } from "@/lib/api"

type ExpressionRow = {
  hgnc_symbol?: string
  ensembl_gene_id?: string
  sample_expression?: number
  reference_mean?: number
  z?: number
}

type ClassificationRow = {
  class?: string
  class_?: string
  score?: number
  true?: number
  total?: number
}

function useRnaAnalysis(sampleId: string) {
  return useQuery({
    queryKey: ["sample-rna-analysis", sampleId],
    queryFn: () => api.get(`/samples/${sampleId}/rna-analysis`).then((response) => response.data),
    staleTime: 60_000,
  })
}

function AnalysisState({
  isLoading,
  error,
  empty,
}: {
  isLoading: boolean
  error: unknown
  empty: string
}) {
  if (isLoading) return <AppLoader label="Loading RNA analysis" />
  if (error) {
    return (
      <div className="flex items-center gap-2 p-4 text-destructive">
        <AlertTriangle className="h-4 w-4" />
        Unable to load RNA analysis.
      </div>
    )
  }
  return <p className="rounded-lg border border-dashed border-border p-2 gap-2 text-xs text-muted-foreground">{empty}</p>
}

function zScorePresentation(value: number) {
  const magnitude = Math.abs(value)
  const direction = value > 0 ? "above" : value < 0 ? "below" : "at"
  if (magnitude >= 3) {
    return {
      barClass: value >= 0 ? "bg-pass/75" : "bg-fail/75",
      label: value >= 0 ? "Strong increase" : "Strong decrease",
      tone: value >= 0 ? "success" as const : "danger" as const,
      detail: `${magnitude.toFixed(2)} standard deviations ${direction} the reference mean. This is a strong expression deviation (|Z| >= 3).`,
    }
  }
  if (magnitude >= 2) {
    return {
      barClass: value >= 0 ? "bg-pass/50" : "bg-fail/50",
      label: value >= 0 ? "Moderate increase" : "Moderate decrease",
      tone: value >= 0 ? "success" as const : "danger" as const,
      detail: `${magnitude.toFixed(2)} standard deviations ${direction} the reference mean. This is a moderate expression deviation (2 <= |Z| < 3).`,
    }
  }
  if (value !== 0) {
    return {
      barClass: value > 0 ? "bg-pass/30" : "bg-fail/30",
      label: value > 0 ? "Reference-range increase" : "Reference-range decrease",
      tone: value > 0 ? "success" as const : "danger" as const,
      detail: `${magnitude.toFixed(2)} standard deviations ${direction} the reference mean. This directional shift remains within the displayed reference range (|Z| < 2).`,
    }
  }
  return {
    barClass: "bg-muted-foreground/25",
    label: "At reference mean",
    tone: "neutral" as const,
    detail: "The expression value is at the reference mean (Z = 0).",
  }
}

function SignedScoreBar({ value, extent }: { value: number; extent: number }) {
  const width = Math.min(50, (Math.abs(value) / Math.max(extent, 1)) * 50)
  const presentation = zScorePresentation(value)
  return (
    <AppTooltip
      label={`${presentation.label}: Z ${value.toFixed(2)}`}
      context="Expression z-score"
      tone={presentation.tone}
      content={presentation.detail}
    >
      <div
        className="relative h-6 min-w-48 overflow-hidden rounded-md border border-border bg-muted/45"
        aria-label={`Z-score ${value.toFixed(2)}: ${presentation.label}`}
        tabIndex={0}
      >
        <span className="absolute inset-y-0 left-1/2 w-px bg-foreground/35" />
        <span
          className={`absolute inset-y-0 ${value >= 0 ? "left-1/2" : "right-1/2"} ${presentation.barClass}`}
          style={{ width: `${width}%` }}
        />
        <span className="relative z-10 flex h-full items-center justify-center type-meta font-bold type-numeric">
          {value.toFixed(2)}
        </span>
      </div>
    </AppTooltip>
  )
}

function ClassificationScore({ row }: { row: ClassificationRow }) {
  const score = Number(row.score || 0)
  const percent = Math.max(0, Math.min(100, score <= 1 ? score * 100 : score))
  const evidence = Number.isFinite(Number(row.true)) && Number.isFinite(Number(row.total))
    ? `${Number(row.true)} of ${Number(row.total)} classifier votes support this class.`
    : `The classifier assigned a score of ${score.toFixed(2)} to this class.`

  return (
    <AppTooltip
      label={`Classifier score ${score.toFixed(2)}`}
      context="Expression-based classification"
      tone="info"
      content={evidence}
    >
      <div
        className="relative h-6 min-w-44 overflow-hidden rounded-md border border-border bg-muted/45"
        role="progressbar"
        aria-label={`${row.class || row.class_ || "Classification"} score`}
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        tabIndex={0}
      >
        <span className="absolute inset-y-0 left-0 bg-tier3/65" style={{ width: `${percent}%` }} />
        <span className="relative z-10 flex h-full items-center justify-center type-meta font-bold type-numeric">
          {score.toFixed(2)}
        </span>
      </div>
    </AppTooltip>
  )
}

function ExpressionPanel({ rows, sampleId, header }: { rows: ExpressionRow[]; sampleId: string; header?: ReactNode }) {
  const extent = Math.max(2, ...rows.map((row) => Math.abs(Number(row.z || 0))))
  const columns: ColumnDef<ExpressionRow, any>[] = [
    {
      id: "gene",
      header: "Gene",
      accessorFn: (row) => row.hgnc_symbol || row.ensembl_gene_id || "-",
      cell: ({ row }) => (
        <div className="leading-tight">
          <span className="block font-bold text-foreground">{row.original.hgnc_symbol || row.original.ensembl_gene_id || "-"}</span>
          {row.original.hgnc_symbol && row.original.ensembl_gene_id ? (
            <span className="block type-meta text-muted-foreground">{row.original.ensembl_gene_id}</span>
          ) : null}
        </div>
      ),
    },
    {
      id: "tpm",
      header: "TPM",
      accessorFn: (row) => Number(row.sample_expression || 0),
      cell: ({ getValue }) => <span className="type-numeric">{Number(getValue()).toFixed(2)}</span>,
    },
    {
      id: "reference_mean",
      header: "Reference mean",
      accessorFn: (row) => Number(row.reference_mean || 0),
      cell: ({ getValue }) => <span className="type-numeric">{Number(getValue()).toFixed(2)}</span>,
    },
    {
      id: "z_score",
      header: "Z-score",
      accessorFn: (row) => Number(row.z || 0),
      meta: { headerClassName: "min-w-52", cellClassName: "min-w-52" },
      cell: ({ getValue }) => <SignedScoreBar value={Number(getValue())} extent={extent} />,
    },
  ]

  return (
    <section className="glass-card flex w-full min-w-0 flex-col overflow-hidden" aria-label="Expression of selected genes">
      {header ? (
        <div className="flex min-h-9 shrink-0 items-center justify-between gap-3 border-b border-border px-4 py-2">
          {header}
        </div>
      ) : null}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/50 bg-muted/50 p-3">
        <div>
          <h4 className="flex items-center gap-2 text-sm font-semibold"><Dna className="size-4" /> Expression of Selected Genes</h4>
          <p className="text-xs text-muted-foreground">TPM and z-scores compared with the configured reference cohort.</p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5" aria-label="Z-score legend">
          <span className="badge badge-neutral">|Z| &lt; 2 reference</span>
          <span className="badge badge-warning">|Z| 2-3 moderate</span>
          <span className="badge badge-success">Z &gt;= 3 increase</span>
          <span className="badge badge-danger">Z &lt;= -3 decrease</span>
        </div>
      </div>
      <div className="flex min-h-72 min-w-0 flex-col bg-muted/10 p-3">
        <DataTable
          columns={columns}
          data={rows}
          filename={`${sampleId}.rna-expression.csv`}
          rowLabel="genes"
          searchPlaceholder="Search expression genes..."
          stateKey={`rna-expression-${sampleId}`}
        />
      </div>
    </section>
  )
}

function ClassificationPanel({ rows, sampleId, header }: { rows: ClassificationRow[]; sampleId: string; header?: ReactNode }) {
  const orderedRows = [...rows].sort((left, right) => Number(right.score || 0) - Number(left.score || 0))
  const columns: ColumnDef<ClassificationRow, any>[] = [
    {
      id: "class",
      header: "Class",
      accessorFn: (row) => row.class || row.class_ || "-",
      cell: ({ getValue }) => <span className="font-semibold text-foreground">{String(getValue())}</span>,
    },
    {
      id: "score",
      header: "Score",
      accessorFn: (row) => Number(row.score || 0),
      meta: { headerClassName: "min-w-48", cellClassName: "min-w-48" },
      cell: ({ row }) => <ClassificationScore row={row.original} />,
    },
  ]

  return (
    <section className="glass-card flex w-full min-w-0 flex-col overflow-hidden" aria-label="Expression-based classification">
      {header ? (
        <div className="flex min-h-9 shrink-0 items-center justify-between gap-3 border-b border-border px-4 py-2">
          {header}
        </div>
      ) : null}
      <div className="flex items-center justify-between border-b border-border/50 bg-muted/50 p-3">
        <div>
          <h4 className="flex items-center gap-2 text-sm font-semibold"><BarChart3 className="size-4" /> Expression-Based Classification</h4>
          <p className="text-xs text-muted-foreground">Classifier scores are ranked from highest to lowest.</p>
        </div>
      </div>
      <div className="flex min-h-72 min-w-0 flex-col bg-muted/10 p-3">
        <DataTable
          columns={columns}
          data={orderedRows}
          filename={`${sampleId}.rna-classification.csv`}
          rowLabel="classes"
          searchPlaceholder="Search classification classes..."
          stateKey={`rna-classification-${sampleId}`}
        />
      </div>
    </section>
  )
}

export function RnaAnalysisTab({ sampleId, header }: { sampleId: string; header?: ReactNode }) {
  const query = useRnaAnalysis(sampleId)
  if (query.isLoading || query.error) {
    return <AnalysisState isLoading={query.isLoading} error={query.error} empty="No RNA analysis result was ingested for this sample." />
  }

  const expressionRows = (query.data?.expression?.sample || []) as ExpressionRow[]
  const classificationRows = (query.data?.classification?.classifier_results || []) as ClassificationRow[]
  const expressionPanel = expressionRows.length
    ? <ExpressionPanel rows={expressionRows} sampleId={sampleId} header={header} />
    : null
  const classificationPanel = classificationRows.length
    ? <ClassificationPanel rows={classificationRows} sampleId={sampleId} header={expressionRows.length ? undefined : header} />
    : null

  if (!expressionPanel && !classificationPanel) {
    return <AnalysisState isLoading={false} error={null} empty="No expression or expression-based classification result was ingested for this sample." />
  }

  return (
    <div className="flex flex-col space-y-4 pb-4">
      {expressionPanel && classificationPanel ? (
        <ResizableSplitPane
          primary={expressionPanel}
          secondary={classificationPanel}
          storageKey="coyote3:rna-analysis-split"
          initialPrimarySize={65}
          minPrimarySize={35}
          maxPrimarySize={80}
          separatorLabel="Resize expression and classification panes"
        />
      ) : expressionPanel || classificationPanel}
    </div>
  )
}
