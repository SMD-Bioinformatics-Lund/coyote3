export function matchedKnowledgebaseGenes(
  genes: Array<string | null | undefined>,
  records: Record<string, unknown> | null | undefined,
) {
  const recordMap = records || {}
  return Array.from(
    new Set(
      genes
        .map((gene) => String(gene || "").trim())
        .filter((gene) => gene && (recordMap[gene] || recordMap[gene.toUpperCase()])),
    ),
  )
}
