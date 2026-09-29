import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useSearchParams } from "react-router-dom"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { PageShell } from "@/components/layout/PageShell"
import { AppLoader } from "@/components/layout/AppLoader"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"
import { hasPermission, useCurrentUserAccess } from "@/lib/access-control"
import { AssaySubpanels } from "./AssaySubpanels"
import { SubpanelNavigation } from "./SubpanelNavigation"
import { AdminHomeLink } from "./AdminHomeLink"

type Assay = { asp_id: string; display_name: string }
type AssayResults = { panels: Assay[]; pagination: { total: number } }

export function AssaySubpanelsPage() {
  const access = useCurrentUserAccess()
  const [params, setParams] = useSearchParams()
  const selected = params.get("assay") || ""
  const [search, setSearch] = useState("")
  const [page, setPage] = useState(1)
  const permitted = hasPermission(access.data, "assay.panel:list") && hasPermission(access.data, "assay.panel:view")
  const assays = useQuery({
    queryKey: ["subpanel-assay-options", search, page],
    enabled: permitted,
    queryFn: () => api.get<AssayResults>(`/resources/asp?${new URLSearchParams({ q: search, page: String(page), per_page: "30" })}`).then((response) => response.data),
  })

  return <PageShell eyebrow="Admin" title="Assay subpanel associations" actions={<AdminHomeLink />}>
    <section aria-label="Assay association registry" className="glass-card min-w-0 space-y-3 p-3">
    <SubpanelNavigation active="associations" />
    {access.isLoading ? <AppLoader label="Loading administration access" /> : !permitted ? (
      <p role="alert">Assay list and view permissions are required.</p>
    ) : <>
      <section className="grid gap-3 border-b border-border pb-3 sm:grid-cols-2" aria-label="Select assay">
        <label className="type-label">Search assays<Input className="mt-1 w-full" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1) }} /></label>
        <label className="type-label">Assay<select aria-label="Assay" className="paper-inset mt-1 w-full rounded-md border border-border px-3 py-2" value={selected} onChange={(event) => setParams(event.target.value ? { assay: event.target.value } : {})}>
          <option value="">Select assay</option>
          {selected && !(assays.data?.panels || []).some((assay) => assay.asp_id === selected) && <option value={selected}>{selected}</option>}
          {(assays.data?.panels || []).map((assay) => <option key={assay.asp_id} value={assay.asp_id}>{assay.display_name || assay.asp_id} ({assay.asp_id})</option>)}
        </select></label>
        {assays.isLoading && <AppLoader label="Loading assays" />}
        {assays.error && <p role="alert" className="text-destructive">Unable to load assays.</p>}
        {assays.data && <div className="flex items-center gap-3 sm:col-span-2">
          <span className="type-body text-muted-foreground">{assays.data.pagination.total} assays</span>
          <Button variant="outline" size="icon" aria-label="Previous assay page" title="Previous assay page" disabled={page === 1 || assays.isFetching} onClick={() => setPage(page - 1)}><ChevronLeft /></Button>
          <span className="type-body">{page}</span>
          <Button variant="outline" size="icon" aria-label="Next assay page" title="Next assay page" disabled={page * 30 >= assays.data.pagination.total || assays.isFetching} onClick={() => setPage(page + 1)}><ChevronRight /></Button>
        </div>}
      </section>
      {selected && <AssaySubpanels key={selected} aspId={selected} canEdit={hasPermission(access.data, "assay.panel:edit")} />}
      {!selected && !assays.isLoading && !assays.error && <p className="border-t border-border py-6 text-center type-body text-muted-foreground">No assay selected.</p>}
    </>}
    </section>
  </PageShell>
}
