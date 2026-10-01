

export function asArray(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((item) => String(item ?? "").trim()).filter(Boolean)
  if (value === null || value === undefined || value === "") return []
  return [String(value)]
}

export function formatScalar(value: unknown) {
  const values = asArray(value)
  return values.length ? values.join(", ") : "-"
}

export const FIRST_CLASS_CATALOG_FIELDS = new Set([
  "analysis",
  "asp",
  "asp_id",
  "aspc_id",
  "aspc_ids",
  "catalog_id",
  "clinical_indications",
  "description",
  "gene_lists",
  "input_material",
  "label",
  "limitations",
  "public_notes",
  "report_sections",
  "sample_modes",
  "sample_query",
  "subheading",
  "subpanel_id",
  "tat",
  "title",
])
