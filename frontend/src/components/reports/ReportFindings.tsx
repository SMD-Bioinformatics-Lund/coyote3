import { flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table"
import type { ColumnDef } from "@tanstack/react-table"
import { REPORT_SNAPSHOT_SECTIONS, isCompactReportBiomarker, type ReportSnapshotRow } from "./report-snapshot"
import { Fragment } from "react"

function measurements(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown> : {}
}

function measurementText(value: unknown): string {
  return typeof value === "number" || (typeof value === "string" && value !== "")
    ? String(value) : "-"
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
      .filter(([field]) => !knownFields.includes(field)
        && field !== "clinical_assessment" && field !== "assessment_history"))
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
            <dd className="type-page-title type-numeric">{percentage}{percentage !== "-" && "%"}</dd>
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
    <dl className="report-measurements type-body-sm">
      {knownGroups.filter((key) => result[key] != null).map((key) => <Fragment key={key}>
        <dt>{key} clinical assessment</dt>
        <dd>{measurementText(measurements(measurements(result[key]).clinical_assessment).value)
          .replace(/^-$/, "Not assessed")}</dd>
      </Fragment>)}
    </dl>
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
    <dd>{value === null || value === undefined || value === "" ? "-" : String(value)}</dd>
  </Fragment>
}

/** Present preserved findings in compact tables and producer-reported biomarker summaries. */
export function ReportFindings({ rows, columns, analysisType }: {
  rows: ReportSnapshotRow[]
  columns: ColumnDef<ReportSnapshotRow>[]
  analysisType?: string
}) {
  const table = useReactTable({ data: rows, columns, getCoreRowModel: getCoreRowModel() })
  if (analysisType && isCompactReportBiomarker(analysisType)) {
    return <div className="divide-y divide-border/60">
      {table.getRowModel().rows.map((row) => <div key={row.id} className="py-2 first:pt-0">
        <BiomarkerSummary type={analysisType} result={measurements(row.original.result)} />
      </div>)}
    </div>
  }
  const label = REPORT_SNAPSHOT_SECTIONS.find((section) => section.type === analysisType)?.label
    ?? "Included findings"
  return <div className="report-findings-table-scroll" role="region" aria-label={`${label} table`} tabIndex={0}>
    <table className="report-findings-table type-body-sm" aria-label={label}>
      <thead>
        {table.getHeaderGroups().map((group) => <tr key={group.id}>
          {group.headers.map((header) => <th key={header.id} scope="col" data-column={header.column.id} className="type-meta">
            {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
          </th>)}
        </tr>)}
      </thead>
      <tbody>
        {table.getRowModel().rows.map((row) => <tr key={row.id}>
          {row.original.result && typeof row.original.result === "object"
            ? <td colSpan={row.getVisibleCells().length}>
              <dl className="report-measurements type-body-sm"><MeasurementValues value={row.original.result} /></dl>
            </td>
            : row.getVisibleCells().map((cell) => <td key={cell.id} className="report-finding-value">
              {flexRender(cell.column.columnDef.cell, cell.getContext())}
            </td>)}
        </tr>)}
      </tbody>
    </table>
  </div>
}
