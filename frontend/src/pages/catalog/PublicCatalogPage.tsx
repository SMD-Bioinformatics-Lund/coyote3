import { valueBadgeClass } from "@/lib/badge-colors"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { Button } from "@/components/ui/button"
import { SearchInput } from "@/components/ui/search-input"
import { api } from "@/lib/api"
import type { Catalog } from "@/pages/admin/catalog-types"
import { useQuery } from "@tanstack/react-query"
import { icon } from "@/lib/assets"
import { Badge } from "@/components/ui/badge"
import { useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { BadgeList, HtmlText } from "./catalog-presentation"
import { CatalogComparisonTable } from "./CatalogComparisonTable"
import { CatalogOfferingDetails } from "./CatalogOfferingDetails"
import { CatalogSidebar } from "./CatalogSidebar"
import { CatalogGeneMatches } from "./CatalogGeneMatches"
import { familyLabels as families, matchesCatalogCategory, matchOffering, offeringGeneMatches, offeringPrice, parseCatalogGenes, type Discovery } from "./offering-types"

const control = "form-control rounded-lg px-3 py-2 type-body-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"

function Select({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: [string, string][] }) {
  return <label className="flex flex-col gap-1 type-supporting">{label}<select aria-label={label} className={control} value={value} onChange={(e) => onChange(e.target.value)}><option value="">All - none selected</option>{options.map(([id, text]) => <option key={id} value={id}>{text}</option>)}</select></label>
}

export function PublicCatalog({ previewDocument, onMatrix }: { previewDocument?: Catalog; onMatrix?: () => void }) {
  const [params, setParams] = useSearchParams()
  const [query, setQuery] = useState("")
  const [group, setGroup] = useState("")
  const [diagnosis, setDiagnosis] = useState("")
  const [assay, setAssay] = useState("")
  const [category, setCategory] = useState("all")
  const [expandedCategories, setExpandedCategories] = useState(() => new Set(["dna", "rna"]))
  const [geneText, setGeneText] = useState("")
  const [analysis, setAnalysis] = useState("")
  const [sort, setSort] = useState("name")
  const [compare, setCompare] = useState<string[]>([])
  const { data, isLoading, error } = useQuery<Discovery>({
    queryKey: previewDocument ? ["catalog-offering-preview", previewDocument] : ["public-catalog-offerings"],
    queryFn: async () => (previewDocument ? await api.post("/admin/assay-catalog/preview/offerings", { document: previewDocument }) : await api.get("/public/assay-catalog/offerings")).data,
  })
  const offerings = data?.offerings || []
  const genes = parseCatalogGenes(geneText)
  const eligible = offerings.filter((item) => matchesCatalogCategory(item, category) && (!group || item.group_id === group))
  const priceKinds = new Set(eligible.flatMap((item) => item.price ? [item.price.kind] : []))
  const currencies = new Set(eligible.flatMap((item) => item.price ? [item.price.currency] : []))
  const visible = eligible.filter((item) => (!assay || item.assay_id === assay) && (!diagnosis || item.diagnosis_id === diagnosis) && (!analysis || item.analysis.includes(analysis)) && (!query.trim() || matchOffering(item, query).length) && (!genes.length || offeringGeneMatches(item, genes).matched.length > 0))
    .sort((a, b) => sort === "price" && currencies.size === 1 && priceKinds.size === 1 ? Number(a.price?.amount ?? Infinity) - Number(b.price?.amount ?? Infinity) : (a.assay_display_name?.trim() || a.title).localeCompare(b.assay_display_name?.trim() || b.title))
  const selected = offerings.find((item) => item.offering_id === params.get("offering"))
  const compared = offerings.filter((item) => compare.includes(item.offering_id))
  const select = (id?: string) => { const next = new URLSearchParams(params); if (id) next.set("offering", id); else next.delete("offering"); setParams(next) }
  return <PageShell className="catalog-page" title={data?.header || "Genomic test catalog"} description="Find published services by diagnosis or assay. Compare methods, clinical gene scope and service information."
    actions={onMatrix ? <Button variant="outline" onClick={onMatrix}>Matrix</Button> : <Button variant="outline" nativeButton={false} render={<Link to="/public/matrix" />}>Gene coverage matrix</Button>}>
    {isLoading ? <AppLoader label="Loading published tests" /> : error ? <div role="alert" className="surface-panel p-4">Unable to load published services. {error instanceof Error ? error.message : ""}</div>
      : selected ? <CatalogOfferingDetails key={selected.offering_id} offering={selected} onBack={() => select()} />
      : params.has("offering") ? <section role="status" className="surface-panel space-y-3 p-5"><p>This offering is not part of the current publication.</p><button className={control} onClick={() => select()}>Browse available tests</button></section>
      : !offerings.length ? <section role="status" className="surface-panel space-y-2 p-5"><h2 className="type-section-title">No published services</h2><p>Published genomic test offerings will appear here.</p></section> : <div className="grid gap-5 lg:grid-cols-[15rem_minmax(0,1fr)]">
        <CatalogSidebar offerings={offerings} selected={category} group={group} diagnosis={diagnosis}
          expanded={expandedCategories} onExpandedChange={setExpandedCategories}
          onSelect={(value, groupId, diagnosisId) => {
            setCategory(value); setGroup(groupId); setDiagnosis(diagnosisId); setAssay("")
          }} />
        <div className="min-w-0 space-y-5">
        <section aria-label="Catalog information" className="surface-panel catalog-toolbar space-y-2 rounded-xl p-4">
          <h2 className="type-section-title">Explore our genomic tests</h2>
          <p className="type-body-sm text-muted-foreground">Browse DNA and RNA tests by sequencing method, or search published gene scopes. Compare up to three services to review their methods, included genes and ordering information.</p>
          {data?.description && <HtmlText html={data.description} />}
        </section>
        <section className="surface-panel catalog-toolbar space-y-4 p-4" aria-label="Find a genomic test">
          <label className="flex flex-col gap-1 type-supporting">Search diagnoses, genes and assays<SearchInput placeholder="Search diagnoses, genes, assays…" value={query} onChange={(e) => setQuery(e.target.value)} /></label>
          <div className="flex flex-col gap-1 type-supporting">
            <label htmlFor="catalog-requested-genes">Requested genes</label>
            <textarea id="catalog-requested-genes" className={`${control} w-full`} rows={3} placeholder="TP53, BRCA1, BCR" value={geneText} onChange={event => setGeneText(event.target.value)} aria-describedby="catalog-gene-help" />
          </div>
          <p id="catalog-gene-help" className="type-meta text-muted-foreground">Enter gene symbols separated by commas or new lines. Tests matching at least one requested gene are shown; counts use published gene scopes only.</p>
          <details>
          <summary className="cursor-pointer type-body-sm font-semibold text-primary">Additional filters</summary>
          <div className="mt-4 space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <Select label="Assay" value={assay} onChange={setAssay} options={[...new Map(eligible.filter(item => !diagnosis || item.diagnosis_id === diagnosis).map((item) => [item.assay_id, item.assay_label])).entries()]} />
            <Select label="Analysis capability" value={analysis} onChange={setAnalysis} options={[...new Set(eligible.flatMap((item) => item.analysis))].map((id) => [id, id])} />
            <label className="flex flex-col gap-1 type-supporting">Sort<select className={control} value={sort} onChange={(e) => setSort(e.target.value)}><option value="name">Test name</option>{currencies.size === 1 && priceKinds.size === 1 && <option value="price">Price ({[...currencies][0]})</option>}</select></label>
          </div>
          </div>
          </details>
        </section>
        <p role="status" className="type-supporting">{visible.length} available tests · publication {data?.version}</p>
        <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">{visible.map((item) => {
          const cardTitle = item.assay_display_name?.trim() || item.title
          return <article key={item.offering_id} data-modality={item.modality} data-family={item.family} className="surface-panel catalog-service-card flex min-w-0 flex-col gap-2 p-3">
          <header className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2"><Badge variant="outline" className={valueBadgeClass(item.modality)}>{item.modality === "dna" ? <icon.dna /> : <icon.flaskConical />}{item.modality.toUpperCase()}</Badge><span className="type-body-sm text-muted-foreground">{item.group_label} · {item.diagnosis_label}</span></div>
            <h2 className="type-card-title break-words font-semibold">{cardTitle}</h2>
          </header>
          <div className="flex flex-wrap items-center gap-1.5"><Badge variant="outline" className={valueBadgeClass(item.family)}>{families[item.family] || item.family}</Badge><BadgeList values={item.analysis} tone={item.modality === "rna" ? "secondary" : "primary"} /></div>
          <div className="flex flex-wrap gap-x-2 gap-y-1 border-y border-border/60 py-1.5 type-body-sm">
            {item.turnaround && <p className="flex items-center gap-1.5"><icon.clock3 className="size-3.5 text-muted-foreground" /><span>Turnaround: <strong className="font-semibold">{item.turnaround}</strong></span></p>}
            {item.gene_scopes.length > 0 && <p className="flex items-center gap-1.5"><icon.layers className="size-3.5 text-muted-foreground" /><span>Published genes: <strong className="font-semibold">{new Set(item.gene_scopes.flatMap(scope => scope.genes)).size}</strong></span></p>}
          </div>
          <HtmlText html={item.description} className="type-body-sm" />
          <p className={item.price ? "type-title font-semibold" : "type-body-sm text-muted-foreground"}>{offeringPrice(item)}</p>
          <CatalogGeneMatches offering={item} genes={genes} />
          {query.trim() && <p className="type-supporting text-muted-foreground">Matched: {matchOffering(item, query).join(", ")}</p>}
          <div className="mt-auto flex flex-wrap items-center justify-between gap-2 pt-1"><Button variant="outline" size="sm" className="catalog-details-button" onClick={() => select(item.offering_id)}>View details<icon.arrowRight className="size-4" /></Button><label className="flex items-center gap-2 type-body-sm"><input type="checkbox" aria-label={`Compare ${cardTitle}${item.assay_display_name?.trim() ? ` / ${item.diagnosis_label}` : ""}`} checked={compare.includes(item.offering_id)} disabled={!compare.includes(item.offering_id) && compare.length >= 3} onChange={(e) => setCompare(e.target.checked ? [...compare, item.offering_id] : compare.filter((id) => id !== item.offering_id))} />Compare</label></div>
        </article>})}</div>
        {visible.length === 0 && <p role="status" className="surface-panel p-4 type-body-sm">No tests match the selected categories, filters and requested genes.</p>}
        {compared.length > 1 && <CatalogComparisonTable offerings={compared} genes={genes} />}
        </div>
      </div>}
  </PageShell>
}
