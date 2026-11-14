/** Software-owned UI constants. Centre and deployment settings are not defined here. */
import { NOMENCLATURE_METADATA } from "@/lib/defaults"

export { DEFAULT_ENVIRONMENT, NOMENCLATURE_METADATA } from "@/lib/defaults"

export type NomenclatureCode = keyof typeof NOMENCLATURE_METADATA

export const NOMENCLATURE_CODES = Object.keys(NOMENCLATURE_METADATA) as NomenclatureCode[]

export function nomenclatureLabel(value: unknown): string {
  const code = String(value || "").trim().toLowerCase()
  if (!code) return "-"
  return NOMENCLATURE_METADATA[code as NomenclatureCode]?.label || String(value)
}
