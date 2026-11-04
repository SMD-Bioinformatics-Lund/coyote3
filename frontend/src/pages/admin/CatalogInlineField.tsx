import { useEffect, useRef, useState, type ReactNode } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { icon } from "@/lib/assets"
import type { CatalogEditableField } from "../catalog/CatalogInformation"
import { Choices, TextField, Turnaround } from "./CatalogFields"
import { CatalogOfferingFields } from "./CatalogOfferingFields"
import type { Category, Presentation, Workspace } from "./catalog-types"

const labels: Record<CatalogEditableField, string> = {
  title: "Display name", subheading: "Subheading", description: "Description", price: "Price",
  tat: "Turnaround", analysis: "Analyses", input_material: "Input material", sample_modes: "Sample modes",
  report_deliverables: "Report deliverables", clinical_indications: "Clinical indications",
  methodology: "Methodology", limitations: "Limitations", ordering_information: "Ordering information", public_notes: "Public notes",
}

/** Edit one displayed field in the draft; Cancel restores only that field's previous value. */
export function CatalogInlineField({ field, value, effective, parentLabel, suppressed = false,
  presets, onChange, onInherit, onEditingChange, children }: {
  field: CatalogEditableField; value: Category; effective: Presentation; parentLabel?: string
  suppressed?: boolean; presets: Workspace["presets"]; onChange: (patch: Partial<Category>) => void
  onInherit?: () => void; children: ReactNode
  onEditingChange?: (editing: boolean) => void
}) {
  const [before, setBefore] = useState<Partial<Category> | null>(null)
  const [buffer, setBuffer] = useState<Presentation>({})
  const editor = useRef<HTMLDivElement>(null)
  const open = before !== null
  const keys: (keyof Presentation)[] = field === "title" ? ["label", "title"]
    : field === "price" ? ["price", "pricing_message"] : [field]
  const snapshot = () => Object.fromEntries((field === "analysis" ? [...keys, "gene_lists", "no_gene_list"] as (keyof Category)[] : keys)
    .map(key => [key, value[key]])) as Partial<Category>
  const patch = (next: Presentation) => {
    const update = Object.fromEntries(keys.map(key => [key, next[key]]))
    setBuffer(previous => ({ ...previous, ...update }))
    onChange(update)
  }
  const local = field === "title" ? value.title || value.label : field === "price" ? value.price || value.pricing_message : value[field]
  const resolved = field === "title" ? effective.title || effective.label : field === "price"
    ? effective.price || effective.pricing_message : effective[field]
  const inherited = parentLabel && !suppressed && resolved != null && resolved !== ""
    && (!Array.isArray(resolved) || resolved.length > 0)
    && (local == null || local === "" || Array.isArray(local) && !local.length)
  const label = labels[field]
  const shown = open ? buffer : effective
  useEffect(() => {
    if (open) editor.current?.querySelector<HTMLElement>("input, textarea, [contenteditable=true], select")?.focus()
  }, [open])
  const close = () => { setBefore(null); onEditingChange?.(false) }
  const cancel = () => { if (before) onChange(before); close() }
  const invalidPrice = field === "price" && shown.price && (!/^\d+(?:\.\d{1,2})?$/.test(shown.price.amount)
    || !/^[A-Z]{3}$/.test(shown.price.currency))
  const duration = /^([1-9]\d*)(?:-([1-9]\d*))? (?:days?|weeks?|months?|years?)$/.exec(shown.tat || "")
  const invalidTat = field === "tat" && shown.tat && (!duration || duration[2] && Number(duration[2]) < Number(duration[1]))
  return <div className="min-w-0 space-y-2" ref={editor} onKeyDown={event => {
    if (open && event.key === "Escape") { event.stopPropagation(); cancel() }
  }}>
    {!open ? <div className="flex min-w-0 items-start justify-between gap-3">
      <div className="min-w-0 flex-1">{children}
        {inherited && <Badge variant="outline" className="mt-1 max-w-full whitespace-normal break-words">Inherited from {parentLabel}</Badge>}
        {suppressed && !local && <Badge variant="outline" className="mt-1">Intentionally empty</Badge>}
      </div>
      <Button size="icon-sm" variant="outline" aria-label={`Edit ${label.toLowerCase()}`}
        title={`Edit ${label.toLowerCase()}`} onClick={() => { setBuffer(effective); setBefore(snapshot()); onEditingChange?.(true) }}><icon.edit className="size-3.5" /></Button>
    </div> : <div className="paper-inset min-w-0 space-y-3 rounded-lg p-3" role="group" aria-label={`Editing ${label.toLowerCase()}`}>
      {field === "price" ? <CatalogOfferingFields value={shown} onChange={patch} />
        : field === "tat" ? <Turnaround key={field} value={shown.tat} onChange={tat => patch({ tat })} />
        : field === "analysis" ? <Choices label="Analysis" value={shown.analysis} presets={presets.analysis} onChange={analysis => patch({ analysis })} />
        : field === "input_material" ? <Choices label="Input material" value={shown.input_material} presets={presets.input_material} custom onChange={input_material => patch({ input_material })} />
        : field === "sample_modes" ? <Choices label="Sample modes" value={shown.sample_modes} presets={presets.sample_modes} onChange={sample_modes => patch({ sample_modes })} />
        : field === "clinical_indications" ? <Choices label="Clinical indications" value={shown.clinical_indications} presets={[]} custom onChange={clinical_indications => patch({ clinical_indications })} />
        : field === "report_deliverables" ? <label className="grid gap-2 type-label">Report deliverables (one per line)
          <textarea aria-label="Report deliverables (one per line)" className="form-control min-h-24 w-full rounded-lg p-2 type-body"
            value={(shown.report_deliverables || []).join("\n")} onChange={event => patch({ report_deliverables: event.target.value.split("\n") })} />
        </label>
        : field === "title" ? <label className="grid gap-2 type-label">Display name<Input value={shown.title || shown.label || ""} onChange={event => patch({ label: event.target.value, title: event.target.value })} /></label>
        : <TextField label={label} multiline={field !== "subheading"} value={shown[field] as string | undefined}
          onChange={text => patch({ [field]: text })} />}
      {(invalidPrice || invalidTat) && <p role="alert" className="type-body-sm text-destructive">{invalidPrice
        ? "Enter a nonnegative amount with up to two decimal places and a three-letter currency."
        : "Enter a positive turnaround, such as 7-10 days."}</p>}
      <div className="flex flex-wrap gap-2">
        <Button size="sm" disabled={Boolean(invalidPrice || invalidTat)} onClick={() => {
          if (field === "report_deliverables") patch({ report_deliverables: shown.report_deliverables?.map(item => item.trim()).filter(Boolean) })
          close()
        }}>Done</Button>
        <Button size="sm" variant="outline" onClick={cancel}>Cancel field edit</Button>
        {onInherit && <Button size="sm" variant="outline" onClick={() => { onInherit(); close() }}>Use parent value</Button>}
      </div>
      <p className="type-meta text-muted-foreground">Changes remain in this draft until you save it.</p>
    </div>}
  </div>
}
