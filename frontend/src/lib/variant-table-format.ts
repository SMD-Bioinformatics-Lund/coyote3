export type HotspotEntry = { source: string; identifiers: string[] }

const COSMIC_IDENTIFIER = /^COS([VMN])(\d+)$/i

function compactHotspotIdentifiers(values: Iterable<string>) {
  const identifiers = Array.from(values)
  const cosmic = identifiers
    .map((identifier) => ({ identifier, match: COSMIC_IDENTIFIER.exec(identifier) }))
    .filter((entry): entry is { identifier: string; match: RegExpExecArray } => Boolean(entry.match))
    .sort((left, right) => {
      const namespaceRank = { V: 3, M: 2, N: 1 } as const
      const namespaceDifference = namespaceRank[right.match[1].toUpperCase() as keyof typeof namespaceRank]
        - namespaceRank[left.match[1].toUpperCase() as keyof typeof namespaceRank]
      if (namespaceDifference) return namespaceDifference
      return Number(right.match[2]) - Number(left.match[2])
    })

  const nonCosmic = identifiers.filter((identifier) => !COSMIC_IDENTIFIER.test(identifier))
  return cosmic.length ? [...nonCosmic, cosmic[0].identifier] : nonCosmic
}

export function formatPopulationFrequency(value: unknown) {
  if (value === null || value === undefined || value === "") return "-"
  const frequency = Number(value)
  if (!Number.isFinite(frequency)) return "-"
  return (frequency * 100).toFixed(6).replace(/\.?0+$/, "")
}

export function variantHotspotEntries(variant: any): HotspotEntry[] {
  const entries = new Map<string, Set<string>>()
  const append = (sourceValue: unknown, identifiersValue: unknown = []) => {
    const source = String(sourceValue || "").trim()
    if (!source) return
    const identifiers = Array.isArray(identifiersValue) ? identifiersValue : [identifiersValue]
    const target = entries.get(source) || new Set<string>()
    identifiers.forEach((identifier) => {
      String(identifier || "").split(/[&|]/).forEach((part) => {
        const normalized = part.trim()
        if (normalized) target.add(normalized)
      })
    })
    entries.set(source, target)
  }

  const hotspotGroups = Array.isArray(variant?.hotspots) ? variant.hotspots : []
  hotspotGroups.forEach((group: unknown) => {
    if (!group || typeof group !== "object" || Array.isArray(group)) return
    Object.entries(group as Record<string, unknown>).forEach(([source, identifiers]) => append(source, identifiers))
  })

  const hydratedHotspots = variant?.INFO?.HOTSPOT
  const hydratedValues = Array.isArray(hydratedHotspots) ? hydratedHotspots : [hydratedHotspots]
  hydratedValues.forEach((source) => append(source))

  return Array.from(entries, ([source, identifiers]) => ({
    source,
    identifiers: compactHotspotIdentifiers(identifiers),
  }))
}

export function hotspotExportValue(variant: any) {
  return variantHotspotEntries(variant)
    .map(({ source, identifiers }) => identifiers.length ? `${source}: ${identifiers.join(", ")}` : source)
    .join(" | ")
}
