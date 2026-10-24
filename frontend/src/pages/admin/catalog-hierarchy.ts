import type { Category, Modality } from "./catalog-types"

/** Resolve inherited editor choices; the API validates and resolves saved content independently. */
export function effectiveCatalogEntry(modality: Modality, key: string): Category {
  const path: Category[] = []
  const seen = new Set<string>()
  let current: string | null | undefined = key
  while (current && !seen.has(current)) {
    seen.add(current)
    const node: Category | undefined = modality.categories[current]
    if (!node) break
    path.unshift(node)
    current = node.parent_key
  }
  const fields = ["description", "subheading", "input_material", "sample_modes", "analysis",
    "report_sections", "clinical_indications", "tat", "limitations", "public_notes",
    "asp_id", "aspc_id", "aspc_ids", "diagnosis_id", "gene_lists", "no_gene_list"] as const
  let result: Category = modality
  for (const node of path) {
    const inherited = Object.fromEntries(fields.filter((field) => !node.clear_fields?.includes(field)
      && (node[field] == null || node[field] === "" || (Array.isArray(node[field]) && !node[field]?.length)
        || (typeof node[field] === "object" && !Object.keys(node[field] || {}).length)))
      .map((field) => [field, result[field]]))
    result = { ...node, ...inherited }
    if (!node.gene_lists?.length && result.no_gene_list?.length) {
      result.gene_lists = result.gene_lists?.flatMap((list) => {
        const analysis = list.analysis?.filter((item) => !result.no_gene_list?.includes(item)) || []
        return analysis.length ? [{ ...list, analysis }] : []
      })
    }
  }
  return result
}
