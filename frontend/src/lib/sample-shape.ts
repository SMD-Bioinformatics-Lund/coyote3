export type FilterSection = "snv" | "cnv" | "coverage" | "fusion"

export function sampleFilePath(sample: any, key: string): string | undefined {
  const file = sample?.files?.[key]
  if (typeof file === "string") return file || undefined
  if (file?.path) return String(file.path)
  return undefined
}

export function sampleFileName(sample: any, key: string): string | undefined {
  const path = sampleFilePath(sample, key)
  if (!path) return undefined
  return path.split(/[\\/]/).filter(Boolean).pop() || path
}

export function hasSampleFile(sample: any, key: string): boolean {
  return Boolean(sampleFilePath(sample, key))
}

export function sampleSubpanel(sample: any): string | undefined {
  return sample?.subpanel_id || undefined
}

export function sampleReported(sample: any): boolean {
  return Boolean(sample?.reported || sample?.latest_report_id)
}

export function sampleFilterSection(
  sampleOrFilters: any,
  section: FilterSection,
  intent = "somatic",
): Record<string, any> {
  const filters = sampleOrFilters?.filters ?? sampleOrFilters ?? {}
  const selected = filters?.[intent]?.[section]
  return selected && typeof selected === "object" && !Array.isArray(selected) ? { ...selected } : {}
}

export function mergeSampleFilterSection(
  sample: any,
  section: FilterSection,
  values: Record<string, any>,
  intent = "somatic",
) {
  const current = sample?.filters && typeof sample.filters === "object" ? { ...sample.filters } : {}
  current[intent] = { ...(current[intent] || {}), [section]: { ...values } }
  return current
}

export function activeFilterSectionForTab(activeTab: string): FilterSection | null {
  if (activeTab === "snvs" || activeTab === "germline-snvs") return "snv"
  if (activeTab === "cnvs") return "cnv"
  if (activeTab === "coverage") return "coverage"
  if (activeTab === "fusions") return "fusion"
  return null
}
