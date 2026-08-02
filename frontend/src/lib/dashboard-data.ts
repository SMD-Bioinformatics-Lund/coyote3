export type PanelGeneChartRow = {
  aspId: string
  name: string
  Covered: number
  Germline: number
}

export function buildPanelGeneChartData(geneGroups: Record<string, any[]>): PanelGeneChartRow[] {
  return Object.values(geneGroups).flatMap((rows) =>
    (rows || []).map((assay: any) => ({
      aspId: String(assay.asp_id || "").trim(),
      name: assay.display_name || assay.asp_id || "Unnamed panel",
      Covered: Number(assay.covered_genes_count ?? assay.gene_count ?? 0),
      Germline: Number(assay.germline_genes_count ?? assay.germline_gene_count ?? 0),
    })),
  )
}

export function buildPanelAnalysisCapabilityData(rows: any[]) {
  return (rows || [])
    .map((row) => ({
      name: String(row.analysis_type || "").trim().toUpperCase(),
      Enabled: Number(row.enabled || 0),
      Reportable: Number(row.reportable || 0),
    }))
    .filter((row) => row.name)
    .sort((a, b) => b.Enabled - a.Enabled || a.name.localeCompare(b.name))
}
