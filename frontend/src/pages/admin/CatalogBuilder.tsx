import { icon } from "@/lib/assets"
import { Button } from "@/components/ui/button"
import { Choices, TextField, PresentationFields } from "./CatalogFields"
import { useState } from "react"
import { CatalogEditableInformation } from "./CatalogEditableInformation"
import type { Catalog, Category, Workspace } from "./catalog-types"
import { CatalogAnalysisLists } from "./CatalogAnalysisLists"
import { effectiveCatalogEntry } from "./catalog-hierarchy"
import { useCatalogDraftPreview } from "./useCatalogDraftPreview"
import { addCatalogChild } from "./catalog-editor-navigation"

export function CatalogBuilder({ catalog, section, entryKey, workspace, onChange, onSelectEntry }: {
  catalog: Catalog; section: string; entryKey: string; workspace: Workspace
  onChange: (value: Catalog) => void
  onSelectEntry: (key: string) => void
}) {
  const [editingAnalysis, setEditingAnalysis] = useState(false)
  const preview = useCatalogDraftPreview(catalog)
  const targetId = entryKey ? `entry:${section}:${entryKey}` : `section:${section}`
  const metadata = new Map((preview.data?.navigation || []).map(node => [node.node_id, node]))
  const offeringIds = new Set((preview.data?.navigation || []).filter(node => {
    const seen = new Set<string>()
    let current: typeof node | undefined = node
    while (current && !seen.has(current.node_id)) {
      if (current.node_id === targetId) return true
      seen.add(current.node_id)
      current = metadata.get(current.parent_id || "")
    }
    return false
  }).flatMap(node => node.offering_id ? [node.offering_id] : []))
  const offerings = preview.data?.offerings.filter(item => !section || offeringIds.has(item.offering_id))
  const modality = catalog.modalities[section]
  const entry = modality?.categories[entryKey]
  const updateCategory = (next: Category) => onChange({ ...catalog, modalities: {
    ...catalog.modalities, [section]: { ...modality, categories: { ...modality.categories, [entryKey]: next } },
  } })
  const addChild = (kind: "entry" | "folder") => {
    const result = addCatalogChild(catalog, { section, entry: entryKey }, kind)
    onChange(result.catalog); onSelectEntry(result.target.entry)
  }
  const structureActions = <section className="surface-panel flex flex-wrap items-center gap-3 p-3" aria-label="Add catalog content">
    <h2 className="type-section-title mr-auto">{entry ? "Add beneath this entry" : "Add to this section"}</h2>
    <Button variant="outline" disabled={editingAnalysis} onClick={() => addChild("folder")}><icon.plus /> Add subsection</Button>
    <Button variant="outline" disabled={editingAnalysis} onClick={() => addChild("entry")}><icon.plus /> {entry ? "Add child entry" : "Add entry"}</Button>
  </section>
  const previewStatus = (preview.issue || preview.pending) && <div className="surface-panel space-y-2 p-3">
    <p role="status" className="type-body-sm text-muted-foreground">{preview.issue || "Updating draft coverage…"}</p>
    {preview.canRetry && <Button variant="outline" size="sm" onClick={preview.retry}>Retry preview</Button>}
  </div>
  if (!modality) return <div className="min-w-0 space-y-4 p-3">
    {previewStatus}
    <CatalogEditableInformation key="introduction" overview="home" value={{
      label: catalog.header, title: catalog.header, description: catalog.description,
    }} effective={{ label: catalog.header, title: catalog.header, description: catalog.description }} editableFields={["title", "description"]}
      presets={workspace.presets} offerings={offerings} onChange={patch => onChange({ ...catalog,
        ...(patch.label !== undefined ? { header: patch.label || "" } : {}),
        ...(patch.description !== undefined ? { description: patch.description || "" } : {}),
      })} />
    <details><summary className="cursor-pointer type-body-sm font-semibold">Catalog settings</summary>
      <div className="mt-3"><TextField label="Maintainer" value={catalog.maintainer}
        onChange={maintainer => onChange({ ...catalog, maintainer })} /></div>
    </details>
  </div>
  if (!entry) return <div className="min-w-0 space-y-4 p-3">
    {structureActions}
    {previewStatus}
    <section className="surface-panel space-y-3 p-4 sm:p-5" aria-label="Section setup">
      <h2 className="type-section-title">Section setup</h2>
      <div className="grid gap-3 md:grid-cols-2">
        <TextField label="Section name" value={modality.label || ""} onChange={label => onChange({ ...catalog,
          modalities: { ...catalog.modalities, [section]: { ...modality, label, title: label } } })} />
        <label className="grid gap-1 type-label">DNA / RNA
          <select aria-label="DNA / RNA" className="form-control rounded-lg p-2 type-body" value={modality.omics || ""}
            onChange={event => onChange({ ...catalog, modalities: { ...catalog.modalities,
              [section]: { ...modality, omics: (event.target.value || null) as "dna" | "rna" | null },
            } })}>
            <option value="">Select category</option><option value="dna">DNA</option><option value="rna">RNA</option>
          </select>
        </label>
      </div>
    </section>
    <CatalogEditableInformation key={section} value={modality} effective={modality}
      overview={modality.label?.toLowerCase() === "dna" || modality.label?.toLowerCase() === "rna" ? modality.omics || undefined : undefined}
      presets={{ ...workspace.presets,
        analysis: workspace.presets.analysis_by_omics?.[modality.omics || ""] || workspace.presets.analysis,
      }} offerings={offerings} onChange={patch => onChange({ ...catalog,
        modalities: { ...catalog.modalities, [section]: { ...modality, ...patch,
          ...(patch.title !== undefined && (modality.omics || Object.values(modality.categories).some(value => value.asp_id))
            ? { label: modality.label } : {}),
        } } })} />
    <details className="surface-panel p-4">
      <summary className="cursor-pointer type-body-sm font-semibold">Section structure and source settings</summary>
      <div className="mt-3 space-y-3">
    <div className="flex flex-wrap gap-2">
      {[-1, 1].map((direction) => <Button key={direction} variant="outline" size="icon-sm"
        aria-label={direction < 0 ? "Move section up" : "Move section down"} title={direction < 0 ? "Move up" : "Move down"}
        onClick={() => {
          const order = [...new Set([...catalog.layout.order, ...Object.keys(catalog.modalities)])]
          const index = order.indexOf(section), target = index + direction
          if (target < 0 || target >= order.length) return
          ;[order[index], order[target]] = [order[target], order[index]]
          onChange({ ...catalog, layout: { order } })
        }}>{direction < 0 ? <icon.arrowUp /> : <icon.arrowDown />}</Button>)}
      <Button variant="outline" onClick={() => {
        const modalities = { ...catalog.modalities }; delete modalities[section]
        onChange({ ...catalog, modalities, layout: { order: catalog.layout.order.filter((v) => v !== section) } })
      }}><icon.trash2 /> Remove section</Button>
    </div>
      </div>
    </details>
  </div>
  const effective = effectiveCatalogEntry(modality, entryKey)
  const configurations = workspace.sources.aspcs.filter((v) => v.asp_id === effective.asp_id)
  const genes = entry.gene_lists || []
  const selectedConfig = entry.aspc_id || entry.aspc_ids?.production || ""
  const diagnosisName = (value: Workspace["sources"]["aspcs"][number]) => value.diagnosis_label
    || (value.diagnosis_id && value.diagnosis_id !== "base" ? value.diagnosis_id : "No diagnosis / General testing")
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
  const updateEntry = (patch: Partial<Category>) => {
    const updated = { ...entry, ...patch,
      ...(entry.node_kind === "folder" && patch.title !== undefined ? { label: entry.label } : {}),
    }
    if (patch.analysis !== undefined && !("gene_lists" in patch) && !("no_gene_list" in patch)) {
      const analyses = patch.analysis.length ? patch.analysis
        : effectiveCatalogEntry({ ...modality, categories: { ...modality.categories, [entryKey]: updated } }, entryKey).analysis || []
      updated.no_gene_list = (entry.no_gene_list || []).filter(analysis => analyses.includes(analysis))
      updated.gene_lists = genes.flatMap(gene => {
        if (!gene.analysis?.length) return [gene]
        const analysis = gene.analysis.filter(item => analyses.includes(item))
        return analysis.length ? [{ ...gene, analysis }] : []
      })
    }
    updateCategory(updated)
  }
  return <div className="min-w-0 space-y-4 p-3">
    {structureActions}
    <fieldset disabled={editingAnalysis} className="surface-panel min-w-0 space-y-4 p-4 sm:p-5" aria-label="Entry setup">
      <h2 className="type-section-title">Entry setup</h2>
      <div className="grid gap-3 lg:grid-cols-3">
        <TextField label="Entry name" value={entry.label || entry.title || ""}
          onChange={label => updateCategory({ ...entry, label, title: label })} />
        <label className="grid gap-1 type-label">Assay
          <select aria-label="Assay" className="form-control rounded-lg p-2 type-body" value={entry.asp_id || ""}
            onChange={event => updateCategory({ ...entry, node_kind: event.target.value ? "entry" : entry.node_kind,
              asp_id: event.target.value, aspc_id: null,
              aspc_ids: {}, diagnosis_id: null, gene_lists: [], no_gene_list: [] })}>
            <option value="">{effective.asp_id && !entry.asp_id ? `Inherit: ${workspace.sources.asps.find(value => value.asp_id === effective.asp_id)?.label || effective.asp_id}` : "Select assay"}</option>
            {workspace.sources.asps.filter(value => !modality.omics || value.category === modality.omics)
              .map(value => <option key={value.asp_id} value={value.asp_id}>{value.label}</option>)}
          </select>
        </label>
        <label className="grid gap-1 type-label">Diagnosis
          <select aria-label="Diagnosis" className="form-control rounded-lg p-2 type-body" value={selectedConfig}
            onChange={event => {
              const configuration = configurations.find(value => value.aspc_id === event.target.value)
              updateCategory({ ...entry, aspc_id: configuration?.aspc_id || null, aspc_ids: {},
                diagnosis_id: configuration?.diagnosis_id || null })
            }}>
            <option value="">{effective.aspc_id && !selectedConfig ? "Inherit parent diagnosis" : "Select diagnosis"}</option>
            {configurations.map(value => <option key={value.aspc_id} value={value.aspc_id}>
              {diagnosisName(value)}{configurations.filter(item => diagnosisName(item) === diagnosisName(value)).length > 1 ? ` (${value.aspc_id})` : ""}
            </option>)}
          </select>
        </label>
      </div>
      <p className="type-meta text-muted-foreground">Choose an assay, then its diagnosis. Gene-list choices below follow the selected assay, diagnosis and analyses.</p>
      <Choices label="Analyses" value={effective.analysis || []} presets={presets.analysis}
        onChange={analysis => updateEntry({ analysis })} />
      <CatalogAnalysisLists key={`${entryKey}:${effective.asp_id || ""}`} entry={effective} sources={workspace.sources}
        onChange={next => updateCategory({ ...entry, gene_lists: next.gene_lists, no_gene_list: next.no_gene_list })} />
    </fieldset>
    <CatalogEditableInformation key={`${section}:${entryKey}`} value={entry} effective={effective}
      parentLabel={modality.categories[entry.parent_key || ""]?.label || modality.label || section}
      presets={presets} offerings={offerings} onAnalysisEditingChange={setEditingAnalysis} onChange={updateEntry} />
    {previewStatus}
    {editingAnalysis && <p className="type-meta text-muted-foreground">Finish or cancel the analysis edit before changing its source links or gene lists.</p>}
    <fieldset disabled={editingAnalysis} className="surface-panel min-w-0 space-y-4 p-4 sm:p-5" aria-label="Entry configuration">
    <h2 className="type-section-title">Additional entry settings</h2>
    <details>
      <summary className="cursor-pointer type-body-sm font-semibold">Entry structure and source settings</summary>
      <div className="mt-3 space-y-4">
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
          <option value="folder">Folder (family or group)</option><option value="entry">Assay or diagnosis</option>
        </select>
      </label>
    </div>
    <p className="type-body-sm text-muted-foreground">Unspecified details inherit from the immediate parent. Enter a value to replace the inherited value. Preview shows the resolved information.</p>
      </div>
    </details>
    <details><summary className="type-label cursor-pointer">Suppress inherited details</summary>
      <p className="type-body-sm text-muted-foreground">Select fields that should remain empty here instead of inheriting a parent value.</p>
      <div className="grid gap-2 md:grid-cols-2">
        {["description", "input_material", "sample_modes", "tat", "clinical_indications", "limitations", "public_notes", "gene_lists", "no_gene_list", "price", "pricing_message", "methodology", "ordering_information", "report_deliverables"].map((field) => <label key={field} className="flex gap-2 type-body-sm">
          <input type="checkbox" checked={entry.clear_fields?.includes(field) || false}
            onChange={(e) => updateCategory({ ...entry,
              [field]: field === "price" ? null : ["description", "tat", "limitations", "public_notes", "pricing_message", "methodology", "ordering_information"].includes(field) ? "" : [],
              clear_fields: e.target.checked ? [...(entry.clear_fields || []), field] : (entry.clear_fields || []).filter((v) => v !== field),
            })} />{field.replaceAll("_", " ")}
        </label>)}
      </div>
    </details>
    <details className="space-y-3 border-t border-border pt-4">
      <summary className="type-body font-semibold cursor-pointer">Selected gene-list descriptions ({genes.length})</summary>
      {genes.map((gene, index) => <details key={index} open className="border-b border-border pb-3">
        <summary className="cursor-pointer type-body font-semibold">{gene.label || "New gene list"}</summary>
        <div className="mt-3 space-y-3">
          <p className="type-meta text-muted-foreground">{gene.isgl_id || gene.key}</p>
          <PresentationFields value={gene} presets={presets} showAnalysis={false} onChange={(next) =>
            updateCategory({ ...entry, gene_lists: genes.map((v, i) => i === index ? { ...v, ...next } : v) })} />
          <Button size="sm" variant="outline" onClick={() => updateCategory({ ...entry, gene_lists: genes.filter((_, i) => i !== index) })}><icon.trash2 /> Remove gene list</Button>
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
    }}><icon.trash2 /> Remove entry</Button>
    {Object.values(modality.categories).some((node) => node.parent_key === entryKey) && <p className="type-body-sm text-muted-foreground">Move or remove child entries before removing their parent.</p>}
    </fieldset>
  </div>
}
