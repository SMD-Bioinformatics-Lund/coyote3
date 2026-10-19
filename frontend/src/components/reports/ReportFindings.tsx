import { flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table"
import type { ColumnDef } from "@tanstack/react-table"
import { isCompactReportBiomarker, type ReportSnapshotRow } from "./report-snapshot"
import { Fragment } from "react"

function measurements(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown> : {}
}

function measurementText(value: unknown): string {
  return typeof value === "number" || (typeof value === "string" && value !== "")
    ? String(value) : "—"
}

/** Show producer-reported values without deriving scores or interpreting thresholds. */
function BiomarkerSummary({ type, result }: {
  type: "HRD" | "MSI" | "TMB"
  result: Record<string, unknown>
}) {
  let content
  const knownFields = type === "HRD" ? ["tai", "hrd", "lst", "sum"]
    : type === "MSI" ? ["tot", "som", "per"] : ["value", "unit"]
  const knownGroups = type === "MSI" ? ["MSIS", "MSIP"] : [type]
  const extraFields = Object.fromEntries(Object.entries(result).flatMap(([key, value]) => {
    if (!knownGroups.includes(key)) return [[key, value]]
    const extra = Object.fromEntries(Object.entries(measurements(value))
      .filter(([field]) => !knownFields.includes(field)))
    return Object.keys(extra).length ? [[key, extra]] : []
  }))

  if (type === "HRD") {
    const hrd = measurements(result.HRD)
    content = <>
      <dl className="report-biomarker-score">
        <dt className="type-meta text-muted-foreground">Total score</dt>
        <dd className="type-page-title type-numeric">{measurementText(hrd.sum)}</dd>
      </dl>
      <dl className="report-biomarker-components type-body-sm">
        {(["tai", "hrd", "lst"] as const).map((key) => <div key={key}>
          <dt className="type-meta text-muted-foreground">{key.toUpperCase()}</dt>
          <dd className="type-numeric font-medium">{measurementText(hrd[key])}</dd>
        </div>)}
      </dl>
    </>
  } else if (type === "MSI") {
    const modes = ([ ["MSIS", "Single"], ["MSIP", "Paired"] ] as const)
      .filter(([key]) => result[key] !== null && result[key] !== undefined)
    content = modes.length ? <div className="report-biomarker-msi">
      {modes.map(([key, label]) => {
        const msi = measurements(result[key])
        const percentage = measurementText(msi.per)
        return <div key={key} role="group" aria-label={`${label} MSI`}>
          <dl className="report-biomarker-score">
            <dt className="type-meta text-muted-foreground">{label}</dt>
            <dd className="type-page-title type-numeric">{percentage}{percentage !== "—" && "%"}</dd>
          </dl>
          <p className="type-meta text-muted-foreground">
            <span className="block type-numeric text-foreground">{measurementText(msi.som)} / {measurementText(msi.tot)}</span>
            <span>unstable sites</span>
          </p>
        </div>
      })}
    </div> : <p className="type-body-sm text-muted-foreground">No MSI measurements recorded.</p>
  } else {
    const tmb = measurements(result.TMB)
    content = <dl className="report-biomarker-score">
      <dt className="type-meta text-muted-foreground">Mutational burden</dt>
      <dd className="flex flex-wrap items-baseline gap-2">
        <span className="type-page-title type-numeric">{measurementText(tmb.value)}</span>
        <span className="type-body-sm text-muted-foreground">{measurementText(tmb.unit)}</span>
      </dd>
    </dl>
  }

  return <div className="space-y-3 py-1">
    {content}
    {Object.keys(extraFields).length > 0 && <details className="type-meta">
      <summary className="cursor-pointer text-muted-foreground">Additional measurements</summary>
      <dl className="report-measurements mt-3"><MeasurementValues value={extraFields} /></dl>
    </details>}
  </div>
}

const measurementLabels: Record<string, string> = {
  tai: "TAI", hrd: "HRD", lst: "LST", sum: "Total score", tot: "Total sites",
  som: "Unstable sites", per: "Percentage", MSIS: "MSI single", MSIP: "MSI paired",
  value: "Value", unit: "Unit",
}

function MeasurementValues({ value, path = [] }: { value: unknown; path?: string[] }) {
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    return <>{Object.entries(value).map(([key, entry]) => (
      <MeasurementValues key={key} value={entry} path={[...path, key]} />
    ))}</>
  }
  // A single wrapper names the biomarker already shown by the section heading.
  const labels = path.length === 2 && ["HRD", "TMB"].includes(path[0])
    ? path.slice(1) : path
  const label = labels.map((key) => measurementLabels[key] ?? key.replaceAll("_", " ")).join(" / ")
  return <Fragment>
    <dt>{label}</dt>
    <dd>{value === null || value === undefined || value === "" ? "—" : String(value)}</dd>
  </Fragment>
}

/** Present preserved snapshot fields as readable records beside the document. */
export function ReportFindings({ rows, columns, analysisType }: {
  rows: ReportSnapshotRow[]
  columns: ColumnDef<ReportSnapshotRow>[]
  analysisType?: string
}) {
  const table = useReactTable({ data: rows, columns, getCoreRowModel: getCoreRowModel() })
  return <div className="divide-y divide-border/60">
    {table.getRowModel().rows.map((row) => (
      analysisType && isCompactReportBiomarker(analysisType)
        ? <div key={row.id} className="py-3 first:pt-0">
          <BiomarkerSummary type={analysisType} result={measurements(row.original.result)} />
        </div>
        : row.original.result && typeof row.original.result === "object"
        ? <dl key={row.id} className="report-measurements type-body-sm py-2">
          <MeasurementValues value={row.original.result} />
        </dl>
        :
      <dl key={row.id} className="space-y-3 py-4 first:pt-2">
        {row.getVisibleCells().map((cell) => (
          <div key={cell.id} className="space-y-1">
            <dt className="type-meta text-muted-foreground">
              {typeof cell.column.columnDef.header === "string" ? cell.column.columnDef.header : cell.column.id}
            </dt>
            <dd className="report-finding-value type-body-sm text-foreground">
              {flexRender(cell.column.columnDef.cell, cell.getContext())}
            </dd>
          </div>
        ))}
      </dl>
    ))}
  </div>
}
