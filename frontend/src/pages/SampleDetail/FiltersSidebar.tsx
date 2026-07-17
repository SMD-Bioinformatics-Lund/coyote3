import { useEffect, useMemo, useState } from "react"
import type { ReactNode } from "react"
import { ChevronLeft, ChevronRight, Filter, RotateCcw, Save } from "lucide-react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import type { QueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { activeFilterSectionForTab, mergeSampleFilterSection, sampleFilterSection } from "@/lib/sample-shape"
import { notifyActionError, notifySuccess } from "@/lib/notifications"

interface FiltersSidebarProps {
  sampleId: string
  sample: any
  context?: any
  activeTab?: string
}

const consequences = [
  ["vep_splicing", "Splicing"],
  ["vep_stop_gained", "Stop gained"],
  ["vep_stop_lost", "Stop lost"],
  ["vep_start_lost", "Start lost"],
  ["vep_frameshift", "Frameshift"],
  ["vep_inframe_indel", "Inframe indel"],
  ["vep_missense", "Missense"],
  ["vep_other_coding", "Other coding"],
  ["vep_synonymous", "Synonymous"],
  ["vep_UTR", "UTR"],
  ["vep_non_coding", "Non-coding"],
  ["vep_intronic", "Intronic"],
  ["vep_intergenic", "Intergenic"],
  ["vep_regulatory", "Regulatory"],
  ["vep_feature_elon_trunc", "Feature elongation/truncation"],
  ["vep_transcript_structure", "Transcript structure"],
  ["vep_miRNA", "miRNA"],
  ["vep_NMD", "NMD"],
] as const

const cnvEffects = [
  ["loss", "Loss"],
  ["gain", "Gain"],
] as const

const fusionEffects = [
  ["in-frame", "In-frame"],
  ["out-of-frame", "Out-of-frame"],
] as const

const fusionCallers = [
  ["arriba", "Arriba"],
  ["fusioncatcher", "FusionCatcher"],
  ["starfusion", "STAR-Fusion"],
] as const

function optionLabel(option: any) {
  return option?.display_name || option?.displayname || option?.name || option?.label || option?.isgl_id || option?.id || option?._id || String(option)
}

function optionId(option: any) {
  return String(option?.id || option?.isgl_id || option?._id || option?.name || option?.display_name || option)
}

function includesType(option: any, type: string) {
  const listTypes = Array.isArray(option?.list_types) ? option.list_types : []
  const rawTypes = Array.isArray(option?.list_type) ? option.list_type : [option?.list_type]
  const value = [...listTypes, ...rawTypes, option?.type, option?.category, option?.name]
    .filter(Boolean)
    .join(" ")
    .toLowerCase()
  return value.includes(type)
}

function invalidateSampleQueries(queryClient: QueryClient, sampleId: string) {
  for (const key of [
    "sample",
    "sample-variants",
    "sample-cnvs",
    "sample-fusions",
    "sample-translocations",
    "sample-coverage",
    "sample-genelists",
    "sample-effective-genes",
    "report-preview",
  ]) {
    queryClient.invalidateQueries({ queryKey: [key, sampleId] })
  }
  queryClient.invalidateQueries({ queryKey: ["samples"] })
}

function activeTableQueryKey(activeTab: string, sampleId: string) {
  const tableKeys: Record<string, string> = {
    snvs: "sample-variants",
    cnvs: "sample-cnvs",
    fusions: "sample-fusions",
    translocations: "sample-translocations",
  }
  const key = tableKeys[activeTab]
  return key ? [key, sampleId] : null
}

async function refetchActiveTable(queryClient: QueryClient, activeTab: string, sampleId: string) {
  const queryKey = activeTableQueryKey(activeTab, sampleId)
  if (!queryKey) return
  await queryClient.refetchQueries({ queryKey, type: "active" })
}

function FilterInput({
  label,
  value,
  step,
  onChange,
}: {
  label: string
  value: any
  step?: string
  onChange: (value: number) => void
}) {
  return (
    <label className="space-y-1">
      <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">{label}</span>
      <input
        type="number"
        step={step}
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value === "" ? "" as any : Number(event.target.value))}
        className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-xs outline-none focus:ring-2 focus:ring-primary/35"
      />
    </label>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-border bg-background/55 p-2.5">
      <h4 className="mb-2 flex items-center gap-1.5 text-xs font-black uppercase tracking-wider text-foreground">
        <Filter className="h-3.5 w-3.5 text-primary" />
        {title}
      </h4>
      <div className="space-y-2">{children}</div>
    </section>
  )
}

function CheckboxList({
  options,
  values,
  onChange,
  empty = "No configured lists.",
}: {
  options: any[]
  values: string[]
  onChange: (values: string[]) => void
  empty?: string
}) {
  if (!options.length) {
    return <p className="rounded-md border border-dashed border-border p-2 text-xs text-muted-foreground">{empty}</p>
  }
  return (
    <div className="max-h-44 space-y-1 overflow-y-auto pr-1">
      {options.map((option) => {
        const id = optionId(option)
        return (
          <label key={id} className="flex cursor-pointer items-start gap-2 rounded-md px-1.5 py-1 text-xs hover:bg-muted/70">
            <input
              type="checkbox"
              checked={values.includes(id)}
              onChange={(event) => onChange(event.target.checked ? [...values, id] : values.filter((value) => value !== id))}
              className="mt-0.5 rounded border-border text-primary focus:ring-primary"
            />
            <span className="min-w-0 truncate" title={optionLabel(option)}>{optionLabel(option)}</span>
          </label>
        )
      })}
    </div>
  )
}

export function FiltersSidebar({ sampleId, sample, context, activeTab = "overview" }: FiltersSidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(true)
  const activeSection = activeFilterSectionForTab(activeTab)
  const sampleName = String(sample?.name || sample?.case_id || sampleId)
  const [filters, setFilters] = useState(activeSection ? sampleFilterSection(sample, activeSection) : {})
  const queryClient = useQueryClient()

  useEffect(() => {
    setFilters(activeSection ? sampleFilterSection(sample, activeSection) : {})
  }, [activeSection, sample])

  const listOptions = useMemo(() => {
    const all = [
      ...(context?.assay_panels || []),
      ...(context?.panel_options || []),
      ...(context?.genelist_options || []),
      ...(context?.sample?.assay_panels || []),
    ]
    const fusion = [...(context?.fusionlist_options || []), ...all.filter((option) => includesType(option, "fusion"))]
    const cnv = [...(context?.cnvlist_options || []), ...all.filter((option) => includesType(option, "cnv"))]
    const snv = [...(context?.snv_genelist_options || []), ...all.filter((option) => includesType(option, "snv"))]
    const unique = (items: any[]) => Array.from(new Map(items.map((item) => [optionId(item), item])).values())
    return { snv: unique(snv), cnv: unique(cnv), fusion: unique(fusion) }
  }, [context])

  const updateFilters = useMutation({
    mutationFn: (newFilters: any) => {
      const payload = activeSection ? mergeSampleFilterSection(sample, activeSection, newFilters) : newFilters
      return api.put(`/samples/${sampleId}/filters`, { filters: payload }).then((res) => res.data)
    },
    onSuccess: async () => {
      invalidateSampleQueries(queryClient, sampleId)
      await refetchActiveTable(queryClient, activeTab, sampleId)
      notifySuccess("Filters applied", `${activeTab || "Sample"} filters were saved for ${sampleName}.`, "Sample filters", {
        type: "sample",
        id: sampleId,
        name: sampleName,
        sampleName,
      })
    },
    onError: (error) => {
      notifyActionError("Unable to apply filters", error, "Sample filters", {
        type: "sample",
        id: sampleId,
        name: sampleName,
        sampleName,
      })
    },
  })

  const resetFilters = useMutation({
    mutationFn: () => api.delete(`/samples/${sampleId}/filters`).then((res) => res.data),
    onSuccess: async () => {
      invalidateSampleQueries(queryClient, sampleId)
      await refetchActiveTable(queryClient, activeTab, sampleId)
      notifySuccess("Filters reset", `Default assay configuration filters were restored for ${sampleName}.`, "Sample filters", {
        type: "sample",
        id: sampleId,
        name: sampleName,
        sampleName,
      })
    },
    onError: (error) => {
      notifyActionError("Unable to reset filters", error, "Sample filters", {
        type: "sample",
        id: sampleId,
        name: sampleName,
        sampleName,
      })
    },
  })

  const setValue = (key: string, value: any) => setFilters((current: any) => ({ ...current, [key]: value }))
  const values = (key: string) => Array.isArray(filters[key]) ? filters[key].map(String) : []
  const consequenceValues = Array.isArray(filters.vep_consequences) ? filters.vep_consequences.map(String) : []

  if (isCollapsed) {
    return (
      <aside className="flex h-full w-8 shrink-0 flex-col items-center rounded-lg border border-primary/10 bg-card/95 py-2 shadow-sm transition-[width] duration-150 ease-out">
        <button onClick={() => setIsCollapsed(false)} className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground" title="Expand filters">
          <ChevronLeft className="h-4 w-4" />
        </button>
        <span className="mt-8 text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground" style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}>
          {activeTab} filters
        </span>
      </aside>
    )
  }

  return (
    <aside className="flex h-full w-60 shrink-0 flex-col overflow-hidden rounded-lg border border-primary/10 bg-card/95 shadow-sm transition-[width] duration-150 ease-out">
      <div className="flex items-center justify-between border-b border-primary/10 bg-gradient-to-r from-dna/10 via-card/80 to-rna/10 px-3 py-2">
        <div>
          <h3 className="text-sm font-black">Filters</h3>
          <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">{activeTab}</p>
        </div>
        <button onClick={() => setIsCollapsed(true)} className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground" title="Collapse filters">
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-2.5 scrollbar-thin scrollbar-thumb-border">
        {activeTab === "snvs" && (
          <>
            <Section title="Small Variant Thresholds">
              <FilterInput label="Min depth" value={filters.min_depth} onChange={(value) => setValue("min_depth", value)} />
              <FilterInput label="Min alt reads" value={filters.min_alt_reads} onChange={(value) => setValue("min_alt_reads", value)} />
              <FilterInput label="Min VAF" step="0.001" value={filters.min_freq} onChange={(value) => setValue("min_freq", value)} />
              <FilterInput label="Max VAF" step="0.001" value={filters.max_freq} onChange={(value) => setValue("max_freq", value)} />
              <FilterInput label="Max normal VAF" step="0.001" value={filters.max_control_freq} onChange={(value) => setValue("max_control_freq", value)} />
              <FilterInput label="Max population freq" step="0.001" value={filters.max_popfreq} onChange={(value) => setValue("max_popfreq", value)} />
            </Section>
            <Section title="Consequences">
              <div className="max-h-56 space-y-1 overflow-y-auto pr-1">
                {consequences.map(([id, label]) => (
                  <label key={id} className="flex cursor-pointer items-center gap-2 rounded-md px-1.5 py-1 text-xs hover:bg-muted/70">
                    <input
                      type="checkbox"
                      checked={consequenceValues.includes(id.replace(/^vep_/, ""))}
                      onChange={(event) => {
                        const value = id.replace(/^vep_/, "")
                        setValue(
                          "vep_consequences",
                          event.target.checked
                            ? Array.from(new Set([...consequenceValues, value]))
                            : consequenceValues.filter((item: string) => item !== value),
                        )
                      }}
                    />
                    {label}
                  </label>
                ))}
              </div>
            </Section>
            <Section title="SNV Gene Lists">
              <CheckboxList options={listOptions.snv} values={values("snvlists")} onChange={(next) => setValue("snvlists", next)} />
            </Section>
          </>
        )}

        {activeTab === "cnvs" && (
          <>
            <Section title="CNV Thresholds">
              <FilterInput label="Min size" value={filters.min_cnv_size} onChange={(value) => setValue("min_cnv_size", value)} />
              <FilterInput label="Max size" value={filters.max_cnv_size} onChange={(value) => setValue("max_cnv_size", value)} />
              <FilterInput label="Gain cutoff" step="0.01" value={filters.cnv_gain_cutoff} onChange={(value) => setValue("cnv_gain_cutoff", value)} />
              <FilterInput label="Loss cutoff" step="0.01" value={filters.cnv_loss_cutoff} onChange={(value) => setValue("cnv_loss_cutoff", value)} />
            </Section>
            <Section title="CNV Gene Lists">
              <CheckboxList options={listOptions.cnv} values={values("cnvlists")} onChange={(next) => setValue("cnvlists", next)} />
            </Section>
            <Section title="CNV Effects">
              <CheckboxList options={cnvEffects.map(([id, label]) => ({ id, label }))} values={values("cnveffects")} onChange={(next) => setValue("cnveffects", next)} />
            </Section>
          </>
        )}

        {activeTab === "fusions" && (
          <>
            <Section title="Fusion Evidence">
              <FilterInput label="Min spanning pairs" value={filters.min_spanning_pairs} onChange={(value) => setValue("min_spanning_pairs", value)} />
              <FilterInput label="Min spanning reads" value={filters.min_spanning_reads} onChange={(value) => setValue("min_spanning_reads", value)} />
            </Section>
            <Section title="Fusion Lists">
              <CheckboxList options={listOptions.fusion} values={values("fusionlists")} onChange={(next) => setValue("fusionlists", next)} />
            </Section>
            <Section title="Callers">
              <CheckboxList options={fusionCallers.map(([id, label]) => ({ id, label }))} values={values("fusion_callers")} onChange={(next) => setValue("fusion_callers", next)} />
            </Section>
            <Section title="Fusion Effects">
              <CheckboxList options={fusionEffects.map(([id, label]) => ({ id, label }))} values={values("fusion_effects")} onChange={(next) => setValue("fusion_effects", next)} />
            </Section>
          </>
        )}

        {activeTab === "translocations" && (
          <Section title="Translocation Filters">
            <p className="text-xs text-muted-foreground">Historical translocation controls are action-oriented. Status, tier, report, and FP actions are available in the table toolbar and row actions.</p>
          </Section>
        )}
      </div>

      <div className="flex gap-2 border-t border-primary/10 bg-muted/25 p-2.5">
        <button
          onClick={() => resetFilters.mutate()}
          disabled={resetFilters.isPending || updateFilters.isPending}
          className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-background text-muted-foreground hover:bg-muted disabled:opacity-50"
          title="Reset filters"
        >
          {resetFilters.isPending ? <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" /> : <RotateCcw className="h-4 w-4" />}
        </button>
        <button
          onClick={() => updateFilters.mutate(filters)}
          disabled={updateFilters.isPending || resetFilters.isPending}
          className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg bg-primary px-3 py-1.5 text-xs font-black text-primary-foreground shadow-sm hover:bg-primary/90 disabled:opacity-50"
        >
          {updateFilters.isPending ? <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary-foreground border-t-transparent" /> : <Save className="h-4 w-4" />}
          Apply
        </button>
      </div>
    </aside>
  )
}
