import { useEffect, useMemo, useState, type ReactNode } from "react"
import { createPortal } from "react-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Activity, ChevronDown, Save, Search, Trash2, X } from "lucide-react"
import { api } from "@/lib/api"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { sampleFilterSection } from "@/lib/sample-shape"

function geneInputCount(value: string) {
  return value.split(/[,\\s]+/).map((item) => item.trim()).filter(Boolean).length
}

export function SettingsCard({ title, tone: _tone, children, className = "" }: { title: string; tone: string; children: ReactNode; className?: string }) {
  return (
    <section className={`glass-card p-3 ${className}`}>
      <h2 className="mb-2.5 text-xs font-black uppercase tracking-wide text-foreground">{title}</h2>
      {children}
    </section>
  )
}

function targetOptions(sample: any) {
  const omics = String(sample?.omics_layer || "").toLowerCase()
  return omics === "rna"
    ? [{ value: "fusion", label: "Fusion lists" }]
    : [
        { value: "snv", label: "SNV gene lists" },
        { value: "cnv", label: "CNV gene lists" },
        { value: "translocation", label: "DNA fusion / translocation lists" },
      ]
}

function filterKeyForTarget(target: string) {
  if (target === "cnv") return "cnvlists"
  if (target === "fusion" || target === "translocation") return "fusionlists"
  return "snvlists"
}

export function SampleGeneSettings({ sampleId, sample }: { sampleId: string; sample: any }) {
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
      translocation: [["sample-translocations", sampleId], ["translocations", sampleId]],
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
