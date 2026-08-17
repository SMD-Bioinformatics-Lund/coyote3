import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { BookOpenCheck } from "lucide-react"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { api } from "@/lib/api"

type ContractCatalogRow = {
  collection?: string
  title?: string
  required?: string[]
  properties?: string[]
}

export default function AdminSchemasPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-schemas"],
    queryFn: () => api.get("/admin/schemas").then((res) => res.data),
    retry: false,
  })
  const rows: ContractCatalogRow[] = useMemo(() => data?.schemas || data?.items || [], [data])
  const groupedRows = useMemo(() => rows.reduce((acc: Record<string, ContractCatalogRow[]>, row) => {
    const group = String(row.collection || "other").split("_")[0] || "other"
    acc[group] = [...(acc[group] || []), row]
    return acc
  }, {}), [rows])

  return (
    <PageShell eyebrow="Diagnostics" title="Contract Diagnostics" description="Read-only backend Pydantic contracts and managed form sources used by the API, ingest, and resource editors.">
      <section className="surface-panel p-3">
        <div className="mb-3 flex flex-wrap items-start justify-between gap-3 px-1">
          <div className="flex items-start gap-2">
            <BookOpenCheck className="mt-0.5 h-5 w-5 text-panel" />
            <div>
              <h2 className="text-lg font-semibold">Managed Collection Contracts</h2>
              <p className="text-sm text-muted-foreground">These contracts support QA and diagnostics. Managed resources are edited through their dedicated admin forms.</p>
            </div>
          </div>
          <span className="rounded-full border border-border bg-background px-3 py-1 text-xs font-bold text-muted-foreground">{rows.length} contracts</span>
        </div>
        {isLoading ? <AppLoader label="Loading schema contracts" /> : error ? (
          <div className="rounded-lg border border-warn/30 bg-warn/10 p-3 text-sm text-warn">{error instanceof Error ? error.message : "Unable to load schema contracts."}</div>
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            {Object.entries(groupedRows).map(([group, contracts]) => (
              <div key={group} className="rounded-xl border border-border bg-background/60 p-3">
                <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide">{group}</h3>
                <div className="space-y-2">
                  {contracts.map((contract) => (
                    <article key={contract.collection} className="glass-card rounded-lg p-3">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div><h4 className="text-sm font-semibold">{contract.title || contract.collection}</h4><p className="text-xs text-muted-foreground">{contract.collection}</p></div>
                        <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-bold text-primary">{(contract.properties || []).length} fields</span>
                      </div>
                      {(contract.required || []).length > 0 && <div className="mt-2 flex flex-wrap gap-1">{(contract.required || []).map((field) => <span key={field} className="rounded-md bg-destructive/10 px-1.5 py-0.5 text-[10px] font-bold text-destructive">{field}</span>)}</div>}
                      <details className="mt-2"><summary className="cursor-pointer text-xs font-bold text-primary">Show field names</summary><div className="mt-2 flex max-h-28 flex-wrap gap-1 overflow-auto rounded-lg bg-muted/40 p-2">{(contract.properties || []).map((field) => <span key={field} className="rounded bg-background px-1.5 py-0.5 text-[10px] text-muted-foreground">{field}</span>)}</div></details>
                    </article>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </PageShell>
  )
}
