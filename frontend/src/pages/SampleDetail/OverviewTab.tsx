import { useState } from "react"
import type { ReactNode } from "react"
import { Link } from "react-router-dom"
import { AlertTriangle, ChevronDown, ChevronUp, RefreshCw } from "lucide-react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { fullDateTime, shortCount } from "@/lib/detail-formatters"
import {
  sampleArtifactCountLabel,
  sampleArtifactPresentation,
  sampleArtifactStatus,
} from "@/lib/sample-artifact-ui"
import { sampleFilterSection, sampleReported } from "@/lib/sample-shape"
import { apiPath } from "@/lib/runtime-paths"
import { SampleGeneSettings, SettingsCard } from "@/pages/SampleDetail/SampleGeneSettings"

function displayValue(value: unknown) {
  if (value === undefined || value === null || value === "") return "-"
  if (Array.isArray(value)) return value.length ? value.join(", ") : "None"
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(4)))
  return String(value)
}

function formatDate(value: unknown) {
  return fullDateTime(value)
}

function formatFileSize(value: unknown) {
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

function StatusPill({ children, tone = "muted" }: { children: ReactNode; tone?: "blue" | "green" | "yellow" | "red" | "muted" }) {
  const tones = {
    blue: "badge-info",
    green: "badge-success",
    yellow: "badge-warning",
    red: "badge-danger",
    muted: "badge-neutral",
  }
  return <span className={`type-badge inline-flex min-h-5 items-center rounded-md border px-2 py-0.5 ${tones[tone]}`}>{children}</span>
}

function numericBiomarkerValue(value: unknown) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

function formatPurityPercentage(value: unknown) {
  const purity = numericBiomarkerValue(value)
  if (purity === null) return null
  const percentage = purity >= 0 && purity <= 1 ? purity * 100 : purity
  return `${Number(percentage.toFixed(2))}%`
}

function selectedPanelEntriesFromContext(context: any) {
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

function selectedPanelEntriesFromFilters(context: any, sample: any) {
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

function normalizePanelEntries(context: any, sample: any) {
  const richEntries = selectedPanelEntriesFromContext(context)
  if (richEntries.length) return richEntries
  return selectedPanelEntriesFromFilters(context, sample)
}

export function PanelSummary({ sample, context }: { sample: any; context?: any }) {
  const [open, setOpen] = useState(false)
  const entries = normalizePanelEntries(context, sample)
  const isFusion = entries.length > 0 && entries.every((entry: any) => entry.target === "FUSION")
  const title = isFusion ? "Fusion List(s)" : "Gene Panel(s)"
  const emptyText = isFusion ? "No fusion list filters applied" : "No genelist filters applied"

  return (
    <section className="glass-panel overflow-hidden rounded-xl border border-border/80 bg-card/85 shadow-sm">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-3 border-b border-border/70 bg-muted/45 px-4 py-3 text-left transition-colors duration-100 hover:bg-primary/8 dark:bg-muted/25 dark:hover:bg-primary/12"
      >
        <div className="min-w-0">
          <h2 className="type-section-title text-foreground">{title}</h2>
          <p className="type-meta mt-0.5 text-muted-foreground">
            {entries.length ? `${entries.length} selected list${entries.length === 1 ? "" : "s"}` : emptyText}
          </p>
        </div>
        {open ? <ChevronUp className="h-4 w-4 shrink-0 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />}
      </button>

      <div className="px-4 py-3 text-sm font-medium">
        {entries.length ? (
          <div className="flex flex-wrap gap-1.5">
            {entries.map((raw: any) => {
              const covered = raw?.covered || []
              const genes = raw?.genes || []
              const name = raw?.name || raw?.id
              return (
                <span
                  key={`${raw?.target || "GENE"}-${raw?.id || name}`}
                  className={`inline-flex items-center gap-1 rounded-lg border px-2.5 py-1 text-xs font-bold shadow-sm transition-colors duration-100 ${
                    raw?.is_active === false
                      ? "border-warn/35 bg-warn/10 text-warn hover:bg-warn/10"
                      : raw?.adhoc
                        ? "border-primary/25 bg-primary/8 text-primary hover:bg-primary/8"
                        : "border-genelist/30 bg-genelist/10 text-genelist hover:bg-genelist/10"
                  }`}
                >
                  <span className="font-black uppercase">{raw?.target || "GENE"}</span>
                  <span className="text-foreground">{name}</span>
                  {raw?.adhoc ? <span className="rounded bg-primary/10 px-1 text-[10px] uppercase text-primary">Ad hoc</span> : null}
                  <span className="text-muted-foreground">
                    {Number(raw?.covered_count ?? covered.length)} / {Number(raw?.gene_count ?? genes.length)} covered
                  </span>
                </span>
              )
            })}
          </div>
        ) : (
          <span className="font-bold text-muted-foreground">{emptyText}</span>
        )}
      </div>

      {open && entries.length > 0 && (
        <div className="space-y-2 px-3 pb-3">
          {entries.map((raw: any) => {
            const covered = raw?.covered || []
            const genes = raw?.genes || []
            const uncovered = raw?.uncovered || []
            const name = raw?.name || raw?.id
            return (
              <div key={`${raw?.target || "GENE"}-${raw?.id || name}`} className="rounded-lg border border-border/80 bg-background/70 p-3 shadow-sm">
                <p className={raw?.is_active === false ? "text-sm font-bold text-warn" : "text-sm font-bold text-foreground"}>
                  <span className="uppercase text-muted-foreground">{raw?.target || "GENE"}</span>: {name} {raw?.adhoc ? <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] uppercase text-primary">Ad hoc</span> : null}
                  <span className="ml-2 text-muted-foreground">
                    {Number(raw?.covered_count ?? covered.length)} of {Number(raw?.gene_count ?? genes.length)} gene(s) covered
                  </span>
                  {raw?.is_active === false ? <span className="ml-2 text-warn">Inactive list, filter not applied.</span> : null}
                </p>
                {genes.length > 0 ? (
                  <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
                    {genes.map((gene: string) => (
                      <span
                        key={gene}
                        title={covered.includes(gene) ? "This gene is covered in the panel" : "This gene is not covered in the panel"}
                        className={covered.includes(gene) ? "rounded-md border border-pass/30 bg-pass/10 px-1.5 py-0.5 font-semibold text-pass" : "rounded-md border border-warn/35 bg-warn/10 px-1.5 py-0.5 font-semibold text-warn"}
                      >
                        {gene}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {Number(raw?.covered_count || 0)} covered gene(s)
                    {uncovered.length ? `, ${uncovered.length} outside assay coverage` : ""}
                  </p>
                )}
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}

function fileItems(context?: any) {
  return context?.sample_expected_files || []
}

function reportItems(sample: any) {
  const reports = sample?.reports || sample?.report_files || []
  if (Array.isArray(reports)) return reports
  if (reports && typeof reports === "object") return Object.values(reports)
  return []
}

function configuredAnalysisSections(sample: any, context?: any) {
  const sections = context?.analysis_sections || context?.aspc?.analysis_types || sample?.analysis_sections || []
  return new Set((Array.isArray(sections) ? sections : []).map((item: unknown) => String(item).toLowerCase()))
}

type OverviewFilterGroup = {
  key: string
  label: string
  rows: Array<[string, unknown]>
}

function hasConfiguredAnalysis(configured: Set<string>, ...keys: string[]) {
  return keys.some((key) => configured.has(key))
}

/** Build omics- and ASPC-aware filter groups for the sample overview. */
function overviewFilterGroups(sample: any, context?: any): OverviewFilterGroup[] {
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

function countValue(...values: unknown[]) {
  for (const value of values) {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed
  }
  return 0
}

function analysisStatusItems(sample: any, context?: any) {
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
      raw: countValue(raw.translocation, raw.translocations, counts.translocation, counts.translocations),
      filtered: countValue(filtered.translocation, filtered.translocations),
      present: countValue(raw.translocation, raw.translocations, counts.translocation, counts.translocations) > 0 || Boolean(files?.transloc || files?.translocation),
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
  return items.filter((item) => configured.size === 0 || item.configuredKeys.some((key) => configured.has(key)))
}

function AnalysisStatusStrip({ sample, context }: { sample: any; context?: any }) {
  const items = analysisStatusItems(sample, context)
  if (!items.length) return null

  return (
    <SettingsCard title="Analysis Status" tone="border-t-primary">
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {items.map((item) => {
          const tone = item.present ? "green" : "yellow"
          const filteredText = item.filtered > 0 ? `${shortCount(item.filtered)} filtered` : "filter on demand"
          const rawText = item.raw > 0 ? `${shortCount(item.raw)} raw` : item.present ? "file present" : "missing"
          return (
            <div key={item.key} className="rounded-xl border border-border bg-background/70 p-2">
              <div className="flex items-start justify-between gap-2">
                <h3 className="type-label text-foreground">{item.label}</h3>
                <StatusPill tone={tone}>{item.present ? "Ready" : "Missing"}</StatusPill>
              </div>
              <p className="type-meta mt-2 text-foreground/80">{rawText}</p>
              <p className="type-meta text-muted-foreground">{filteredText}</p>
            </div>
          )
        })}
      </div>
    </SettingsCard>
  )
}


export function OverviewTab({ sampleId, sample, context }: { sampleId: string; sample: any; context?: any }) {
  const queryClient = useQueryClient()
  const applyLatestAspc = useMutation({
    mutationFn: () => api.post(`/samples/${sampleId}/aspc/apply-latest`, {}).then((response) => response.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sample", sampleId] })
      queryClient.invalidateQueries({ queryKey: ["samples"] })
      notifySuccess("Latest ASPC applied", "The sample now uses the latest assay configuration.", "Assay configuration", { type: "sample", id: sampleId, name: sample?.name || sampleId })
    },
    onError: (error) => notifyActionError("Unable to apply latest ASPC", error, "Assay configuration", { type: "sample", id: sampleId, name: sample?.name || sampleId }),
  })
  const verificationSample = context?.verification_sample_used || sample?.verification_sample_used
  const files = fileItems(context)
  const snvFilters = sampleFilterSection(sample, "snv")
  const cnvFilters = sampleFilterSection(sample, "cnv")
  const fusionFilters = sampleFilterSection(sample, "fusion")
  const translocationFilters = sampleFilterSection(sample, "translocation")
  const adhoc = {
    ...(snvFilters?.adhoc_genes ? { snv: snvFilters.adhoc_genes } : {}),
    ...(cnvFilters?.adhoc_genes ? { cnv: cnvFilters.adhoc_genes } : {}),
    ...(fusionFilters?.adhoc_genes ? { fusion: fusionFilters.adhoc_genes } : {}),
  }
  const omics = String(sample?.omics_layer || "").toLowerCase()
  const reports = reportItems(sample)
  const filterGroups = overviewFilterGroups(sample, context)

  return (
    <div className="space-y-3">
      <AnalysisStatusStrip sample={sample} context={context} />

      {sample?.aspc_resolution?.used_base_configuration && (
        <section className="glass-card flex items-start gap-2 border-warn/35 bg-card/95 p-3 text-sm">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warn" />
          <div className="min-w-0">
            <strong className="text-warn">Base configuration in use.</strong>{" "}
            <span className="text-muted-foreground">
              {sample.aspc_resolution.warning || "No subpanel-specific ASPC is active."}{" "}
              Requested subpanel: <strong className="text-foreground">{sample.aspc_resolution.requested_subpanel_id}</strong>.
            </span>
          </div>
        </section>
      )}

      <div className="grid gap-3 xl:grid-cols-5">
        <SettingsCard title="Sample Meta" tone="border-t-yellow-400" className="xl:col-span-1">
          <div className="flex flex-wrap gap-2">
            {sample?.omics_layer && <StatusPill tone="blue">{String(sample.omics_layer).toUpperCase()}</StatusPill>}
            {sample?.platform && <StatusPill tone="green">{sample.platform}</StatusPill>}
            {sample?.read_mode && <StatusPill tone="green">{sample.read_mode}</StatusPill>}
            {sample?.sequencing_scope && <StatusPill tone="blue">{sample.sequencing_scope}</StatusPill>}
            {sample?.genome_build && <StatusPill>{`GRCh${sample.genome_build}`}</StatusPill>}
            {sample?.environment && <StatusPill tone="yellow">{sample.environment}</StatusPill>}
            {sample?.asp_id && <StatusPill tone="blue">ASP: {sample.asp_id}</StatusPill>}
            {sample?.current_aspc_key && <StatusPill tone="blue">ASPC: {sample.current_aspc_key}{sample.current_aspc_version ? ` v${sample.current_aspc_version}` : ""}</StatusPill>}
            {sample?.pipeline && <StatusPill tone="blue">{sample.pipeline}{sample.pipeline_version ? ` v${sample.pipeline_version}` : ""}</StatusPill>}
            {sampleReported(sample) && <StatusPill tone="blue">Reported</StatusPill>}
          </div>
          {context?.aspc_update?.available && (
            <div className="mt-3 rounded-lg border border-primary/25 bg-primary/5 p-2">
              <p className="text-xs font-semibold">Newer ASPC available: {context.aspc_update.latest_aspc_id}{context.aspc_update.latest_version ? ` v${context.aspc_update.latest_version}` : ""}</p>
              <button
                type="button"
                disabled={applyLatestAspc.isPending}
                onClick={() => {
                  if (window.confirm("Apply the latest ASPC? This replaces this sample's saved filters and analysis configuration.")) applyLatestAspc.mutate()
                }}
                className="mt-2 inline-flex items-center gap-1.5 rounded-md bg-primary px-2 py-1 text-xs font-semibold text-primary-foreground disabled:opacity-60"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                {applyLatestAspc.isPending ? "Applying..." : "Apply latest ASPC"}
              </button>
            </div>
          )}
        </SettingsCard>

        <SettingsCard title="Case and Control" tone="border-t-orange-400" className="xl:col-span-2">
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="type-table-cell w-full min-w-[38rem] border-separate border-spacing-0">
              <thead>
                <tr className="type-table-header bg-muted/65 text-left text-muted-foreground">
                  <th className="w-28 px-3 py-1">Field</th>
                  <th className="bg-pass/8 px-3 py-1 text-pass">Case</th>
                  <th className="bg-tier3/8 px-3 py-1 text-tier3">Control</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ["ID", sample?.case?.id || sample?.case_id, sample?.control?.id || sample?.control_id],
                  ["Clarity ID", sample?.case?.clarity_id, sample?.control?.clarity_id],
                  ["Pool ID", sample?.case?.clarity_pool_id, sample?.control?.clarity_pool_id],
                  ["Sequencing run", sample?.case?.sequencing_run, sample?.control?.sequencing_run],
                  ["Reads", sample?.case?.reads, sample?.control?.reads],
                  ["FFPE", sample?.case?.ffpe ? "Yes" : "No", sample?.control?.ffpe ? "Yes" : "No"],
                  ["Purity", formatPurityPercentage(sample?.case?.purity), formatPurityPercentage(sample?.control?.purity)],
                ].map(([label, caseValue, controlValue]) => (
                  <tr key={String(label)} className="border-t border-border/40">
                    <th scope="row" className="border-t border-border/40 bg-muted/35 px-3 py-1 text-left font-semibold uppercase text-muted-foreground">{label}</th>
                    <td className="border-t border-border/55 bg-pass/5 px-3 py-1 font-normal text-foreground">{displayValue(caseValue)}</td>
                    <td className="border-t border-border/55 bg-tier3/5 px-3 py-1 font-normal text-foreground">{sample?.paired ? displayValue(controlValue) : "Not paired"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SettingsCard>

        <SettingsCard title={`Files & QC (${sample?.omics_layer || "-"})`} tone="border-t-orange-800" className="xl:col-span-2">
          <div className="space-y-2">
            {files.length ? files.map((file: any, index: number) => (
              <div key={file.key || file.path || index} className="flex items-start justify-between gap-3 rounded-xl border border-border bg-background/70 px-3 py-2">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold">{sampleArtifactPresentation(file.analysis_type).label}</span>
                    <StatusPill tone={file.required ? "blue" : "muted"}>{file.required ? "Required" : "Optional"}</StatusPill>
                    {formatFileSize(file.size_bytes) && (
                      <StatusPill tone="muted">{formatFileSize(file.size_bytes)}</StatusPill>
                    )}
                    {sampleArtifactCountLabel(file.analysis_type, file.data_count) && (
                      <StatusPill tone="green">{sampleArtifactCountLabel(file.analysis_type, file.data_count)}</StatusPill>
                    )}
                  </div>
                  <p className={`mt-0.5 break-all text-[11px] ${file.path && file.exists === false ? "text-fail" : "text-muted-foreground"}`}>
                    {file.path || sampleArtifactPresentation(file.analysis_type).missingMessage}
                  </p>
                  {file.checksum && (
                    <p className="mt-0.5 truncate text-[10px] text-muted-foreground">
                      checksum {file.checksum}
                    </p>
                  )}
                </div>
                <StatusPill tone={sampleArtifactStatus(file.availability).tone}>
                  {sampleArtifactStatus(file.availability).label}
                </StatusPill>
              </div>
            )) : <p className="text-sm text-muted-foreground">No assay-configured files for this sample.</p>}
          </div>
        </SettingsCard>
      </div>

      {reports.length > 0 && (
        <SettingsCard title="Saved Reports" tone="border-t-tier3">
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {reports.map((report: any, index: number) => {
              const reportId = report?._id || report?.id || report?.report_id || report?.report_num || index
              const label = report?.report_name || report?.file || report?.report_id || `Report ${index + 1}`
              return (
                <div key={String(reportId)} className="rounded-xl border border-border bg-background/70 p-3">
                  <p className="break-all text-sm font-semibold">{label}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{formatDate(report?.created_at || report?.time_created || report?.date)}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Link to={`/samples/${sample?.name || sampleId}/reports/${reportId}`} className="rounded-lg bg-primary px-3 py-1.5 text-xs font-bold text-primary-foreground">
                      View
                    </Link>
                    <a href={apiPath(`/samples/${sample?.name || sampleId}/reports/${reportId}/download`)} className="rounded-lg border border-border px-3 py-1.5 text-xs font-bold hover:bg-muted">
                      Download
                    </a>
                  </div>
                </div>
              )
            })}
          </div>
        </SettingsCard>
      )}

      <div className="grid gap-3 xl:grid-cols-4">
        <SampleGeneSettings sampleId={sampleId} sample={sample} />

        <SettingsCard title="Gene Filters" tone="border-t-slate-400" className="xl:col-span-2">
          <div className="divide-y divide-border/60">
            {omics === "dna" && (
              <section className="py-3 first:pt-0">
                <h3 className="type-label text-green-700 dark:text-green-300">Selected SNV ISGLs</h3>
                <div className="type-body-sm mt-2 flex flex-wrap gap-2">
                  {(snvFilters.snvlists || []).length ? snvFilters.snvlists.map((name: string) => <StatusPill key={name} tone="green">{name}</StatusPill>) : <p className="text-muted-foreground">No ISGLs selected for this sample.</p>}
                </div>
              </section>
            )}
            {omics === "dna" && (
              <section className="py-3">
                <h3 className="type-label text-warn">Selected CNV ISGLs</h3>
                <div className="type-body-sm mt-2 flex flex-wrap gap-2">
                  {(cnvFilters.cnvlists || []).length ? cnvFilters.cnvlists.map((name: string) => <StatusPill key={name} tone="yellow">{name}</StatusPill>) : <p className="text-muted-foreground">No CNV ISGLs selected for this sample.</p>}
                </div>
              </section>
            )}
            {omics === "rna" && (
              <section className="py-3 first:pt-0">
                <h3 className="type-label text-tier4">Selected Fusion Lists</h3>
                <div className="type-body-sm mt-2 flex flex-wrap gap-2">
                  {(fusionFilters.fusionlists || []).length ? fusionFilters.fusionlists.map((name: string) => <StatusPill key={name} tone="green">{name}</StatusPill>) : <p className="text-muted-foreground">No fusion lists selected for this sample.</p>}
                </div>
              </section>
            )}
            {omics === "dna" && (
              <section className="py-3">
                <h3 className="type-label text-tier3">Selected DNA Fusion / Translocation ISGLs</h3>
                <div className="type-body-sm mt-2 flex flex-wrap gap-2">
                  {(translocationFilters.fusionlists || []).length ? translocationFilters.fusionlists.map((name: string) => <StatusPill key={name} tone="blue">{name}</StatusPill>) : <p className="text-muted-foreground">No DNA fusion or translocation ISGLs selected for this sample.</p>}
                </div>
              </section>
            )}
            <section className="py-3 last:pb-0">
              <h3 className="type-label text-tier3">Sample Ad-Hoc Genes</h3>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                {Object.keys(adhoc).length ? Object.entries(adhoc).map(([scope, entry]: [string, any]) => (
                  <div key={scope} className="rounded-xl border border-border bg-background/70 p-2">
                    <p className="type-label text-muted-foreground">{scope}</p>
                    <p className="type-body-sm mt-0.5 text-foreground">{entry?.label || "Ad Hoc"}</p>
                    <p className="type-meta text-muted-foreground">{(entry?.genes || []).length} gene(s)</p>
                  </div>
                )) : <p className="type-body-sm text-muted-foreground">No ad-hoc genes configured.</p>}
              </div>
            </section>
          </div>
        </SettingsCard>

        <SettingsCard title="Configured Filters" tone="border-t-blue-400" className="xl:col-span-2">
          <div className="space-y-3">
            {filterGroups.length ? filterGroups.map((group) => (
              <section key={group.key} aria-labelledby={`filter-group-${group.key}`} className="rounded-xl border border-border bg-background/55 p-2.5">
                <h3 id={`filter-group-${group.key}`} className="type-label mb-2 text-foreground">{group.label}</h3>
                <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {group.rows.map(([label, rowValue]) => (
                    <div key={label} className="rounded-lg bg-card px-2.5 py-2 shadow-sm">
                      <dt className="type-meta text-muted-foreground">{label}</dt>
                      <dd className="type-body-sm mt-0.5 break-words text-foreground">{displayValue(rowValue)}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            )) : <p className="text-sm text-muted-foreground">No configurable filters apply to the enabled analyses for this sample.</p>}
          </div>
        </SettingsCard>
      </div>

      {verificationSample && (
        <section className="paper-inset rounded-xl px-3 py-2">
          <h2 className="text-base font-semibold uppercase tracking-wide text-foreground">Verification Sample</h2>
          <p className="mt-2 text-sm font-semibold text-yellow-700 dark:text-yellow-300">
            Verification sample used: {verificationSample}
          </p>
        </section>
      )}
    </div>
  )
}
