import { Input } from "@/components/ui/input"

type Props = { value: Record<string, unknown>; change: (value: Record<string, unknown>) => void; prefix?: string }

export function RuleTerminologyEditor({ value, change, prefix = "Structured wording" }: Props) {
  return <div className="space-y-3">{Object.entries(value).map(([key, item]) => {
    const label = `${prefix}: ${key.replaceAll("_", " ")}`
    const update = (next: unknown) => change({ ...value, [key]: next })
    if (item !== null && typeof item === "object" && !Array.isArray(item)) {
      return <details key={key} className="rounded-lg border p-3"><summary className="cursor-pointer font-medium">{key.replaceAll("_", " ")}</summary><div className="mt-3"><RuleTerminologyEditor value={item as Record<string, unknown>} prefix={label} change={update} /></div></details>
    }
    if (typeof item === "boolean") return <label key={key} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={item} onChange={event => update(event.target.checked)} />{label}</label>
    if (typeof item === "number") return <label key={key} className="type-label block">{label}<Input type="number" value={item} onChange={event => { if (event.target.value !== "" && Number.isFinite(event.target.valueAsNumber)) update(event.target.valueAsNumber) }} /></label>
    if (typeof item === "string") return <label key={key} className="type-label block">{label}<textarea className="paper-inset mt-1 min-h-16 w-full rounded-lg p-2 text-sm" value={item} onChange={event => update(event.target.value)} /></label>
    if (key === "multiple_gene_read_prefix_tiers" && Array.isArray(item) && item.every(entry => typeof entry === "number")) {
      return <fieldset key={key} className="rounded-lg border p-2"><legend className="type-label">{label}</legend>{[1, 2, 3, 4].map(tier => <label key={tier} className="mr-3 inline-flex items-center gap-1 text-sm"><input type="checkbox" checked={item.includes(tier)} onChange={event => update(event.target.checked ? [...item, tier].sort() : item.filter(entry => entry !== tier))} />Tier {tier}</label>)}</fieldset>
    }
    return null
  })}</div>
}
