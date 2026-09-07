import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { TextField, PresentationFields } from "./CatalogFields"
import type { Catalog, Category, Workspace } from "./catalog-types"

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
    <TextField label="Section display name" value={modality.label} onChange={(label) => onChange({
      ...catalog, modalities: { ...catalog.modalities, [section]: { ...modality, label, title: label } },
    })} />
    <TextField label="Section description" multiline value={modality.description} onChange={(description) => onChange({
      ...catalog, modalities: { ...catalog.modalities, [section]: { ...modality, description } },
    })} />
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
  const configurations = workspace.sources.aspcs.filter((v) => v.asp_id === entry.asp_id)
  const genes = entry.gene_lists || []
  const selectedConfig = entry.aspc_id || entry.aspc_ids?.production || ""
  return <div className="space-y-5 p-4">
    <label className="grid gap-1 type-label">Assay
      <select aria-label="Assay" className="paper-inset rounded-lg p-2 type-body" value={entry.asp_id || ""}
        onChange={(e) => updateCategory({ ...entry, asp_id: e.target.value, aspc_id: null, aspc_ids: {}, subpanel_id: null })}>
        <option value="">Select assay</option>
        {workspace.sources.asps.map((v) => <option key={v.asp_id} value={v.asp_id}>{v.label} ({v.asp_id})</option>)}
      </select>
    </label>
    <label className="grid gap-1 type-label">Assay configuration
      <select aria-label="Assay configuration" className="paper-inset rounded-lg p-2 type-body" value={selectedConfig}
        onChange={(e) => {
          const config = configurations.find((v) => v.aspc_id === e.target.value)
          updateCategory({ ...entry, aspc_id: config?.aspc_id || null,
            aspc_ids: {}, subpanel_id: config?.subpanel_id || null })
        }}>
        <option value="">Select configuration</option>
        {configurations.map((v) => <option key={v.aspc_id} value={v.aspc_id}>{v.subpanel_id || "Base"}</option>)}
      </select>
    </label>
    <PresentationFields key={entryKey} value={entry} presets={workspace.presets} onChange={(v) => updateCategory({ ...entry, ...v })} />
    <section className="space-y-3 border-t border-border pt-4">
      <div className="flex items-center justify-between gap-2"><h3 className="type-body font-semibold">Gene lists and diagnoses</h3>
        <Button size="sm" variant="outline" onClick={() => updateCategory({ ...entry, gene_lists: [...genes, {}] })}><Plus /> Add gene list</Button></div>
      {genes.map((gene, index) => <details key={index} open className="border-b border-border pb-3">
        <summary className="cursor-pointer type-body font-semibold">{gene.label || "New gene list"}</summary>
        <div className="mt-3 space-y-3">
          <label className="grid gap-1 type-label">Gene list
            <select className="paper-inset rounded-lg p-2 type-body" value={gene.isgl_id || gene.key || ""}
              onChange={(e) => {
                const source = workspace.sources.gene_lists.find((v) => v.isgl_id === e.target.value)
                updateCategory({ ...entry, gene_lists: genes.map((v, i) => i === index
                  ? { ...gene, isgl_id: e.target.value, key: e.target.value, label: source?.label || "" } : v) })
              }}>
              <option value="">Select gene list</option>
              {workspace.sources.gene_lists.map((v) => <option key={v.isgl_id} value={v.isgl_id}>{v.label} ({v.isgl_id})</option>)}
            </select>
          </label>
          <PresentationFields value={gene} presets={workspace.presets} onChange={(next) =>
            updateCategory({ ...entry, gene_lists: genes.map((v, i) => i === index ? { ...v, ...next } : v) })} />
          <Button size="sm" variant="outline" onClick={() => updateCategory({ ...entry, gene_lists: genes.filter((_, i) => i !== index) })}><Trash2 /> Remove gene list</Button>
        </div>
      </details>)}
    </section>
    <details><summary className="type-label cursor-pointer">Database references</summary>
      <dl className="mt-2 grid gap-2 type-body-sm">
        <dt>assay_specific_panels.asp_id</dt><dd>{entry.asp_id || "Not linked"}</dd>
        <dt>asp_configs.aspc_id</dt><dd className="break-all">{selectedConfig || "Not linked"}</dd>
        <dt>Public entry identifier</dt><dd className="break-all">{entry.catalog_id || "Assigned when saved"}</dd>
      </dl>
    </details>
    <Button variant="outline" onClick={() => {
      const categories = { ...modality.categories }; delete categories[entryKey]
      onChange({ ...catalog, modalities: { ...catalog.modalities, [section]: { ...modality, categories } } })
    }}><Trash2 /> Remove entry</Button>
  </div>
}
