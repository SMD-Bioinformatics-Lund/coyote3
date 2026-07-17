export type FilterSection = "snv" | "cnv" | "coverage" | "fusion"

export function sampleFilePath(sample: any, key: string): string | undefined {
  const file = sample?.files?.[key]
  if (typeof file === "string") return file || undefined
  if (file?.path) return String(file.path)
  const legacy = sample?.[key]
  return legacy ? String(legacy) : undefined
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
  return sample?.subpanel_id || sample?.subpanel || undefined
}

export function sampleReported(sample: any): boolean {
  return Boolean(sample?.reported || sample?.latest_report_id || sample?.report_num)
}

export function sampleFilterSection(sampleOrFilters: any, section: FilterSection): Record<string, any> {
  const filters = sampleOrFilters?.filters ?? sampleOrFilters ?? {}
  const direct = filters?.[section]
  if (direct && typeof direct === "object" && !Array.isArray(direct)) return { ...direct }
  if (section === "snv") {
    return pick(filters, [
      "max_freq",
      "min_freq",
      "max_control_freq",
      "max_popfreq",
      "min_depth",
      "min_alt_reads",
      "vep_consequences",
      "snvlists",
      "adhoc_genes",
    ])
  }
  if (section === "cnv") {
    return pick(filters, [
      "min_cnv_size",
      "max_cnv_size",
      "cnv_loss_cutoff",
      "cnv_gain_cutoff",
      "cnveffects",
      "cnvlists",
      "adhoc_genes",
    ])
  }
  if (section === "coverage") return pick(filters, ["warn_cov", "error_cov"])
  return pick(filters, [
    "fusion_callers",
    "fusion_effects",
    "fusionlists",
    "min_spanning_pairs",
    "min_spanning_reads",
    "adhoc_genes",
  ])
}

export function mergeSampleFilterSection(sample: any, section: FilterSection, values: Record<string, any>) {
  const current = sample?.filters && typeof sample.filters === "object" ? { ...sample.filters } : {}
  current[section] = { ...values }
  return current
}

export function activeFilterSectionForTab(activeTab: string): FilterSection | null {
  if (activeTab === "snvs") return "snv"
  if (activeTab === "cnvs") return "cnv"
  if (activeTab === "coverage") return "coverage"
  if (activeTab === "fusions") return "fusion"
  return null
}

function pick(source: any, keys: string[]) {
  const out: Record<string, any> = {}
  for (const key of keys) {
    if (source?.[key] !== undefined) out[key] = source[key]
  }
  return out
}
