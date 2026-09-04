export type KnowledgebaseRelease = {
  source: string
  release: string
  status: string
  published_at?: string | null
  records: number
  collections?: Array<{ name: string; records: number }>
}

export type KnowledgebaseStatusPayload = {
  releases?: KnowledgebaseRelease[]
  summary?: {
    installed_products?: number
    configured_services?: number
    available_products?: number
    total_records?: number
  }
}

const familyLabels: Record<string, string> = {
  brca_exchange: "BRCA Exchange",
  civic: "CIViC",
  clinpgx: "ClinPGx",
  hpa: "Human Protein Atlas",
  iarc_tp53: "IARC TP53",
  nci_tp53: "NCI TP53",
  oncokb: "OncoKB",
}

export function knowledgebaseSourceDetails(source: string) {
  if (source.startsWith("cosmic_")) {
    return { key: "cosmic", family: "COSMIC", product: source.slice(7).replaceAll("_", " ") }
  }
  const familyKey = Object.keys(familyLabels).find((key) => source.startsWith(key))
  const suffix = familyKey ? source.slice(familyKey.length).replace(/^_/, "") : ""
  return {
    key: familyKey || source,
    family: familyKey ? familyLabels[familyKey] : source.replaceAll("_", " "),
    product: suffix ? suffix.replaceAll("_", " ") : "reference",
  }
}

export type KnowledgebaseFamilySummary = {
  key: string
  family: string
  releases: string[]
  products: number
  records: number
  configured: boolean
}

export function summarizeKnowledgebaseFamilies(
  releases: KnowledgebaseRelease[],
): KnowledgebaseFamilySummary[] {
  const grouped = new Map<string, KnowledgebaseFamilySummary>()
  releases.forEach((release) => {
    const details = knowledgebaseSourceDetails(release.source)
    const current = grouped.get(details.key) || {
      key: details.key,
      family: details.family,
      releases: [],
      products: 0,
      records: 0,
      configured: false,
    }
    const version = String(release.release || "").trim()
    if (version && !current.releases.includes(version)) current.releases.push(version)
    current.products += 1
    current.records += Number(release.records || 0)
    current.configured ||= release.status === "configured"
    grouped.set(details.key, current)
  })
  return Array.from(grouped.values()).sort((left, right) => left.family.localeCompare(right.family))
}
