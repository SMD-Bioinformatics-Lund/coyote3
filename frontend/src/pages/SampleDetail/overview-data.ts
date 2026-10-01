import { sampleFilterSection } from "@/lib/sample-shape"


export function displayValue(value: unknown) {
  if (value === undefined || value === null || value === "") return "-"
  if (Array.isArray(value)) return value.length ? value.join(", ") : "None"
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(4)))
  return String(value)
}

export function formatFileSize(value: unknown) {
  const size = Number(value)
  if (!Number.isFinite(size) || size < 0) return null
  const units = ["B", "KB", "MB", "GB", "TB"]
  let scaled = size
  let unitIndex = 0
  while (scaled >= 1024 && unitIndex < units.length - 1) {
    scaled /= 1024
    unitIndex += 1
  }
  const formatted = unitIndex === 0 || scaled >= 10 ? scaled.toFixed(0) : scaled.toFixed(1)
  return `${formatted} ${units[unitIndex]}`
}

export function numericBiomarkerValue(value: unknown) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

export function formatPurityPercentage(value: unknown) {
  const purity = numericBiomarkerValue(value)
  if (purity === null) return null
  const percentage = purity >= 0 && purity <= 1 ? purity * 100 : purity
  return `${Number(percentage.toFixed(2))}%`
}

export function selectedPanelEntriesFromContext(context: any) {
  const selected = context?.selected_gene_panels
  if (!selected || typeof selected !== "object") return []
  return Object.entries(selected).flatMap(([target, raw]: [string, any]) => {
    const lists = Array.isArray(raw?.lists) ? raw.lists : []
    return lists.map((entry: any) => ({
      ...entry,
      target: String(target).toUpperCase(),
    }))
  })
}

export function selectedPanelEntriesFromFilters(context: any, sample: any) {
  const sections = [
    {
      target: "SNV",
      ids: sampleFilterSection(sample || context?.sample, "snv", "somatic")?.snvlists,
      options: context?.snv_genelist_options,
    },
    {
      target: "CNV",
      ids: sampleFilterSection(sample || context?.sample, "cnv", "somatic")?.cnvlists,
      options: context?.cnvlist_options,
    },
    {
      target: "FUSION",
      ids: sampleFilterSection(sample || context?.sample, "fusion", "somatic")?.fusionlists,
      options: context?.fusionlist_options,
    },
    {
      target: "TRANSLOCATION",
      ids: sampleFilterSection(sample || context?.sample, "translocation", "somatic")?.fusionlists,
      options: context?.fusionlist_options,
    },
  ]
  return sections.flatMap((section) => {
    const ids = Array.isArray(section.ids) ? section.ids : []
    const options = Array.isArray(section.options) ? section.options : []
    return ids.map((id: string) => {
      const option = options.find((item: any) => String(item?.id || item?.isgl_id || item?._id) === String(id))
      return {
        id: String(id),
        name: option?.display_name || option?.name || option?.label || String(id),
        target: section.target,
        adhoc: Boolean(option?.adhoc),
        is_active: true,
        gene_count: Number(option?.gene_count || 0),
        covered_count: Number(option?.gene_count || 0),
        uncovered_count: 0,
        genes: [],
        covered: [],
        uncovered: [],
      }
    })
  })
}

export function normalizePanelEntries(context: any, sample: any) {
  const richEntries = selectedPanelEntriesFromContext(context)
  if (richEntries.length) return richEntries
  return selectedPanelEntriesFromFilters(context, sample)
}

export function fileItems(context?: any) {
  return context?.sample_expected_files || []
}

export function reportItems(sample: any) {
  const reports = sample?.reports || sample?.report_files || []
  if (Array.isArray(reports)) return reports
  if (reports && typeof reports === "object") return Object.values(reports)
  return []
}

export function configuredAnalysisSections(sample: any, context?: any) {
  const sections = context?.analysis_sections || context?.aspc?.analysis_types || sample?.analysis_sections || []
  return new Set((Array.isArray(sections) ? sections : []).map((item: unknown) => String(item).toLowerCase()))
}

export type OverviewFilterGroup = {
  key: string
  label: string
  rows: Array<[string, unknown]>
}

export function hasConfiguredAnalysis(configured: Set<string>, ...keys: string[]) {
  return keys.some((key) => configured.has(key))
}

export function overviewFilterGroups(sample: any, context?: any): OverviewFilterGroup[] {
  const configured = configuredAnalysisSections(sample, context)
  const omics = String(sample?.omics_layer || "").toLowerCase()
  const include = (...keys: string[]) => configured.size === 0 || hasConfiguredAnalysis(configured, ...keys)

  if (omics === "rna") {
    if (!include("fusion", "fusions")) return []
    const fusion = sampleFilterSection(sample, "fusion")
    return [{
      key: "fusion",
      label: "Fusion filters",
      rows: [
        ["Callers", fusion.fusion_callers],
        ["Effects", fusion.fusion_effects],
        ["Gene lists", fusion.fusionlists],
        ["Minimum spanning pairs", fusion.min_spanning_pairs],
        ["Minimum spanning reads", fusion.min_spanning_reads],
      ],
    }]
  }

  if (omics !== "dna") return []
  const groups: OverviewFilterGroup[] = []
  if (include("snv", "snvs", "small_variant", "small_variants")) {
    const snv = sampleFilterSection(sample, "snv")
    groups.push({ key: "snv", label: "SNV filters", rows: [
      ["Minimum depth", snv.min_depth],
      ["Minimum alternate reads", snv.min_alt_reads],
      ["Minimum VAF", snv.min_freq],
      ["Maximum VAF", snv.max_freq],
      ["Maximum control VAF", snv.max_control_freq],
      ["Maximum population frequency", snv.max_popfreq],
      ["Consequences", snv.vep_consequences],
      ["Gene lists", snv.snvlists],
    ] })
  }
  if (include("cnv", "cnvs")) {
    const cnv = sampleFilterSection(sample, "cnv")
    groups.push({ key: "cnv", label: "CNV filters", rows: [
      ["Minimum size", cnv.min_cnv_size],
      ["Maximum size", cnv.max_cnv_size],
      ["Gain cutoff", cnv.cnv_gain_cutoff],
      ["Loss cutoff", cnv.cnv_loss_cutoff],
      ["Effects", cnv.cnveffects],
      ["Gene lists", cnv.cnvlists],
    ] })
  }
  if (include("coverage", "cov")) {
    const coverage = sampleFilterSection(sample, "coverage")
    groups.push({ key: "coverage", label: "Coverage filters", rows: [
      ["Warning threshold", coverage.warn_cov],
      ["Error threshold", coverage.error_cov],
    ] })
  }
  if (include("translocation", "translocations", "fusion", "fusions")) {
    const translocation = sampleFilterSection(sample, "translocation")
    groups.push({ key: "translocation", label: "DNA fusion / translocation filters", rows: [
      ["Gene lists", translocation.fusionlists],
    ] })
  }
  return groups
}

export function countValue(...values: unknown[]) {
  for (const value of values) {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed
  }
  return 0
}

export function analysisStatusItems(sample: any, context?: any) {
  const configured = configuredAnalysisSections(sample, context)
  const counts = sample?.data_counts || {}
  const raw = context?.analysis_counts_raw || {}
  const filtered = context?.analysis_counts_filtered || {}
  const files = sample?.files || sample
  const items = [
    {
      key: "snv",
      label: "Small variants",
      configuredKeys: ["snv", "small_variants", "small_variant"],
      raw: countValue(raw.snv, raw.snvs, counts.snv, counts.snvs),
      filtered: countValue(filtered.snv, filtered.snvs),
      present: countValue(raw.snv, raw.snvs, counts.snv, counts.snvs) > 0 || Boolean(files?.vcf_files),
    },
    {
      key: "cnv",
      label: "CNVs",
      configuredKeys: ["cnv", "cnvs"],
      raw: countValue(raw.cnv, raw.cnvs, counts.cnv, counts.cnvs),
      filtered: countValue(filtered.cnv, filtered.cnvs),
      present: countValue(raw.cnv, raw.cnvs, counts.cnv, counts.cnvs) > 0 || Boolean(files?.cnv),
    },
    {
      key: "fusion",
      label: "Fusions",
      configuredKeys: ["fusion", "fusions"],
      raw: countValue(raw.fusion, raw.fusions, counts.fusion, counts.fusions),
      filtered: countValue(filtered.fusion, filtered.fusions),
      present: countValue(raw.fusion, raw.fusions, counts.fusion, counts.fusions) > 0 || Boolean(files?.fusion || files?.fusion_vcf),
    },
    {
      key: "translocation",
      label: "Translocations",
      configuredKeys: ["translocation", "translocations"],
      raw: countValue(raw.translocation, raw.translocations, counts.transloc, counts.translocation, counts.translocations),
      filtered: countValue(filtered.translocation, filtered.translocations),
      present: counts.transloc !== undefined || counts.translocations !== undefined || countValue(raw.translocation, raw.translocations, counts.translocation) > 0 || Boolean(files?.transloc || files?.translocation),
    },
    {
      key: "coverage",
      label: "Coverage",
      configuredKeys: ["coverage", "cov"],
      raw: counts.cov === true ? 1 : countValue(raw.coverage, raw.cov, counts.coverage, counts.cov),
      filtered: countValue(filtered.coverage, filtered.cov),
      present: Boolean(counts.cov || files?.cov || files?.coverage),
    },
    {
      key: "biomarkers",
      label: "Biomarkers",
      configuredKeys: ["biomarker", "biomarkers"],
      raw: countValue(raw.biomarker, raw.biomarkers, counts.biomarker, counts.biomarkers),
      filtered: countValue(filtered.biomarker, filtered.biomarkers),
      present: countValue(raw.biomarker, raw.biomarkers, counts.biomarker, counts.biomarkers) > 0 || Boolean(files?.biomarkers),
    },
  ]
  const fileKeys: Record<string, string> = {
    snv: "vcf_files", cnv: "cnv", fusion: "fusion_files", translocation: "transloc",
    coverage: "cov", biomarkers: "biomarkers",
  }
  const missing = new Set(sample?.missing_expected_files || [])
  return items.filter((item) => configured.size === 0 || item.configuredKeys.some((key) => configured.has(key)))
    .map((item) => missing.has(fileKeys[item.key]) ? { ...item, present: false, raw: 0, filtered: 0 } : item)
}
