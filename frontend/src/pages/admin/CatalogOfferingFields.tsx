import { TextField } from "./CatalogFields"
import type { Category } from "./catalog-types"

export function CatalogOfferingFields({ value, onChange }: { value: Category; onChange: (value: Category) => void }) {
  const price = value.price
  return <fieldset className="surface-panel space-y-4 p-4">
    <legend className="type-section-title">Published service information</legend>
    <label className="flex items-center gap-2 type-label"><input type="checkbox" checked={Boolean(price)} onChange={(e) => onChange({ ...value, price: e.target.checked ? { amount: "", currency: "", kind: "fixed", conditions: "" } : null })} />Publish an offering-specific price</label>
    {price ? <div className="grid gap-3 md:grid-cols-2">
      <TextField label="Price amount" value={price.amount} onChange={(amount) => onChange({ ...value, price: { ...price, amount } })} />
      <TextField label="Currency (three-letter code)" value={price.currency} onChange={(currency) => onChange({ ...value, price: { ...price, currency: currency.toUpperCase() } })} />
      <label className="grid gap-1 type-label">Price type<select className="paper-inset rounded-lg p-2 type-body" value={price.kind} onChange={(e) => onChange({ ...value, price: { ...price, kind: e.target.value as "fixed" | "starting" | "estimated" } })}><option value="fixed">Fixed</option><option value="starting">Starting from</option><option value="estimated">Estimated</option></select></label>
      <TextField label="Pricing conditions" value={price.conditions} onChange={(conditions) => onChange({ ...value, price: { ...price, conditions } })} />
    </div> : <TextField label="Pricing message" value={value.pricing_message || "Contact for pricing"} onChange={(pricing_message) => onChange({ ...value, pricing_message })} />}
    <TextField label="Report deliverables (one per line)" multiline value={(value.report_deliverables || []).join("\n")} onChange={(text) => onChange({ ...value, report_deliverables: text.split("\n").filter(Boolean) })} />
    <TextField label="Methodology" multiline value={value.methodology} onChange={(methodology) => onChange({ ...value, methodology })} />
    <TextField label="Ordering information" multiline value={value.ordering_information} onChange={(ordering_information) => onChange({ ...value, ordering_information })} />
  </fieldset>
}
