import type { ColumnDef } from "@tanstack/react-table"

import { TierBadge } from "@/lib/variant-ui"

export type ReportType = "dna" | "rna"
export type ReportSnapshotRow = Record<string, any>

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-"
  return typeof value === "string" ? value : JSON.stringify(value)
}

function renderClippedValue(value: unknown, className = "max-w-[34rem]") {
  return (
    <span className={`type-table-cell block truncate ${className}`} title={String(value || "")}>
      {String(value || "-")}
    </span>
  )
}

const snvColumns: ColumnDef<ReportSnapshotRow, any>[] = [
  {
    id: "gene",
    header: "Gene",
    accessorFn: (row) => row.gene || row.gene1 || row.hgnc_symbol || "-",
    cell: ({ row }) => <span className="font-semibold text-link">{String(row.getValue("gene"))}</span>,
  },
  {
    id: "variant",
    header: "Variant",
    accessorFn: (row) => row.variant || row.hgvs || row.variant_name || row.breakpoint || "-",
    cell: ({ row }) => renderClippedValue(row.getValue("variant")),
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
    cell: ({ row }) => renderClippedValue(row.getValue("text"), "max-w-[30rem]"),
  },
]

const fusionColumns: ColumnDef<ReportSnapshotRow, any>[] = [
  {
    id: "fusion",
    header: "Fusion",
    accessorFn: (row) => row.fusion ?? "-",
    cell: ({ row }) => <span className="font-semibold text-link">{String(row.getValue("fusion"))}</span>,
  },
  {
    id: "breakpoints",
    header: "Breakpoints",
    accessorFn: (row) => [row.breakpoint_1, row.breakpoint_2].filter(Boolean).join(" / ") || "-",
  },
  { id: "effect", header: "Effect", accessorFn: (row) => row.effect ?? "-" },
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
    cell: ({ row }) => renderClippedValue(row.getValue("text")),
  },
]

const cnvColumns: ColumnDef<ReportSnapshotRow, any>[] = [
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

const translocationColumns: ColumnDef<ReportSnapshotRow, any>[] = [
  { id: "gene1", header: "Gene 1", accessorFn: (row) => row.gene1 || row.gene_1 || "-" },
  { id: "gene2", header: "Gene 2", accessorFn: (row) => row.gene2 || row.gene_2 || "-" },
  { id: "breakpoint", header: "Breakpoint", accessorFn: (row) => row.breakpoint || "-" },
  { id: "hgvsc", header: "HGVS.c", accessorFn: (row) => row.hgvsc || "-" },
  { id: "hgvsp", header: "HGVS.p", accessorFn: (row) => row.hgvsp || "-" },
  { id: "effect", header: "Effect", accessorFn: (row) => row.effect || "-" },
]

const biomarkerColumns: ColumnDef<ReportSnapshotRow, any>[] = [
  { id: "biomarker", header: "Biomarker", accessorFn: (row) => row.biomarker || "-" },
  {
    id: "result",
    header: "Result",
    accessorFn: (row) => formatValue(row.result),
    cell: ({ row }) => renderClippedValue(row.getValue("result"), "max-w-[54rem]"),
  },
]

const pgxColumns: ColumnDef<ReportSnapshotRow, any>[] = [
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
          ? `Activity score: ${formatValue(row.activity_score)}`
          : null,
        row.recommendation ? `Recommendation: ${formatValue(row.recommendation)}` : null,
      ]
        .filter(Boolean)
        .join("; ") || "-",
    cell: ({ row }) => renderClippedValue(row.getValue("details"), "max-w-[54rem]"),
  },
]

export const REPORT_SNAPSHOT_SECTIONS = [
  { type: "SNV", label: "Small variants", columns: snvColumns },
  { type: "CNV", label: "Copy-number variants", columns: cnvColumns },
  { type: "TRANSLOCATION", label: "DNA fusions and translocations", columns: translocationColumns },
  { type: "FUSION", label: "RNA fusions", columns: fusionColumns },
  { type: "BIOMARKER", label: "Biomarkers", columns: biomarkerColumns },
  { type: "PGX", label: "Pharmacogenomics", columns: pgxColumns },
] as const

export function reportSnapshotAnalysisType(row: ReportSnapshotRow, reportType: ReportType): string {
  const explicitType = String(row.analysis_type || "").trim().toUpperCase()
  if (explicitType) return explicitType
  return reportType === "rna" ? "FUSION" : "SNV"
}
