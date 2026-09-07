import { useState } from "react"
import { Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { Presentation } from "./catalog-types"

export function TextField({ label, value, onChange, multiline = false }: {
  label: string; value?: string | null; onChange: (value: string) => void; multiline?: boolean
}) {
  return <label className="grid gap-1 type-label">{label}{multiline
    ? <textarea className="paper-inset min-h-24 w-full rounded-lg p-2 type-body" value={value || ""} onChange={(e) => onChange(e.target.value)} />
    : <Input value={value || ""} onChange={(e) => onChange(e.target.value)} />}</label>
}

export function Choices({ label, value = [], presets, custom = false, onChange }: {
  label: string; value?: string[]; presets: string[]; custom?: boolean; onChange: (value: string[]) => void
}) {
  const [text, setText] = useState("")
  const add = () => {
    if (text.trim()) onChange([...new Set([...value, text.trim()])])
    setText("")
  }
  return <div className="space-y-2">
    <p className="type-label">{label}</p>
    <div className="flex flex-wrap gap-1.5" role="group" aria-label={label}>
      {[...new Set([...presets, ...value])].map((item) => <label key={item}
        className="flex cursor-pointer items-center gap-1.5 rounded-full border border-border px-2.5 py-1 type-body-sm has-checked:border-primary has-checked:bg-primary/10">
        <input type="checkbox" checked={value.includes(item)}
          onChange={() => onChange(value.includes(item) ? value.filter((v) => v !== item) : [...value, item])} />
        {item}
      </label>)}
    </div>
    {custom && <div className="flex max-w-sm gap-2"><Input aria-label={`New ${label.toLowerCase()}`}
      value={text} onChange={(e) => setText(e.target.value)}
      onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add() } }} />
      <Button size="icon-sm" variant="outline" aria-label={`Add ${label.toLowerCase()}`} title="Add custom value" onClick={add} disabled={!text.trim()}><Plus /></Button>
    </div>}
  </div>
}

export function Turnaround({ value = "", onChange }: { value?: string; onChange: (value: string) => void }) {
  const match = /^(\d+(?:-\d+)?)\s+(days?|weeks?|months?|years?)$/.exec(value)
  const [amount, setAmount] = useState(match?.[1] || (value ? value : ""))
  const [unit, setUnit] = useState(match?.[2].replace(/s?$/, "s") || "days")
  const valid = !amount || /^\d+(?:-\d+)?$/.test(amount) && amount.split("-").every((v) => Number(v) > 0)
    && (amount.split("-").length === 1 || Number(amount.split("-")[0]) <= Number(amount.split("-")[1]))
  return <div className="space-y-1"><p className="type-label">Turnaround time</p>
    <div className="flex gap-2"><Input aria-label="Turnaround value or range" aria-invalid={!valid}
      placeholder="7 or 7-10" value={amount} onChange={(e) => { setAmount(e.target.value); onChange(e.target.value ? `${e.target.value} ${unit}` : "") }} />
      <select aria-label="Turnaround unit" className="paper-inset rounded-lg p-2 type-body" value={unit}
        onChange={(e) => { setUnit(e.target.value); onChange(amount ? `${amount} ${e.target.value}` : "") }}>
        {["days", "weeks", "months", "years"].map((v) => <option key={v}>{v}</option>)}
      </select></div>
    {!valid && <p role="alert" className="type-body-sm text-destructive">Enter a positive number or an ascending range, such as 7-10.</p>}
  </div>
}

export function PresentationFields({ value, presets, onChange }: {
  value: Presentation; presets: { analysis: string[]; input_material: string[]; sample_modes: string[] }
  onChange: (value: Presentation) => void
}) {
  return <div className="space-y-4">
    <div className="grid gap-3 md:grid-cols-2">
      <TextField label="Display name" value={value.label || value.title} onChange={(label) => onChange({ ...value, label, title: label })} />
      <TextField label="Subheading" value={value.subheading} onChange={(subheading) => onChange({ ...value, subheading })} />
    </div>
    <TextField label="Description" multiline value={value.description} onChange={(description) => onChange({ ...value, description })} />
    <Choices label="Input material" value={value.input_material} presets={presets.input_material} custom onChange={(input_material) => onChange({ ...value, input_material })} />
    <div className="grid gap-4 md:grid-cols-2">
      <Turnaround value={value.tat} onChange={(tat) => onChange({ ...value, tat })} />
      <Choices label="Sample modes" value={value.sample_modes} presets={presets.sample_modes} onChange={(sample_modes) => onChange({ ...value, sample_modes })} />
    </div>
    <Choices label="Analysis" value={value.analysis} presets={presets.analysis} onChange={(analysis) => onChange({ ...value, analysis })} />
    <details><summary className="cursor-pointer type-body font-semibold">Additional public content</summary>
      <div className="mt-3 space-y-3">
        <TextField label="Limitations" multiline value={value.limitations} onChange={(limitations) => onChange({ ...value, limitations })} />
        <TextField label="Public notes" multiline value={value.public_notes} onChange={(public_notes) => onChange({ ...value, public_notes })} />
        <Choices label="Report sections" value={value.report_sections} presets={presets.analysis} onChange={(report_sections) => onChange({ ...value, report_sections })} />
        <Choices label="Clinical indications" value={value.clinical_indications} presets={[]} custom onChange={(clinical_indications) => onChange({ ...value, clinical_indications })} />
      </div>
    </details>
  </div>
}
