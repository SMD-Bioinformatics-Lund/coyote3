import { Input } from "@/components/ui/input"
import { MarkdownComposer } from "@/components/comments/MarkdownComposer"

type Props = { value: Record<string, unknown>; change: (value: Record<string, unknown>) => void; prefix?: string; readOnly?: boolean }

export function RuleTerminologyEditor({ value, change, prefix = "Structured wording", readOnly = false }: Props) {
  return <div className="space-y-3">{Object.entries(value).map(([key, item]) => {
    const label = `${prefix}: ${key.replaceAll("_", " ")}`
    const update = (next: unknown) => change({ ...value, [key]: next })
    if (item !== null && typeof item === "object" && !Array.isArray(item)) {
      return <details key={key} className="rounded-lg border p-3"><summary className="cursor-pointer font-medium">{key.replaceAll("_", " ")}</summary><div className="mt-3"><RuleTerminologyEditor value={item as Record<string, unknown>} prefix={label} change={update} readOnly={readOnly} /></div></details>
    }
    if (typeof item === "boolean") return <label key={key} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={item} onChange={event => update(event.target.checked)} />{label}</label>
    if (typeof item === "number") return <label key={key} className="type-label block">{label}<Input type="number" value={item} onChange={event => { if (event.target.value !== "" && Number.isFinite(event.target.valueAsNumber)) update(event.target.valueAsNumber) }} /></label>
    if (typeof item === "string") return <div key={key} className="space-y-1"><p className="type-label">{label}</p><MarkdownComposer label={label} compact value={item} onChange={update} maxLength={null} readOnly={readOnly} /></div>
    if (key === "multiple_gene_read_prefix_tiers" && Array.isArray(item) && item.every(entry => typeof entry === "number")) {
      return <fieldset key={key} className="rounded-lg border p-2"><legend className="type-label">{label}</legend>{[1, 2, 3, 4].map(tier => <label key={tier} className="mr-3 inline-flex items-center gap-1 text-sm"><input type="checkbox" checked={item.includes(tier)} onChange={event => update(event.target.checked ? [...item, tier].sort() : item.filter(entry => entry !== tier))} />Tier {tier}</label>)}</fieldset>
    }
    return null
  })}</div>
}
