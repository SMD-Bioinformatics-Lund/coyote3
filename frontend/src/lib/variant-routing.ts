const TIERED_SEARCH_MODES = new Set([
  "variant",
  "gene",
  "hgvsp",
  "hgvsc",
  "genomic",
  "transcript",
  "subpanel",
  "author",
  "annotation",
  "all",
])

export type TieredVariantSearchState = {
  search: string
  mode: string
  includeText: boolean
  assays: string[]
}

export function tieredVariantSearchPath(gene: unknown, assayGroup?: unknown) {
  const params = new URLSearchParams()
  const normalizedGene = String(gene || "").trim()
  const normalizedAssayGroup = String(assayGroup || "").trim()

  if (normalizedGene) {
    params.set("search_str", normalizedGene)
    params.set("search_mode", "gene")
  }
  if (normalizedAssayGroup) params.append("assays", normalizedAssayGroup)

  const query = params.toString()
  return `/variants/search${query ? `?${query}` : ""}`
}

export function tieredVariantSearchState(params: URLSearchParams): TieredVariantSearchState {
  const search = String(params.get("search_str") || "").trim()
  const requestedMode = String(params.get("search_mode") || "").trim().toLowerCase()
  const mode = TIERED_SEARCH_MODES.has(requestedMode) ? requestedMode : search ? "gene" : "variant"
  const assays = Array.from(
    new Set(params.getAll("assays").map((value) => value.trim()).filter(Boolean)),
  )

  return {
    search,
    mode,
    includeText: params.get("include_annotation_text") === "true",
    assays,
  }
}
