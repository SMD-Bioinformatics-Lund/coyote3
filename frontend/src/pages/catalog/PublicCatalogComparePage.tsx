import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { Button } from "@/components/ui/button"
import { SearchInput } from "@/components/ui/search-input"
import { api } from "@/lib/api"
import type { Catalog } from "@/pages/admin/catalog-types"
import { CatalogComparisonTable } from "./CatalogComparisonTable"
import { catalogService } from "./catalog-information"
import type { Discovery } from "./offering-types"

/** Compare reviewed services in a separate workspace without changing catalog navigation. */
export function PublicCatalogCompare({ previewDocument, onCatalog }: {
  previewDocument?: Catalog; onCatalog?: () => void
}) {
  const [params, setParams] = useSearchParams()
  const [search, setSearch] = useState("")
  const { data, isLoading, error, refetch } = useQuery<Discovery>({
    queryKey: previewDocument ? ["catalog-offering-preview", previewDocument] : ["public-catalog-offerings"],
    queryFn: async () => (previewDocument
      ? await api.post("/admin/assay-catalog/preview/offerings", { document: previewDocument }, { errorNotice: "inline" })
      : await api.get("/public/assay-catalog/offerings")).data,
    ...(previewDocument ? { retry: false, refetchOnWindowFocus: false } : {}),
  })
  const offerings = data?.offerings || []
  const ids = [...new Set(params.getAll("compare"))]
    .filter(id => offerings.some(item => item.offering_id === id)).slice(0, 3)
  const selected = ids.flatMap(id => offerings.filter(item => item.offering_id === id))
  const toggle = (id: string) => {
    const next = new URLSearchParams(params)
    next.delete("compare")
    for (const value of ids.includes(id) ? ids.filter(value => value !== id) : [...ids, id].slice(0, 3)) next.append("compare", value)
    setParams(next)
  }
  const visible = offerings.filter(item => [item.title, item.assay_label, item.assay_display_name,
    item.group_label, item.diagnosis_label, item.modality, item.family].join(" ").toLowerCase().includes(search.toLowerCase()))
  return <PageShell title="Compare assays" description="Select up to three published assay and diagnosis services to compare their scope and requirements."
    actions={onCatalog ? <Button variant="outline" onClick={onCatalog}>Catalog</Button>
      : <Button variant="outline" nativeButton={false} render={<Link to="/public/catalog" />}>Catalog</Button>}>
    {isLoading ? <AppLoader label="Loading published assays" /> : error ? <section role="alert" className="surface-panel space-y-3 p-4">
      <p>Unable to load published assays.</p><Button variant="outline" onClick={() => void refetch()}>Retry</Button>
    </section> : <>
      <section className="surface-panel space-y-3 p-4" aria-label="Choose assays to compare">
        <SearchInput aria-label="Search assays to compare" placeholder="Search assays, groups and diagnoses…" value={search} onChange={event => setSearch(event.target.value)} />
        <p role="status" className="type-body-sm">{selected.length} of 3 services selected</p>
        <div className="max-h-64 space-y-1 overflow-y-auto">
          {visible.map(item => <label key={item.offering_id} className="flex cursor-pointer items-start gap-3 rounded-lg p-2 type-body-sm hover:bg-muted">
            <input type="checkbox" checked={ids.includes(item.offering_id)} disabled={!ids.includes(item.offering_id) && ids.length >= 3}
              onChange={() => toggle(item.offering_id)} />
            <span><span className="block font-semibold">{item.assay_display_name || item.assay_label} · {item.diagnosis_label}</span>
              <span className="text-muted-foreground">{item.modality.toUpperCase()} · {item.family} · {item.group_label}</span></span>
          </label>)}
          {!visible.length && <p className="type-body-sm text-muted-foreground">{offerings.length ? "No assays match the search." : "No published services."}</p>}
        </div>
      </section>
      {selected.length < 2 ? <p role="status" className="type-body-sm text-muted-foreground">Select at least two services for a comparison.</p>
        : <CatalogComparisonTable offerings={selected.map(item =>
          catalogService(item, data?.navigation?.find(node => node.offering_id === item.offering_id)))} />}
    </>}
  </PageShell>
}
