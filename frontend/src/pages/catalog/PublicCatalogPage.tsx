import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import type { Catalog, Category } from "@/pages/admin/catalog-types"
import { useQuery } from "@tanstack/react-query"
import { useMemo } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { catalogService, emptyCatalogInformation, offeringInformation } from "./catalog-information"
import { CatalogInformation } from "./CatalogInformation"
import { CatalogOfferingDetails } from "./CatalogOfferingDetails"
import { CatalogTree } from "./CatalogTree"
import { catalogNavigation, type CatalogBrowseNode } from "./catalog-navigation"
import type { Discovery } from "./offering-types"

export function PublicCatalog({ previewDocument, onMatrix, onCompare }: { previewDocument?: Catalog; onMatrix?: () => void; onCompare?: () => void }) {
  const [params, setParams] = useSearchParams()
  const { data, isLoading, error, refetch } = useQuery<Discovery>({
    queryKey: previewDocument ? ["catalog-offering-preview", previewDocument] : ["public-catalog-offerings"],
    queryFn: async () => (previewDocument
      ? await api.post("/admin/assay-catalog/preview/offerings", { document: previewDocument }, { errorNotice: "inline" })
      : await api.get("/public/assay-catalog/offerings")).data,
    ...(previewDocument ? { retry: false, refetchOnWindowFocus: false } : {}),
  })
  const nodes = useMemo(() => catalogNavigation(data), [data])
  const offerings = data?.offerings || []
  const selected = nodes.find(node => params.has("node")
    ? node.node_id === params.get("node") : node.level === "diagnosis"
      && node.offerings.some(item => item.offering_id === params.get("offering")))
  const selectedOfferings = params.has("node") ? selected?.level === "diagnosis" ? selected.offerings : []
    : offerings.filter(item => item.offering_id === params.get("offering"))
  const categories: Record<string, Category> = Object.fromEntries(nodes.map(node => [node.node_id, {
    label: node.label, parent_key: node.parent_id,
  }]))
  const select = (node?: CatalogBrowseNode) => {
    const next = new URLSearchParams(params)
    next.delete("offering"); next.delete("node")
    if (node) next.set("node", node.node_id)
    setParams(next)
  }
  const path: CatalogBrowseNode[] = []
  let ancestor = selected
  while (ancestor && !path.includes(ancestor)) {
    path.unshift(ancestor)
    ancestor = nodes.find(node => node.node_id === ancestor?.parent_id)
  }
  const unavailable = (params.has("node") || params.has("offering")) && !selected
  const summaryOfferings = (selected?.offerings || offerings).map(item =>
    catalogService(item, data?.navigation?.find(node => node.offering_id === item.offering_id), selected))
  return <PageShell className="catalog-page" title={data?.header || "Genomic test catalog"}
    description="Browse the catalog and select a section, group or diagnosis to read its service information."
    actions={<>{onCompare ? <Button variant="outline" onClick={onCompare}>Compare assays</Button>
      : <Button variant="outline" nativeButton={false} render={<Link to="/public/catalog/compare" />}>Compare assays</Button>}
      {onMatrix ? <Button variant="outline" onClick={onMatrix}>Matrix</Button>
      : <Button variant="outline" nativeButton={false} render={<Link to="/public/matrix" />}>Gene coverage matrix</Button>}</>}>
    {isLoading ? <AppLoader label="Loading published tests" /> : error ? <div role="alert" className="surface-panel space-y-3 p-4">
      <p>Unable to load published services.</p><Button variant="outline" onClick={() => void refetch()}>Retry</Button>
    </div> : !nodes.length && !offerings.length ? <section role="status" className="surface-panel space-y-2 p-5">
      <h2 className="type-section-title">No published services</h2><p>Published genomic test information will appear here.</p>
    </section> : <div className="grid items-start gap-5 lg:grid-cols-[17rem_minmax(0,1fr)]">
      <aside className="surface-panel catalog-sidebar min-w-0 p-3">
        <h2 className="type-section-title px-2 py-2">Browse tests</h2>
        <nav aria-label="Test categories" className="space-y-2">
          <Button variant={selected ? "ghost" : "secondary"} className="w-full justify-start" onClick={() => select()}>Catalog introduction</Button>
          <CatalogTree categories={categories} selected={selected?.node_id}
            appearances={Object.fromEntries(nodes.map(node => [node.node_id, { level: node.level,
              tone: node.level === "modality" ? node.offerings[0]?.modality : node.level === "family"
                ? node.offerings[0]?.family : node.level === "group" ? node.offerings[0]?.group_id : undefined,
            }]))}
            defaultExpanded={['["dna"]', '["rna"]']}
            onSelect={id => select(nodes.find(node => node.node_id === id))} />
        </nav>
      </aside>
      <div className="min-w-0 space-y-4">
        {path.length > 0 && <nav aria-label="Catalog location" className="flex flex-wrap items-center gap-2 type-body-sm">
          {path.map((node, index) => <span key={node.node_id} className="inline-flex items-center gap-2">
            {index > 0 && <span aria-hidden="true">/</span>}
            <button className="rounded text-primary underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-ring"
              aria-current={node === selected ? "page" : undefined} onClick={() => select(node)}>{node.label}</button>
          </span>)}
        </nav>}
        {unavailable ? <section role="status" className="surface-panel space-y-3 p-5"><p>This selection is not part of the current publication.</p><Button variant="outline" onClick={() => select()}>Browse available tests</Button></section>
          : selectedOfferings?.length ? <>
            {selectedOfferings.length > 1 && selected && <CatalogInformation information={selected} offerings={summaryOfferings} />}
            {selectedOfferings.map(item => {
              const information = data?.navigation?.find(node => node.offering_id === item.offering_id)
              const resolved = offeringInformation(item, information, selected)
              return <CatalogOfferingDetails key={item.offering_id} offering={item}
                showInformation={selectedOfferings.length === 1}
                information={{ ...resolved, title: selected && selectedOfferings.length === 1 ? selected.title : resolved.title }} />
            })}
          </>
          : selected ? <CatalogInformation information={selected} offerings={summaryOfferings}
            overview={selected.level === "modality" ? selected.offerings[0]?.modality : undefined} />
          : <CatalogInformation information={{ ...emptyCatalogInformation("Our genomic tests"),
            description: data?.description || "" }} offerings={summaryOfferings} overview="home" />}
      </div>
    </div>}
  </PageShell>
}
