export type OncoKbGeneRecord = {
  name?: string
  gene?: string
  description?: string
  geneSummary?: string
  gene_summary?: string
  summary?: string
  is_oncokb?: boolean
}

export function isOncoKbGene(gene: string | undefined, oncokbGenes?: string[] | Record<string, OncoKbGeneRecord>) {
  if (!gene) return false
  if (Array.isArray(oncokbGenes)) return oncokbGenes.includes(gene)
  return Boolean(oncokbGenes?.[gene])
}
