import { shortCount } from "@/lib/detail-formatters"


export function flattenCoverageTable(covTable: any) {
  return Object.entries(covTable || {}).flatMap(([gene, regions]: [string, any]) =>
    Object.entries(regions || {}).map(([region, row]: [string, any]) => ({
      gene,
      region,
      ...row,
    })),
  )
}

export function metric(value: unknown) {
  return shortCount(value, "-")
}

export function coord(row: any) {
  const chr = row?.chr || row?.chrom || "-"
  return `${chr}:${row?.start || "-"}-${row?.end || "-"}`
}

export function coverageNumber(row: any) {
  const value = Number(row?.cov)
  return Number.isFinite(value) ? value : Number.NaN
}

export function regionLength(row: any) {
  const start = Number(row?.start)
  const end = Number(row?.end)
  return Number.isFinite(start) && Number.isFinite(end) ? Math.max(0, end - start) : 0
}

export type CoverageFeatureKind = "Probe" | "Exon" | "CDS"

export type InspectedCoverageFeature = {
  kind: CoverageFeatureKind
  label: string
  coordinates: string
  coverage: number
  length: number
}
