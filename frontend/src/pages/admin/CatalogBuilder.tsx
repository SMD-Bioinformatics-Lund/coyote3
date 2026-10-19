import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { TextField, PresentationFields } from "./CatalogFields"
import type { Catalog, Category, Workspace } from "./catalog-types"
import { CatalogAnalysisLists } from "./CatalogAnalysisLists"
import { effectiveCatalogEntry } from "./catalog-hierarchy"

export function CatalogBuilder({ catalog, section, entryKey, workspace, onChange }: {
  catalog: Catalog; section: string; entryKey: string; workspace: Workspace
  onChange: (value: Catalog) => void
}) {
  const modality = catalog.modalities[section]
  const entry = modality?.categories[entryKey]
  const updateCategory = (next: Category) => onChange({ ...catalog, modalities: {
    ...catalog.modalities, [section]: { ...modality, categories: { ...modality.categories, [entryKey]: next } },
  } })
  if (!modality) return <div className="space-y-4 p-4">
    <TextField label="Catalog heading" value={catalog.header} onChange={(header) => onChange({ ...catalog, header })} />
    <TextField label="Maintainer" value={catalog.maintainer} onChange={(maintainer) => onChange({ ...catalog, maintainer })} />
    <TextField label="Introduction" multiline value={catalog.description} onChange={(description) => onChange({ ...catalog, description })} />
  </div>
  if (!entry) return <div className="space-y-4 p-4">
    <label className="grid gap-1 type-label">DNA / RNA
      <select aria-label="DNA / RNA" className="paper-inset rounded-lg p-2 type-body" value={modality.omics || ""}
        onChange={(e) => onChange({ ...catalog, modalities: { ...catalog.modalities, [section]: {
          ...modality, omics: (e.target.value || null) as "dna" | "rna" | null,
        } } })}>
        <option value="">Select category</option><option value="dna">DNA</option><option value="rna">RNA</option>
      </select>
    </label>
    <TextField label="Section display name" value={modality.label} onChange={(label) => onChange({
      ...catalog, modalities: { ...catalog.modalities, [section]: { ...modality, label, title: label } },
    })} />
    <TextField label="Section description" multiline value={modality.description} onChange={(description) => onChange({
      ...catalog, modalities: { ...catalog.modalities, [section]: { ...modality, description } },
    })} />
    <PresentationFields value={modality} showHeading={false} presets={{ ...workspace.presets,
      analysis: workspace.presets.analysis_by_omics?.[modality.omics || ""] || workspace.presets.analysis,
    }} onChange={(value) => onChange({ ...catalog, modalities: { ...catalog.modalities, [section]: { ...modality, ...value } } })} />
    <div className="flex flex-wrap gap-2">
      {[-1, 1].map((direction) => <Button key={direction} variant="outline" size="icon-sm"
        aria-label={direction < 0 ? "Move section up" : "Move section down"} title={direction < 0 ? "Move up" : "Move down"}
        onClick={() => {
          const order = [...new Set([...catalog.layout.order, ...Object.keys(catalog.modalities)])]
          const index = order.indexOf(section), target = index + direction
          if (target < 0 || target >= order.length) return
          ;[order[index], order[target]] = [order[target], order[index]]
          onChange({ ...catalog, layout: { order } })
        }}>{direction < 0 ? <ArrowUp /> : <ArrowDown />}</Button>)}
      <Button variant="outline" onClick={() => {
        const key = crypto.randomUUID().replaceAll("-", "_")
        onChange({ ...catalog, modalities: { ...catalog.modalities, [section]: {
          ...modality, categories: { ...modality.categories, [key]: { label: "New entry", gene_lists: [] } },
        } } })
      }}><Plus /> Add entry</Button>
      <Button variant="outline" onClick={() => {
        const modalities = { ...catalog.modalities }; delete modalities[section]
        onChange({ ...catalog, modalities, layout: { order: catalog.layout.order.filter((v) => v !== section) } })
      }}><Trash2 /> Remove section</Button>
    </div>
  </div>
  const effective = effectiveCatalogEntry(modality, entryKey)
  const configurations = workspace.sources.aspcs.filter((v) => v.asp_id === effective.asp_id)
  const genes = entry.gene_lists || []
  const selectedConfig = entry.aspc_id || entry.aspc_ids?.production || ""
  const omics = modality.omics || workspace.sources.asps.find((assay) => assay.asp_id === effective.asp_id)?.category || ""
  const presets = { ...workspace.presets, analysis: workspace.presets.analysis_by_omics?.[omics] || workspace.presets.analysis }
  const validParent = (key: string) => {
    const seen = new Set([entryKey])
    let current: string | null | undefined = key
    while (current) {
      if (seen.has(current)) return false
      seen.add(current)
      current = modality.categories[current]?.parent_key
    }
    return true
  }
  return <div className="space-y-5 p-4">
    <div className="grid gap-3 md:grid-cols-2">
      <label className="grid gap-1 type-label">Parent entry
        <select aria-label="Parent entry" className="paper-inset rounded-lg p-2 type-body" value={entry.parent_key || ""}
          onChange={(e) => updateCategory({ ...entry, parent_key: e.target.value || null })}>
          <option value="">{modality.label || section} (section root)</option>
          {Object.entries(modality.categories).filter(([key]) => validParent(key)).map(([key, value]) =>
            <option key={key} value={key}>{value.label || key}</option>)}
        </select>
      </label>
      <label className="grid gap-1 type-label">Entry type
        <select aria-label="Entry type" className="paper-inset rounded-lg p-2 type-body" value={entry.node_kind || "entry"}
          onChange={(e) => updateCategory({ ...entry, node_kind: e.target.value as "entry" | "folder" })}>
          <option value="folder">Folder (family or group)</option><option value="entry">Assay or subpanel</option>
        </select>
      </label>
    </div>
    <p className="type-body-sm text-muted-foreground">Unspecified details inherit from the immediate parent. Enter a value to replace the inherited value. Preview shows the resolved information.</p>
    <Button variant="outline" onClick={() => {
      const key = crypto.randomUUID().replaceAll("-", "_")
      onChange({ ...catalog, modalities: { ...catalog.modalities, [section]: { ...modality,
        categories: { ...modality.categories, [key]: { label: "New child", parent_key: entryKey } },
      } } })
    }}><Plus /> Add child entry</Button>
    <label className="grid gap-1 type-label">Assay
      <select aria-label="Assay" className="paper-inset rounded-lg p-2 type-body" value={entry.asp_id || ""}
        onChange={(e) => updateCategory({ ...entry, asp_id: e.target.value, aspc_id: null, aspc_ids: {}, subpanel_id: null, gene_lists: [], no_gene_list: [] })}>
        <option value="">{effective.asp_id && !entry.asp_id ? `Inherit: ${effective.asp_id}` : "Select assay"}</option>
        {workspace.sources.asps.filter((v) => !modality.omics || v.category === modality.omics).map((v) => <option key={v.asp_id} value={v.asp_id}>{v.label} ({v.asp_id})</option>)}
      </select>
    </label>
    <label className="grid gap-1 type-label">Assay configuration
      <select aria-label="Assay configuration" className="paper-inset rounded-lg p-2 type-body" value={selectedConfig}
        onChange={(e) => {
          const config = configurations.find((v) => v.aspc_id === e.target.value)
          updateCategory({ ...entry, aspc_id: config?.aspc_id || null,
            aspc_ids: {}, subpanel_id: config?.subpanel_id || null })
        }}>
        <option value="">{effective.aspc_id && !selectedConfig ? `Inherit: ${effective.aspc_id}` : "Select configuration"}</option>
        {configurations.map((v) => <option key={v.aspc_id} value={v.aspc_id}>{v.subpanel_id || "Base"}</option>)}
      </select>
    </label>
    <PresentationFields key={entryKey} value={entry} presets={presets} onChange={(v) => updateCategory({ ...entry, ...v,
      no_gene_list: (entry.no_gene_list || []).filter((analysis) => v.analysis?.includes(analysis)),
      gene_lists: genes.flatMap((gene) => {
        if (!gene.analysis?.length) return [gene]
        const analysis = gene.analysis.filter((item) => v.analysis?.includes(item))
        return analysis.length ? [{ ...gene, analysis }] : []
      }),
    })} />
    <details><summary className="type-label cursor-pointer">Suppress inherited details</summary>
      <p className="type-body-sm text-muted-foreground">Select fields that should remain empty here instead of inheriting a parent value.</p>
      <div className="grid gap-2 md:grid-cols-2">
        {["description", "input_material", "sample_modes", "tat", "clinical_indications", "limitations", "public_notes", "gene_lists", "no_gene_list"].map((field) => <label key={field} className="flex gap-2 type-body-sm">
          <input type="checkbox" checked={entry.clear_fields?.includes(field) || false}
            onChange={(e) => updateCategory({ ...entry,
              [field]: ["description", "tat", "limitations", "public_notes"].includes(field) ? "" : [],
              clear_fields: e.target.checked ? [...(entry.clear_fields || []), field] : (entry.clear_fields || []).filter((v) => v !== field),
            })} />{field.replaceAll("_", " ")}
        </label>)}
      </div>
    </details>
    {!entry.analysis?.length && effective.analysis?.length ? <p className="type-body-sm text-muted-foreground">Inherited analyses: {effective.analysis.join(", ")}. Select analyses above to replace this set.</p> : null}
    <CatalogAnalysisLists key={`${entryKey}:${effective.asp_id || ""}`} entry={effective} sources={workspace.sources}
      onChange={(next) => updateCategory({ ...entry, gene_lists: next.gene_lists, no_gene_list: next.no_gene_list })} />
    <details className="space-y-3 border-t border-border pt-4">
      <summary className="type-body font-semibold cursor-pointer">Selected gene-list descriptions ({genes.length})</summary>
      {genes.map((gene, index) => <details key={index} open className="border-b border-border pb-3">
        <summary className="cursor-pointer type-body font-semibold">{gene.label || "New gene list"}</summary>
        <div className="mt-3 space-y-3">
          <p className="type-meta text-muted-foreground">{gene.isgl_id || gene.key}</p>
          <PresentationFields value={gene} presets={presets} showAnalysis={false} onChange={(next) =>
            updateCategory({ ...entry, gene_lists: genes.map((v, i) => i === index ? { ...v, ...next } : v) })} />
          <Button size="sm" variant="outline" onClick={() => updateCategory({ ...entry, gene_lists: genes.filter((_, i) => i !== index) })}><Trash2 /> Remove gene list</Button>
        </div>
      </details>)}
    </details>
    <details><summary className="type-label cursor-pointer">Database references</summary>
      <dl className="mt-2 grid gap-2 type-body-sm">
        <dt>assay_specific_panels.asp_id</dt><dd>{entry.asp_id || "Not linked"}</dd>
        <dt>asp_configs.aspc_id</dt><dd className="break-all">{selectedConfig || "Not linked"}</dd>
        <dt>Public entry identifier</dt><dd className="break-all">{entry.catalog_id || "Assigned when saved"}</dd>
      </dl>
    </details>
    <Button variant="outline" disabled={Object.values(modality.categories).some((node) => node.parent_key === entryKey)} onClick={() => {
      const categories = { ...modality.categories }; delete categories[entryKey]
      onChange({ ...catalog, modalities: { ...catalog.modalities, [section]: { ...modality, categories } } })
    }}><Trash2 /> Remove entry</Button>
    {Object.values(modality.categories).some((node) => node.parent_key === entryKey) && <p className="type-body-sm text-muted-foreground">Move or remove child entries before removing their parent.</p>}
  </div>
}
