import { TextField } from "./CatalogFields"
import type { Presentation } from "./catalog-types"

export function CatalogOfferingFields({ value, onChange }: { value: Presentation; onChange: (value: Presentation) => void }) {
  const price = value.price
  return <div className="space-y-3">
    <p className="type-label">Pricing</p>
    <label className="flex items-center gap-2 type-label"><input type="checkbox" checked={Boolean(price)} onChange={(e) => onChange({ ...value, price: e.target.checked ? { amount: "", currency: "", kind: "fixed", conditions: "" } : null })} />Set a price at this level</label>
    <p className="type-meta text-muted-foreground">Blank service fields inherit from the immediate parent. Diagnosis-specific values replace those defaults.</p>
    {price ? <div className="grid gap-3 md:grid-cols-2">
      <TextField label="Price amount" value={price.amount} onChange={(amount) => onChange({ ...value, price: { ...price, amount } })} />
      <TextField label="Currency (three-letter code)" value={price.currency} onChange={(currency) => onChange({ ...value, price: { ...price, currency: currency.toUpperCase() } })} />
      <label className="grid gap-1 type-label">Price type<select className="paper-inset rounded-lg p-2 type-body" value={price.kind} onChange={(e) => onChange({ ...value, price: { ...price, kind: e.target.value as "fixed" | "starting" | "estimated" } })}><option value="fixed">Fixed</option><option value="starting">Starting from</option><option value="estimated">Estimated</option></select></label>
      <TextField label="Pricing conditions" value={price.conditions} onChange={(conditions) => onChange({ ...value, price: { ...price, conditions } })} />
    </div> : <TextField label="Pricing message" help="Leave blank to inherit the parent's pricing wording." value={value.pricing_message} onChange={(pricing_message) => onChange({ ...value, pricing_message })} />}
  </div>
}
