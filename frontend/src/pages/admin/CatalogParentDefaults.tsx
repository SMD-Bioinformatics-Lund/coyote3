import { useState } from "react"
import { Button } from "@/components/ui/button"
import { CatalogInformation } from "../catalog/CatalogInformation"
import type { CatalogEditorNode, CatalogEditorTarget } from "./catalog-editor-navigation"
import type { Catalog } from "./catalog-types"
import { useCatalogDraftPreview } from "./useCatalogDraftPreview"

/** Show a virtual public level and explicitly create editable defaults within its source section. */
export function CatalogParentDefaults({ node, catalog, onAdd, onSelect, onAddChild }: {
  node: CatalogEditorNode; catalog: Catalog; onAdd: () => void
  onSelect: (target: CatalogEditorTarget) => void
  onAddChild: (section: string, kind: "entry" | "folder") => void
}) {
  const sections = [...new Set(node.offerings.map(item => item.section))]
  const [sourceSection, setSourceSection] = useState(sections.length === 1 ? sections[0] : "")
  const preview = useCatalogDraftPreview(catalog)
  const data = preview.data
  const selectedIds = new Set(node.offerings.flatMap(service => {
    const preview = data?.navigation.find(item => item.node_id === `entry:${service.section}:${service.entry}`)
    return preview?.offering_id ? [preview.offering_id] : []
  }))
  return <div className="min-w-0 space-y-4 p-3">
    <section className="surface-panel flex flex-wrap items-center gap-3 p-3" aria-label="Add catalog content">
      <h2 className="type-section-title mr-auto">Add beneath {node.label}</h2>
      {sections.length > 1 && <label className="grid gap-1 type-label">Source section
        <select aria-label="Source section" value={sourceSection} className="form-control rounded-lg p-2 type-body"
          onChange={event => setSourceSection(event.target.value)}>
          <option value="">Select source section</option>
          {sections.map(section => <option key={section} value={section}>{catalog.modalities[section].label || section}</option>)}
        </select>
      </label>}
      <Button variant="outline" disabled={!sourceSection} onClick={() => onAddChild(sourceSection, "folder")}>Add subsection</Button>
      <Button variant="outline" disabled={!sourceSection} onClick={() => onAddChild(sourceSection, "entry")}>Add entry</Button>
    </section>
    <CatalogInformation information={node} overview={node.level === "modality" ? node.offerings[0]?.modality : undefined}
      offerings={data?.offerings.filter(item => selectedIds.has(item.offering_id))} />
    <section className="surface-panel space-y-3 p-4" aria-label="Shared defaults">
      <h2 className="type-section-title">Shared defaults</h2>
      {sections.length === 1 && node.level !== "modality" ? <>
        <p className="type-body-sm text-muted-foreground">Add defaults for this level to edit its information in place. Existing entry settings and source links are retained.</p>
        <Button onClick={onAdd}>Add shared defaults</Button>
      </> : <>
        <p className="type-body-sm text-muted-foreground">This overview combines source sections. Edit their existing defaults separately, or select a diagnosis to edit its service information.</p>
        <div className="flex flex-wrap gap-2">{sections.map(section => <Button key={section} variant="outline"
          onClick={() => onSelect({ section, entry: "" })}>Edit {catalog.modalities[section].label || section} defaults</Button>)}</div>
      </>}
      {preview.issue && <p role="status" className="type-meta text-muted-foreground">{preview.issue}</p>}
      {preview.canRetry && <Button variant="outline" size="sm" onClick={preview.retry}>Retry preview</Button>}
    </section>
    {node.level === "diagnosis" && <section className="surface-panel space-y-3 p-4">
      <h2 className="type-section-title">Individual assay information</h2>
      <div className="flex flex-wrap gap-2">{node.offerings.map(service => {
        const entry = catalog.modalities[service.section].categories[service.entry]
        return <Button key={service.offering_id} variant="outline" onClick={() => onSelect(service)}>{entry.title || entry.label || service.entry}</Button>
      })}</div>
    </section>}
  </div>
}
