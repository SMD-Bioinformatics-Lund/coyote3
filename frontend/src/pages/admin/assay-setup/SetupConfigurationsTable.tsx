import { icon } from "@/lib/assets"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"

type Configuration = Record<string, unknown>

export function SetupConfigurationsTable({ scopes, environments, records, readonly, pending, formAvailable, onEdit, onCreate, onRemove }: {
  scopes: string[]; environments: string[]; records: Configuration[]
  readonly: boolean; pending: boolean; formAvailable: boolean
  onEdit: (index: number) => void
  onCreate: (scope: string, environment: string) => void
  onRemove: (index: number) => void
}) {
  const [requestedPage, setPage] = useState(1)
  const slots = new Map<string, { scope: string; environment: string }>()
  for (const scope of scopes) for (const environment of environments) {
    slots.set(`${scope}::${environment}`, { scope, environment })
  }
  for (const record of records) {
    const scope = String(record.diagnosis_id || "base")
    const environment = String(record.environment || "")
    slots.set(`${scope}::${environment}`, { scope, environment })
  }
  const rows = [...slots.values()]
  const pages = Math.max(1, Math.ceil(rows.length / 10))
  const page = Math.min(requestedPage, pages)
  return <section aria-label="Saved configuration coverage" className="space-y-3">
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full text-left type-body">
        <caption className="sr-only">Configuration coverage by scope and environment</caption>
        <thead className="bg-muted/60 type-label"><tr>{["Scope", "Environment", "Status", "Saved configuration", "Actions"].map(label => <th key={label} scope="col" className="p-3">{label}</th>)}</tr></thead>
        <tbody className="divide-y divide-border">{rows.slice((page - 1) * 10, page * 10).map(({ scope, environment }) => {
          const matches = records.map((record, index) => ({ record, index })).filter(({ record }) => (record.diagnosis_id || "base") === scope && record.environment === environment)
          return <tr key={`${scope}::${environment}`}>
            <th scope="row" className="p-3 font-medium">{scope}</th><td className="p-3">{environment}</td>
            <td className="p-3"><Badge variant="outline" className={matches.length ? "border-pass/30 bg-pass/10 text-pass" : "border-warning/30 bg-warning/10"}>{matches.length ? <icon.check /> : <icon.circleAlert />}{matches.length ? "Configured" : "Missing"}</Badge></td>
            <td className="p-3">{matches.length ? matches.map(({ record, index }) => <div key={index} className="break-words font-medium">{String(record.display_name || record.name || record.aspc_id || `${scope} / ${environment}`)}</div>) : <span className="type-body-sm text-muted-foreground">Not saved yet</span>}</td>
            <td className="p-3"><div className="flex flex-wrap gap-2">{matches.length ? matches.map(({ index }) => <div key={index} className="flex gap-1">
              <Button variant="outline" size="sm" disabled={!formAvailable || pending} onClick={() => onEdit(index)} aria-label={`${readonly ? "View" : "Edit"} ${scope} ${environment}`}><icon.edit />{readonly ? "View" : "Edit"}</Button>
              {!readonly && <Button variant="ghost" size="icon" disabled={pending} aria-label={`Remove configuration ${scope} ${environment}`} onClick={() => onRemove(index)}><icon.trash2 /></Button>}
            </div>) : !readonly && <Button variant="outline" size="sm" disabled={!formAvailable || pending} aria-label={`Add configuration ${scope} ${environment}`} onClick={() => onCreate(scope, environment)}><icon.plus />Add</Button>}</div></td>
          </tr>
        })}</tbody>
      </table>
    </div>
    {rows.length > 0 && <nav aria-label="Configuration pages" className="flex flex-wrap items-center justify-between gap-2">
      <p role="status" className="type-body-sm text-muted-foreground">Showing {(page - 1) * 10 + 1}–{Math.min(page * 10, rows.length)} of {rows.length} scopes · 10 per page</p>
      <div className="flex items-center gap-2"><Button size="sm" variant="outline" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous configurations</Button><span className="type-meta">Page {page} of {pages}</span><Button size="sm" variant="outline" disabled={page === pages} onClick={() => setPage(page + 1)}>Next configurations</Button></div>
    </nav>}
  </section>
}
