/** Software-owned UI constants. Centre and deployment settings are not defined here. */
export const DEFAULT_ENVIRONMENT = "production" as const

export const NOMENCLATURE_METADATA = {
  p: { label: "Protein (p)" },
  c: { label: "cDNA (c)" },
  g: { label: "Genomic (g)" },
  cn: { label: "Copy number (cn)" },
  f: { label: "Fusion (f)" },
  t: { label: "Translocation (t)" },
} as const

export type NomenclatureCode = keyof typeof NOMENCLATURE_METADATA

export const NOMENCLATURE_CODES = Object.keys(NOMENCLATURE_METADATA) as NomenclatureCode[]

export function nomenclatureLabel(value: unknown): string {
  const code = String(value || "").trim().toLowerCase()
  if (!code) return "-"
  return NOMENCLATURE_METADATA[code as NomenclatureCode]?.label || String(value)
}
