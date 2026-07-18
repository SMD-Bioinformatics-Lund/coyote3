import { useEffect, useMemo, useState } from "react"
import type { ReactNode } from "react"
import { createPortal } from "react-dom"
import { Link } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Activity, Save, Trash2, ChevronDown, ChevronUp, Search, X } from "lucide-react"
import { api } from "@/lib/api"
import { shortCount } from "@/lib/detail-formatters"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { sampleFilterSection, sampleReported } from "@/lib/sample-shape"
import { apiPath } from "@/lib/runtime-paths"

function displayValue(value: unknown) {
  if (value === undefined || value === null || value === "") return "-"
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(4)))
  return String(value)
}

function geneInputCount(value: string) {
  return value.split(/[,\s]+/).map((item) => item.trim()).filter(Boolean).length
}

function formatDate(value: unknown) {
  if (!value) return "-"
  const date = new Date(String(value))
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString()
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

function StatusPill({ children, tone = "muted" }: { children: ReactNode; tone?: "blue" | "green" | "yellow" | "red" | "indigo" | "muted" }) {
  const tones = {
    blue: "bg-blue-100 text-blue-800 border-blue-200",
    green: "bg-green-100 text-green-800 border-green-200",
    yellow: "bg-yellow-100 text-yellow-900 border-yellow-200",
    red: "bg-red-100 text-red-800 border-red-200",
    indigo: "bg-indigo-100 text-indigo-800 border-indigo-200",
    muted: "bg-muted text-muted-foreground border-border",
  }
  return <span className={`rounded-full border px-2 py-0.5 text-[11px] font-bold ${tones[tone]}`}>{children}</span>
}

function BiomarkerBadge({ label, value, title }: { label: string; value: unknown; title?: string }) {
  return (
    <span title={title} className="inline-flex items-center gap-1 rounded-md bg-sand-100 px-1.5 py-0.5 text-[11px] font-semibold text-foreground shadow-sm dark:bg-sand-900/40">
      <span className="text-muted-foreground">{label}:</span>
      {displayValue(value)}
    </span>
  )
}

type BiomarkerBadgeEntry = {
  key: string
  node: ReactNode
}

function numericBiomarkerValue(value: unknown) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

function msiBadge(marker: any, label: string, key: string): BiomarkerBadgeEntry | null {
  if (!marker || typeof marker !== "object") return null
  const percentage = numericBiomarkerValue(marker.per ?? marker.perc)
  if (percentage === null) return null
  return {
    key,
    node: (
      <BiomarkerBadge
        label={label}
        value={`${percentage}%`}
        title={`Total: ${displayValue(marker.tot)}; Somatic: ${displayValue(marker.som)}`}
      />
    ),
  }
}

function hrdBadge(marker: any): BiomarkerBadgeEntry | null {
  if (!marker || typeof marker !== "object") return null
  const sum = numericBiomarkerValue(marker.sum)
  if (sum === null) return null
  return {
    key: "HRD",
    node: (
      <BiomarkerBadge
        label="HRD"
        value={sum}
        title={`TAI: ${displayValue(marker.tai)}; HRD: ${displayValue(marker.hrd)}; LST: ${displayValue(marker.lst)}`}
      />
    ),
  }
}

function SettingsCard({ title, tone, children, className = "" }: { title: string; tone: string; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-border bg-card/90 p-3 shadow-sm border-t-4 ${tone} ${className}`}>
      <h2 className="mb-2.5 text-xs font-black uppercase tracking-wide text-foreground">{title}</h2>
      {children}
    </section>
  )
}

function FieldList({ rows }: { rows: Array<[string, unknown]> }) {
  return (
    <dl className="grid gap-1.5 text-xs">
      {rows.map(([label, rowValue]) => (
        <div key={label} className="grid grid-cols-[5.8rem_1fr] gap-2 rounded-md bg-background/60 px-2 py-1.5">
          <dt className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">{label}</dt>
          <dd className="min-w-0 break-words text-xs font-semibold">{displayValue(rowValue)}</dd>
        </div>
      ))}
    </dl>
  )
}

function SettingsHero({ sample }: { sample: any }) {
  const status = String(sample?.ingest_status || "").toLowerCase()
  const statusTone = status === "ready" ? "blue" : status === "failed" ? "red" : status === "pending" ? "muted" : "muted"
  return (
    <section className="rounded-xl border border-border border-t-4 border-t-teal-800 bg-card/90 p-3 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Sample</div>
          <h1 className="mt-1 flex flex-wrap items-center gap-2 break-all text-xl font-black text-foreground">
            {sample?.name || sample?.case_id || sample?._id || "-"}
            <StatusPill tone={sample?.paired ? "green" : "yellow"}>{sample?.paired ? "Paired" : "Unpaired"}</StatusPill>
            {sample?.ingest_status && <StatusPill tone={statusTone}>{sample.ingest_status}</StatusPill>}
            {sample?.archived && <StatusPill tone="red">Archived</StatusPill>}
            <StatusPill tone={sampleReported(sample) ? "indigo" : "yellow"}>{sampleReported(sample) ? "Reported" : "Unreported"}</StatusPill>
          </h1>
          <div className="mt-2 flex flex-wrap gap-1.5 text-xs text-muted-foreground">
            {sample?.case_id && <StatusPill>Case: {sample.case_id}</StatusPill>}
            {sample?.time_added && <StatusPill>Added {formatDate(sample.time_added)}</StatusPill>}
          </div>
        </div>
      </div>
    </section>
  )
}

export function BiomarkerRow({ context }: { context?: any }) {
  const biomarkers = context?.display_sections_data?.biomarkers || context?.biomarkers || []
  if (!biomarkers.length) return null
  const badges: BiomarkerBadgeEntry[] = biomarkers.flatMap((bio: any, index: number) => [
    msiBadge(bio?.MSIS, "MSI (Single)", `MSIS-${index}`),
    msiBadge(bio?.MSIP, "MSI (Paired)", `MSIP-${index}`),
    hrdBadge(bio?.HRD),
  ].filter((badge): badge is BiomarkerBadgeEntry => Boolean(badge)))
  if (!badges.length) return null

  return (
    <div className="mt-3 flex flex-wrap items-center gap-1.5">
      {badges.map((badge, index) => (
        <span key={`${badge.key}-${index}`} className="inline-flex items-center gap-1.5">
          {index > 0 && <span className="text-muted-foreground/50">|</span>}
          {badge.node}
        </span>
      ))}
    </div>
  )
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
  const filters = sample?.filters || context?.sample?.filters || {}
  const sections = [
    {
      target: "SNV",
      ids: filters?.snv?.snvlists,
      options: context?.snv_genelist_options,
    },
    {
      target: "CNV",
      ids: filters?.cnv?.cnvlists,
      options: context?.cnvlist_options,
    },
    {
      target: "FUSION",
      ids: filters?.fusion?.fusionlists,
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
    <section className="rounded-xl bg-blue-50 shadow-md dark:bg-blue-950/20">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between rounded-t-xl px-4 py-2 text-left transition hover:bg-purple-200/70 dark:hover:bg-purple-900/30"
      >
        <h2 className="text-base font-semibold uppercase tracking-wide text-foreground">{title}</h2>
        {open ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
      </button>

      <div className="px-4 pb-3 text-sm font-medium">
        {entries.length ? (
          <div className="flex flex-wrap gap-1.5">
            {entries.map((raw: any) => {
              const covered = raw?.covered || []
              const genes = raw?.genes || []
              const name = raw?.name || raw?.id
              return (
                <span
                  key={`${raw?.target || "GENE"}-${raw?.id || name}`}
                  className={`rounded-md px-3 py-1 text-xs shadow-sm transition ${
                    raw?.is_active === false
                      ? "bg-orange-400 text-orange-950 hover:bg-orange-500"
                      : raw?.adhoc
                        ? "bg-purple-200 text-purple-950 hover:bg-purple-300"
                        : "bg-gray-200 text-gray-900 hover:bg-green-200"
                  }`}
                >
                  <span className="font-black">{raw?.target || "GENE"}</span>: {name} {raw?.adhoc ? <i>(AdHoc)</i> : null}:{" "}
                  {Number(raw?.covered_count ?? covered.length)} of {Number(raw?.gene_count ?? genes.length)} gene(s) covered
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
              <div key={`${raw?.target || "GENE"}-${raw?.id || name}`} className="rounded-md bg-background/70 p-2 shadow-sm">
                <p className={raw?.is_active === false ? "text-sm font-bold text-red-700 dark:text-red-300" : "text-sm font-bold text-foreground"}>
                  {raw?.target ? `${raw.target}: ` : ""}{name} {raw?.adhoc ? <i>(AdHoc)</i> : null} - {Number(raw?.covered_count ?? covered.length)} of {Number(raw?.gene_count ?? genes.length)} gene(s) covered
                  {raw?.is_active === false ? ": This list is inactive and the filter has not been applied." : ":"}
                </p>
                {genes.length > 0 ? (
                  <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
                    {genes.map((gene: string) => (
                      <span
                        key={gene}
                        title={covered.includes(gene) ? "This gene is covered in the panel" : "This gene is not covered in the panel"}
                        className={covered.includes(gene) ? "rounded-md bg-green-200 px-1.5 py-0.5 text-green-950" : "rounded-md bg-orange-400 px-1.5 py-0.5 text-orange-950"}
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

function fileItems(sample: any, context?: any) {
  return context?.sample_expected_files || sample?.sample_expected_files || sample?.expected_files || []
}

function reportItems(sample: any) {
  const reports = sample?.reports || sample?.report_files || []
  if (Array.isArray(reports)) return reports
  if (reports && typeof reports === "object") return Object.values(reports)
  return []
}

function configuredAnalysisSections(sample: any, context?: any) {
  const sections = context?.analysis_sections || context?.aspc?.reporting?.analysis || sample?.analysis_sections || []
  return new Set((Array.isArray(sections) ? sections : []).map((item: unknown) => String(item).toLowerCase()))
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
                <h3 className="text-[11px] font-black uppercase tracking-wide text-foreground">{item.label}</h3>
                <StatusPill tone={tone}>{item.present ? "Ready" : "Missing"}</StatusPill>
              </div>
              <p className="mt-2 text-xs font-semibold text-muted-foreground">{rawText}</p>
              <p className="text-xs text-muted-foreground">{filteredText}</p>
            </div>
          )
        })}
      </div>
    </SettingsCard>
  )
}

function targetOptions(sample: any) {
  const omics = String(sample?.omics_layer || "").toLowerCase()
  return omics === "rna"
    ? [{ value: "fusion", label: "Fusion lists" }]
    : [
        { value: "snv", label: "SNV gene lists" },
        { value: "cnv", label: "CNV gene lists" },
      ]
}

function filterKeyForTarget(target: string) {
  if (target === "cnv") return "cnvlists"
  if (target === "fusion") return "fusionlists"
  return "snvlists"
}

function SampleGeneSettings({ sampleId, sample }: { sampleId: string; sample: any }) {
  const queryClient = useQueryClient()
  const sampleName = String(sample?.name || sample?.case_id || sampleId)
  const options = targetOptions(sample)
  const [target, setTarget] = useState(options[0]?.value || "snv")
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [adhocLabel, setAdhocLabel] = useState("adhoc")
  const [adhocGenes, setAdhocGenes] = useState("")
  const [listPickerOpen, setListPickerOpen] = useState(false)
  const [listSearch, setListSearch] = useState("")

  const selectedFromSample = useMemo(
    () => sampleFilterSection(sample, target as any)?.[filterKeyForTarget(target)] || [],
    [sample, target],
  )
  useEffect(() => {
    setSelectedIds(Array.isArray(selectedFromSample) ? selectedFromSample.map(String) : [])
    const adhoc = sampleFilterSection(sample, target as any)?.adhoc_genes
    setAdhocLabel(adhoc?.label || "adhoc")
    setAdhocGenes(Array.isArray(adhoc?.genes) ? adhoc.genes.join("\n") : "")
  }, [target, sample, selectedFromSample])

  const genelists = useQuery({
    queryKey: ["sample-genelists", sampleId, target],
    queryFn: () => api.get(`/samples/${sampleId}/genelists?target=${target}`).then((res) => res.data),
  })
  const effectiveGenes = useQuery({
    queryKey: ["sample-effective-genes", sampleId, target],
    queryFn: () => api.get(`/samples/${sampleId}/effective-genes?target=${target}`).then((res) => res.data),
  })

  const invalidateSampleSettings = () => {
    queryClient.invalidateQueries({ queryKey: ["sample", sampleId] })
    queryClient.invalidateQueries({ queryKey: ["samples"] })
    queryClient.invalidateQueries({ queryKey: ["sample-effective-genes", sampleId, target] })
    queryClient.invalidateQueries({ queryKey: ["report-preview", sampleId] })
    const targetQueryKeys: Record<string, unknown[][]> = {
      snv: [["sample-variants", sampleId], ["variants", sampleId]],
      cnv: [["sample-cnvs", sampleId], ["cnvs", sampleId]],
      fusion: [["sample-fusions", sampleId], ["fusions", sampleId]],
    }
    ;(targetQueryKeys[target] || []).forEach((queryKey) => queryClient.invalidateQueries({ queryKey }))
  }

  const saveLists = useMutation({
    mutationFn: () => api.put(`/samples/${sampleId}/genelists/selection?target=${target}`, { isgl_ids: selectedIds, list_type: target }),
    onSuccess: () => {
      invalidateSampleSettings()
      notifySuccess(
        "Gene lists applied",
        `${selectedIds.length} ${target.toUpperCase()} list(s) applied to ${sampleName}.`,
        "Sample overview",
        { type: "sample", id: sampleId, name: sampleName, sampleName }
      )
    },
    onError: (error) => {
      notifyActionError("Unable to apply gene lists", error, "Sample overview", {
        type: "sample",
        id: sampleId,
        name: sampleName,
        sampleName,
      })
    },
  })
  const saveAdhoc = useMutation({
    mutationFn: () => api.put(`/samples/${sampleId}/adhoc-genes?target=${target}`, { label: adhocLabel, genes: adhocGenes, list_type: target }),
    onSuccess: (result) => {
      invalidateSampleSettings()
      notifySuccess(
        "Ad-hoc genes saved",
        `${result?.data?.gene_count ?? geneInputCount(adhocGenes)} ${target.toUpperCase()} gene(s) saved for ${sampleName}.`,
        "Sample overview",
        { type: "sample", id: sampleId, name: sampleName, sampleName }
      )
    },
    onError: (error) => {
      notifyActionError("Unable to save ad-hoc genes", error, "Sample overview", {
        type: "sample",
        id: sampleId,
        name: sampleName,
        sampleName,
      })
    },
  })
  const clearAdhoc = useMutation({
    mutationFn: () => api.delete(`/samples/${sampleId}/adhoc-genes?target=${target}`),
    onSuccess: () => {
      invalidateSampleSettings()
      setAdhocGenes("")
      notifySuccess(
        "Ad-hoc genes cleared",
        `${target.toUpperCase()} ad-hoc genes were cleared for ${sampleName}.`,
        "Sample overview",
        { type: "sample", id: sampleId, name: sampleName, sampleName }
      )
    },
    onError: (error) => {
      notifyActionError("Unable to clear ad-hoc genes", error, "Sample overview", {
        type: "sample",
        id: sampleId,
        name: sampleName,
        sampleName,
      })
    },
  })

  const items = genelists.data?.items || []
  const effective = effectiveGenes.data?.items || []
  const isPending = saveLists.isPending || saveAdhoc.isPending || clearAdhoc.isPending
  const selectedSet = new Set(selectedIds)
  const selectedItems = items.filter((item: any) => selectedSet.has(String(item.isgl_id)))
  const filteredItems = items.filter((item: any) => {
    const needle = listSearch.trim().toLowerCase()
    if (!needle) return true
    return [item.name, item.isgl_id, item.description, item.diagnosis]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(needle))
  })
  const toggleList = (id: string, checked: boolean) => {
    setSelectedIds((current) => {
      const currentSet = new Set(current)
      if (checked) currentSet.add(id)
      else currentSet.delete(id)
      return Array.from(currentSet)
    })
  }
  const applySelectedLists = () => saveLists.mutate(undefined, { onSuccess: () => setListPickerOpen(false) })

  return (
    <SettingsCard title="Sample Gene Settings" tone="border-t-genelist" className="xl:col-span-2">
      <div className="space-y-4">
        <div className="flex flex-wrap gap-2">
          {options.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setTarget(option.value)}
              className={`rounded-lg px-3 py-1.5 text-xs font-bold ${target === option.value ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-muted/80"}`}
            >
              {option.label}
            </button>
          ))}
        </div>

        <div className="rounded-xl border border-border bg-background/70 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-xs font-black uppercase tracking-wider text-muted-foreground">Selectable lists</h3>
              <p className="mt-1 text-xs text-muted-foreground">
                {genelists.isLoading ? "Loading available lists..." : `${selectedIds.length} of ${items.length} selected`}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setListPickerOpen(true)}
              disabled={genelists.isLoading}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-1.5 text-xs font-bold text-primary-foreground shadow-sm disabled:opacity-50"
            >
              <ChevronDown className="h-3.5 w-3.5" />
              Choose lists
            </button>
          </div>
          <div className="mt-3 min-h-10 rounded-lg border border-dashed border-border bg-card/70 p-2">
            {selectedItems.length ? (
              <div className="flex flex-wrap gap-1.5">
                {selectedItems.map((item: any) => (
                  <span key={String(item.isgl_id)} className="rounded-md bg-genelist/10 px-2 py-1 text-xs font-bold text-genelist">
                    {item.name || item.isgl_id}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No {target.toUpperCase()} ISGLs selected.</p>
            )}
          </div>

          {listPickerOpen && createPortal(
            <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/35 p-4">
              <div className="flex max-h-[calc(100vh-2rem)] w-full max-w-xl flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-lg">
                <div className="flex items-start justify-between gap-3 border-b border-border px-4 py-3">
                  <div>
                    <h3 className="text-sm font-black uppercase tracking-wide text-foreground">Choose {target.toUpperCase()} ISGLs</h3>
                    <p className="mt-0.5 text-xs text-muted-foreground">{selectedIds.length} selected from {items.length} available lists</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setListPickerOpen(false)}
                    className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                    aria-label="Close list picker"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>

                <div className="min-h-0 flex-1 space-y-3 overflow-hidden p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="relative min-w-0 flex-1">
                      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                      <input
                        value={listSearch}
                        onChange={(event) => setListSearch(event.target.value)}
                        className="w-full rounded-lg border border-input bg-background py-2 pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-primary/40"
                        placeholder="Search lists..."
                      />
                    </div>
                    <button
                      type="button"
                      onClick={() => setSelectedIds(items.map((item: any) => String(item.isgl_id)))}
                      className="rounded-lg border border-border px-3 py-2 text-xs font-bold hover:bg-muted"
                    >
                      Select all
                    </button>
                    <button
                      type="button"
                      onClick={() => setSelectedIds([])}
                      className="rounded-lg border border-border px-3 py-2 text-xs font-bold hover:bg-muted"
                    >
                      Clear
                    </button>
                  </div>

                  <div className="max-h-[min(22rem,calc(100vh-18rem))] overflow-auto rounded-xl border border-border bg-background">
                    {filteredItems.length ? filteredItems.map((item: any) => {
                      const id = String(item.isgl_id)
                      const checked = selectedSet.has(id)
                      return (
                        <label
                          key={id}
                          className={`flex cursor-pointer items-start gap-3 border-b border-border px-3 py-2.5 last:border-b-0 hover:bg-muted/60 ${checked ? "bg-genelist/10" : ""}`}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={(event) => toggleList(id, event.target.checked)}
                            className="mt-0.5 h-4 w-4"
                          />
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-sm font-bold text-foreground">{item.name || id}</span>
                            <span className="mt-0.5 block text-xs text-muted-foreground">
                              {item.gene_count ?? 0} genes{item.version ? `, v${item.version}` : ""}{item.diagnosis ? `, ${item.diagnosis}` : ""}
                            </span>
                          </span>
                        </label>
                      )
                    }) : (
                      <div className="px-3 py-8 text-center text-sm text-muted-foreground">No lists match this search.</div>
                    )}
                  </div>
                </div>

                <div className="flex items-center justify-between gap-3 border-t border-border bg-muted/40 px-4 py-3">
                  <button
                    type="button"
                    onClick={() => setListPickerOpen(false)}
                    className="rounded-lg border border-border bg-background px-3 py-2 text-xs font-bold hover:bg-muted"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={applySelectedLists}
                    disabled={isPending}
                    className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-xs font-bold text-primary-foreground shadow-sm disabled:opacity-50"
                  >
                    {saveLists.isPending ? <Activity className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                    Apply lists
                  </button>
                </div>
              </div>
            </div>,
            document.body,
          )}
        </div>

        <div className="rounded-xl border border-border bg-background/70 p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h3 className="text-xs font-black uppercase tracking-wider text-muted-foreground">Ad-hoc genes</h3>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => clearAdhoc.mutate()}
                disabled={isPending}
                className="inline-flex items-center gap-2 rounded-lg border border-destructive/30 px-3 py-1.5 text-xs font-bold text-destructive hover:bg-destructive/10 disabled:opacity-50"
              >
                <Trash2 className="h-3.5 w-3.5" />
                Clear
              </button>
              <button
                type="button"
                onClick={() => saveAdhoc.mutate()}
                disabled={isPending}
                className="inline-flex items-center gap-2 rounded-lg bg-pass px-3 py-1.5 text-xs font-bold text-white disabled:opacity-50"
              >
                {saveAdhoc.isPending ? <Activity className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                Save
              </button>
            </div>
          </div>
          <input
            value={adhocLabel}
            onChange={(event) => setAdhocLabel(event.target.value)}
            className="mb-2 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/40"
            placeholder="Label"
          />
          <textarea
            value={adhocGenes}
            onChange={(event) => setAdhocGenes(event.target.value)}
            className="min-h-28 w-full rounded-lg border border-input bg-background p-3 font-mono text-xs outline-none focus:ring-2 focus:ring-primary/40"
            placeholder="One gene per line, or separated by spaces/commas"
          />
        </div>

        <div className="rounded-xl border border-border bg-background/70 p-3">
          <h3 className="text-xs font-black uppercase tracking-wider text-muted-foreground">Effective genes</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            {effective.length} effective gene(s), {effectiveGenes.data?.asp_covered_genes_count ?? 0} covered by assay panel.
          </p>
          <div className="mt-2 max-h-36 overflow-auto rounded-lg border border-border bg-card/70 p-2">
            <div className="flex flex-wrap gap-1">
              {effective.length ? effective.map((gene: any) => (
                <span key={String(gene)} className="rounded-md bg-genelist/10 px-1.5 py-0.5 text-xs font-semibold text-genelist">{String(gene)}</span>
              )) : <span className="text-sm text-muted-foreground">No effective genes returned.</span>}
            </div>
          </div>
        </div>
      </div>
    </SettingsCard>
  )
}

export function OverviewTab({ sampleId, sample, context }: { sampleId: string; sample: any; context?: any }) {
  const verificationSample = context?.verification_sample_used || sample?.verification_sample_used
  const files = fileItems(sample, context)
  const snvFilters = sampleFilterSection(sample, "snv")
  const cnvFilters = sampleFilterSection(sample, "cnv")
  const fusionFilters = sampleFilterSection(sample, "fusion")
  const coverageFilters = sampleFilterSection(sample, "coverage")
  const adhoc = {
    ...(snvFilters?.adhoc_genes ? { snv: snvFilters.adhoc_genes } : {}),
    ...(cnvFilters?.adhoc_genes ? { cnv: cnvFilters.adhoc_genes } : {}),
    ...(fusionFilters?.adhoc_genes ? { fusion: fusionFilters.adhoc_genes } : {}),
  }
  const omics = String(sample?.omics_layer || "").toLowerCase()
  const reports = reportItems(sample)
  const filterRows: Array<[string, unknown]> = [
    ["Min depth", snvFilters.min_depth],
    ["Min alt reads", snvFilters.min_alt_reads],
    ["Min VAF", snvFilters.min_freq],
    ["Max VAF", snvFilters.max_freq],
    ["Max normal VAF", snvFilters.max_control_freq],
    ["Max pop freq", snvFilters.max_popfreq],
    ["CNV min size", cnvFilters.min_cnv_size],
    ["CNV max size", cnvFilters.max_cnv_size],
    ["CNV gain", cnvFilters.cnv_gain_cutoff],
    ["CNV loss", cnvFilters.cnv_loss_cutoff],
    ["Coverage warn", coverageFilters.warn_cov],
    ["Coverage error", coverageFilters.error_cov],
    ["Fusion pairs", fusionFilters.min_spanning_pairs],
    ["Fusion reads", fusionFilters.min_spanning_reads],
  ]

  return (
    <div className="space-y-3">
      <SettingsHero sample={sample} />
      <AnalysisStatusStrip sample={sample} context={context} />

      {["pending", "failed"].includes(String(sample?.ingest_status || "").toLowerCase()) && (
        <section className="rounded-2xl border border-yellow-400 bg-yellow-50 p-4 text-sm font-semibold text-yellow-900 shadow-sm dark:bg-yellow-950/30 dark:text-yellow-200">
          Some expected analysis files are missing or unreadable. Verify inputs before reporting.
        </section>
      )}

      <div className="grid gap-3 xl:grid-cols-5">
        <SettingsCard title="Sample Meta" tone="border-t-yellow-400" className="xl:col-span-1">
          <div className="flex flex-wrap gap-2">
            {sample?.omics_layer && <StatusPill tone="blue">{String(sample.omics_layer).toUpperCase()}</StatusPill>}
            {sample?.sequencing_technology && <StatusPill tone="green">{sample.sequencing_technology}</StatusPill>}
            {sample?.sequencing_scope && <StatusPill tone="indigo">{sample.sequencing_scope}</StatusPill>}
            {sample?.genome_build && <StatusPill>{`GRCh${sample.genome_build}`}</StatusPill>}
            {sample?.profile && <StatusPill tone="yellow">{sample.profile}</StatusPill>}
            {sample?.assay && <StatusPill tone="blue">Assay: {sample.assay}</StatusPill>}
            {sample?.pipeline && <StatusPill tone="indigo">{sample.pipeline}{sample.pipeline_version ? ` v${sample.pipeline_version}` : ""}</StatusPill>}
            {sampleReported(sample) && <StatusPill tone="indigo">Reported</StatusPill>}
          </div>
          <BiomarkerRow context={context} />
        </SettingsCard>

        <SettingsCard title="Overview" tone="border-t-orange-400" className="xl:col-span-2">
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-xl border border-green-200 bg-green-50/80 p-2.5 dark:bg-green-950/20">
              <h3 className="mb-2 text-xs font-black uppercase tracking-wide text-green-700 dark:text-green-300">Case</h3>
              {sample?.case ? (
                <FieldList rows={[
                  ["ID", sample.case.id],
                  ["Clarity ID", sample.case.clarity_id || "N/A"],
                  ["Pool ID", sample.case.clarity_pool_id || "N/A"],
                  ["Run", sample.case.sequencing_run || "N/A"],
                  ["Reads", sample.case.reads || "N/A"],
                  ["FFPE", sample.case.ffpe ? "Yes" : "No"],
                  ["Purity", sample.case.purity ?? "N/A"],
                ]} />
              ) : <p className="text-sm text-muted-foreground">No Case Information</p>}
            </div>
            <div className="rounded-xl border border-blue-200 bg-blue-50/80 p-2.5 dark:bg-blue-950/20">
              <h3 className="mb-2 text-xs font-black uppercase tracking-wide text-blue-600 dark:text-blue-300">Control</h3>
              {sample?.paired && sample?.control ? (
                <FieldList rows={[
                  ["ID", sample.control.id],
                  ["Clarity ID", sample.control.clarity_id || "N/A"],
                  ["Pool ID", sample.control.clarity_pool_id || "N/A"],
                  ["Run", sample.control.sequencing_run || "N/A"],
                  ["Reads", sample.control.reads || "N/A"],
                  ["FFPE", sample.control.ffpe ? "Yes" : "No"],
                  ["Purity", sample.control.purity ?? "N/A"],
                ]} />
              ) : <p className="text-sm text-muted-foreground">Unpaired sample (no control)</p>}
            </div>
          </div>
        </SettingsCard>

        <SettingsCard title={`Files & QC (${sample?.omics_layer || "-"})`} tone="border-t-orange-800" className="xl:col-span-2">
          <div className="space-y-2">
            {files.length ? files.map((file: any, index: number) => (
              <div key={file.path || file.label || index} className="flex items-start justify-between gap-3 rounded-xl border border-border bg-background/70 px-3 py-2">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold">{file.label || file.name || "File"}</span>
                    <StatusPill tone={file.required ? "blue" : "muted"}>{file.required ? "Required" : "Optional"}</StatusPill>
                    {formatFileSize(file.size_bytes) && (
                      <StatusPill tone="muted">{formatFileSize(file.size_bytes)}</StatusPill>
                    )}
                    {file.count_badge && <StatusPill tone="green">{file.count_badge}</StatusPill>}
                  </div>
                  <p className={`mt-0.5 break-all text-[11px] ${file.path && file.exists === false ? "text-red-700 dark:text-red-300" : "text-muted-foreground"}`}>
                    {file.path || file.missing_msg || "No file available"}
                  </p>
                  {file.checksum && (
                    <p className="mt-0.5 truncate text-[10px] text-muted-foreground">
                      checksum {file.checksum}
                    </p>
                  )}
                </div>
                <StatusPill tone={file.present || file.exists ? "green" : file.required ? "red" : "yellow"}>
                  {file.status_label || (file.present || file.exists ? "Present" : "Missing")}
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
                  <p className="break-all text-sm font-bold">{label}</p>
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

        <SettingsCard title="Gene Filters" tone="border-t-purple-400" className="xl:col-span-2">
          <div className="space-y-4 text-sm">
            <div>
              <h3 className="text-xs font-black uppercase tracking-wider text-green-700 dark:text-green-300">Selected SNV ISGLs</h3>
              <div className="mt-2 flex flex-wrap gap-2">
                {(snvFilters.snvlists || []).length ? snvFilters.snvlists.map((name: string) => <StatusPill key={name} tone="green">{name}</StatusPill>) : <p className="text-muted-foreground">No ISGLs selected for this sample.</p>}
              </div>
            </div>
            {omics === "dna" && (
              <div>
                <h3 className="text-xs font-black uppercase tracking-wider text-orange-700 dark:text-orange-300">Selected CNV ISGLs</h3>
                <div className="mt-2 flex flex-wrap gap-2">
                  {(cnvFilters.cnvlists || []).length ? cnvFilters.cnvlists.map((name: string) => <StatusPill key={name} tone="yellow">{name}</StatusPill>) : <p className="text-muted-foreground">No CNV ISGLs selected for this sample.</p>}
                </div>
              </div>
            )}
            {omics === "rna" && (
              <div>
                <h3 className="text-xs font-black uppercase tracking-wider text-teal-700 dark:text-teal-300">Selected Fusion Lists</h3>
                <div className="mt-2 flex flex-wrap gap-2">
                  {(fusionFilters.fusionlists || []).length ? fusionFilters.fusionlists.map((name: string) => <StatusPill key={name} tone="green">{name}</StatusPill>) : <p className="text-muted-foreground">No fusion lists selected for this sample.</p>}
                </div>
              </div>
            )}
            <div>
              <h3 className="text-xs font-black uppercase tracking-wider text-blue-700 dark:text-blue-300">Sample Ad-Hoc Genes</h3>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                {Object.keys(adhoc).length ? Object.entries(adhoc).map(([scope, entry]: [string, any]) => (
                  <div key={scope} className="rounded-xl border border-border bg-background/70 p-2">
                    <p className="text-xs font-bold uppercase text-muted-foreground">{scope}</p>
                    <p className="text-sm font-semibold">{entry?.label || "Ad Hoc"}</p>
                    <p className="text-xs text-muted-foreground">{(entry?.genes || []).length} gene(s)</p>
                  </div>
                )) : <p className="text-muted-foreground">No ad-hoc genes configured.</p>}
              </div>
            </div>
          </div>
        </SettingsCard>

        <SettingsCard title="Filter Thresholds" tone="border-t-blue-400" className="xl:col-span-2">
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {filterRows.map(([label, rowValue]) => (
              <div key={label} className="rounded-xl bg-background/70 p-2">
                <dt className="text-xs text-muted-foreground">{label}</dt>
                <dd className="font-semibold">{displayValue(rowValue)}</dd>
              </div>
            ))}
          </div>
        </SettingsCard>
      </div>

      {verificationSample && (
        <section className="rounded-xl bg-blue-50 px-3 py-2 shadow-md dark:bg-blue-950/20">
          <h2 className="text-base font-semibold uppercase tracking-wide text-foreground">Verification Sample</h2>
          <p className="mt-2 text-sm font-semibold text-yellow-700 dark:text-yellow-300">
            Verification sample used: {verificationSample}
          </p>
        </section>
      )}
    </div>
  )
}
