import {
  objectMetrics
} from "@/components/detail/VariantKnowledgebase"
import { displayValue } from "@/lib/detail-formatters"


export function variantLocation(variant: any) {
  if (!variant) return "-"
  const ref = Array.isArray(variant.REF) ? variant.REF.join(",") : variant.REF
  const alt = Array.isArray(variant.ALT) ? variant.ALT.join(",") : variant.ALT
  return `${variant.CHROM}:${variant.POS} ${displayValue(ref)}>${displayValue(alt)}`
}

export function clinicalSig(csq: any, variant: any) {
  return csq?.CLIN_SIG || variant?.INFO?.CLNSIG || variant?.INFO?.CLIN_SIG
}

export function ponRows(value: unknown) {
  if (!value || typeof value !== "object") return []
  return Object.entries(value)
    .flatMap(([caller, callerValue]: [string, unknown]) => {
      if (!callerValue || typeof callerValue !== "object" || Array.isArray(callerValue)) return []
      const evidence = callerValue as Record<string, unknown>
      const num = displayValue(evidence.NUM)
      const ratio = /^(\d+)\s*\/\s*(\d+)$/.exec(num)
      const detected = ratio && Number(ratio[2]) > 0 && Number(ratio[1]) <= Number(ratio[2])
        ? `${num} (${(100 * Number(ratio[1]) / Number(ratio[2])).toFixed(1)}%)`
        : num
      const values = (Array.isArray(evidence.VAFS) ? evidence.VAFS : String(evidence.VAFS ?? "").split(","))
        .map((value) => String(value).trim())
        .filter(Boolean)
        .slice(-20)
        .map((value) => {
          const frequency = Number(value)
          return Number.isFinite(frequency) && frequency >= 0 && frequency <= 1
            ? `${(100 * frequency).toFixed(1)}%`
            : "-"
        })
      return [{ caller, detected, frequencies: values.join(", ") || "-" }]
    })
}

export function brcaExchangeMetrics(record: any) {
  if (!record) {
    return [{ label: "Status", value: "No local BRCA Exchange evidence is available." }]
  }

  const grch38 = record.chr38 && record.pos38
    ? `${record.chr38}:${record.pos38} ${record.ref38 || ""}>${record.alt38 || ""}`.trim()
    : "-"
  return [
    ...objectMetrics(record, [
      { label: "Clinical significance", keys: ["enigma_clinsig"] },
      { label: "References", keys: ["enigma_clinsig_refs"] },
      { label: "Comment", keys: ["enigma_clinsig_comment"] },
    ]),
    { label: "GRCh38", value: grch38, monospace: grch38 !== "-" },
  ]
}
