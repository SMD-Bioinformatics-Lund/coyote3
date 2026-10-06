import type { SampleDataSegment } from "./sample-data-status"
import { FILE_ANALYSIS_LABELS } from "@/lib/sample-artifact-ui"
import type { SortingState } from "@tanstack/react-table"


export type SampleTab = "live" | "reported"

export const DEFAULT_LIVE_SORTING: SortingState = [{ id: "added", desc: true }]

export const DEFAULT_REPORTED_SORTING: SortingState = [{ id: "latest_reported", desc: true }]

export const BOOLEAN_ANALYSIS_LABELS: Record<string, string> = {
  cov: "Cov",
  hrd: "HRD",
  msi: "MSI",
  tmb: "TMB",
  qc: "QC",
  classification: "Classification",
  rna_expr: "Expr",
  rna_expression: "Expr",
  rna_class: "Class",
  rna_classification: "Class",
  rna_qc: "QC",
}

export const STANDARD_DATA_EXPORT_COLUMNS = [
  { key: "snvs", aliases: ["snvs"] },
  { key: "cnvs", aliases: ["cnvs"] },
  { key: "fusions", aliases: ["fusions"] },
  { key: "transloc", aliases: ["transloc", "translocations"] },
  { key: "cov", aliases: ["cov"] },
  { key: "hrd", aliases: ["hrd"] },
  { key: "msi", aliases: ["msi"] },
  { key: "tmb", aliases: ["tmb"] },
  { key: "pgx", aliases: ["pgx"] },
  { key: "rna_expr", aliases: ["rna_expr", "rna_expression"] },
  { key: "rna_class", aliases: ["rna_class", "rna_classification"] },
  { key: "rna_qc", aliases: ["rna_qc", "qc"] },
] as const

export const DATA_EXPORT_LABELS: Record<string, string> = {
  snvs: "SNV count",
  cnvs: "CNV count",
  fusions: "Fusion count",
  transloc: "Translocation count",
  translocations: "Translocation count",
  cov: "Coverage loaded",
  hrd: "HRD loaded",
  msi: "MSI loaded",
  tmb: "TMB loaded",
  pgx: "PGx loaded",
  rna_expr: "Expression loaded",
  rna_expression: "Expression loaded",
  rna_class: "Classification loaded",
  rna_classification: "Classification loaded",
  rna_qc: "QC loaded",
  qc: "QC loaded",
}

export function exportScalar(value: unknown) {
  if (typeof value === "boolean") return value ? "Yes" : "No"
  return value ?? ""
}

export function firstDefinedValue(record: Record<string, unknown>, keys: readonly string[]) {
  for (const key of keys) {
    if (record[key] !== undefined) return record[key]
  }
  return undefined
}

export function countBadges(sample: { data_counts?: Record<string, number | boolean>; missing_expected_files?: string[] }): SampleDataSegment[] {
  const counts = sample?.data_counts || {}
  const missing = new Set(sample?.missing_expected_files || [])
  const translocations = counts.transloc ?? counts.translocations
  const numericBadges = [
    counts.snvs !== undefined && !missing.has("vcf_files") ? { label: "SNV", value: Number(counts.snvs).toLocaleString("en-US"), className: "matte-badge-pass" } : null,
    counts.cnvs !== undefined && !missing.has("cnv") ? { label: "CNV", value: Number(counts.cnvs).toLocaleString("en-US"), className: "matte-badge-pass" } : null,
    counts.fusions !== undefined && !missing.has("fusion_files") ? { label: "Fusion", value: Number(counts.fusions).toLocaleString("en-US"), className: "matte-badge-pass" } : null,
    translocations !== undefined && !missing.has("transloc") ? { label: "SV", value: Number(translocations).toLocaleString("en-US"), className: "matte-badge-pass" } : null,
  ].filter((item): item is NonNullable<typeof item> => item !== null)
  const fileForCount: Record<string, string> = {
    rna_expr: "expression_path", rna_expression: "expression_path",
    rna_class: "classification_path", rna_classification: "classification_path", rna_qc: "qc",
  }
  const booleanBadges = Object.entries(counts)
    .filter(([key, value]) => (typeof value === "boolean" || ["hrd", "msi", "tmb"].includes(key)) && key !== "biomarkers" && !missing.has(fileForCount[key] || key))
    .map(([key, value]) => ({
      label: BOOLEAN_ANALYSIS_LABELS[key] || key.replaceAll("_", " ").toUpperCase(),
      className: value ? "matte-badge-pass" : "matte-badge-fail",
    }))

  const missingBadges = (sample?.missing_expected_files || []).map((key: string) => ({
    label: key === "transloc" ? "Transloc" : FILE_ANALYSIS_LABELS[key] || key,
    title: `${FILE_ANALYSIS_LABELS[key] || key} not available`,
    className: "matte-badge-fail",
  }))
  return [...numericBadges, ...booleanBadges, ...missingBadges]
}

export function positivePage(value: string | null) {
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1
}

export function resetSamplePagination(params: URLSearchParams) {
  params.delete("live_page")
  params.delete("reported_page")
}

export function sampleFindingTotal(sample: any) {
  const counts = sample?.data_counts || {}
  return (
    Number(counts.snvs || 0) +
    Number(counts.cnvs || 0) +
    Number(counts.fusions || 0) +
    Number(counts.transloc ?? counts.translocations ?? 0)
  )
}
