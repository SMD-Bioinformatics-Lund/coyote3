import { DataTable } from "@/components/data-table/DataTable"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import type { Catalog } from "@/pages/admin/catalog-types"
import { useQuery } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"
import { ArrowLeft, ArrowRight, Clock3, Dna, FlaskConical, Layers } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { BadgeList, HtmlText } from "./catalog-presentation"
import { familyLabels as families, matchOffering, offeringPrice, type Discovery, type Offering } from "./offering-types"

const control = "form-control rounded-lg px-3 py-2 type-body-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
type GeneRow = { gene: string; analysis: string; list: string; revision: number }
const columns: ColumnDef<GeneRow>[] = [
  { accessorKey: "gene", header: "Gene" }, { accessorKey: "analysis", header: "Analysis" },
  { accessorKey: "list", header: "Gene list" }, { accessorKey: "revision", header: "Revision" },
]

function Details({ offering: item }: { offering: Offering }) {
  const rows = item.gene_scopes.flatMap((scope) => scope.genes.map((gene) => ({ gene, analysis: scope.analysis, list: scope.label, revision: scope.revision })))
  return <article data-modality={item.modality} className="surface-panel catalog-service-card space-y-6 p-5">
    <header className="space-y-3 border-b border-border pb-4">
      <p className="type-supporting text-muted-foreground">{item.group_label} · {item.diagnosis_label}</p>
      <h2 className="type-section-title">{item.title}</h2><p>{families[item.family] || item.family} · {item.assay_label}</p>
      <p className="type-section-title">{offeringPrice(item)}</p>{item.price?.conditions && <p>{item.price.conditions}</p>}<HtmlText html={item.description} />
      {item.diagnosis_id === "base" && <p className="type-supporting">General testing uses the published Base scope, without a named diagnosis.</p>}
    </header>
    <section className="space-y-2"><h3 className="type-section-title">Analysis capabilities</h3><BadgeList values={item.analysis} /></section>
    <section className="space-y-3"><h3 className="type-section-title">Effective clinical gene scope</h3>
      <p className="type-supporting text-muted-foreground">Published genes are limited to configured analysis lists and validated assay coverage. Sequencing breadth does not define clinical reportability.</p>
      {item.gene_scopes.map((scope) => <p key={`${scope.list_id}-${scope.analysis}`} className="type-supporting">{scope.label} · revision {scope.revision} · {scope.analysis} · {scope.genes.length} eligible genes{scope.excluded_gene_count ? ` · ${scope.excluded_gene_count} list genes outside validated assay coverage` : ""}</p>)}
      {item.gene_scopes.length ? <DataTable columns={columns} data={rows} filename={`${item.offering_id}_genes.csv`} /> : <p>No public gene list is published for this offering.</p>}
    </section>
    <div className="grid gap-5 md:grid-cols-2">
      <section className="space-y-2"><h3 className="type-section-title">Reporting</h3><BadgeList values={item.report_deliverables} />{!item.report_deliverables.length && <p>Contact the service for report deliverables.</p>}</section>
      <section className="space-y-2"><h3 className="type-section-title">Specimen and turnaround</h3><BadgeList values={item.input_material} /><p>{item.turnaround || "Contact the service for turnaround information."}</p></section>
      <section className="space-y-2"><h3 className="type-section-title">Methodology</h3><p>{item.methodology || families[item.family] || item.family}</p></section>
      <section className="space-y-2"><h3 className="type-section-title">Limitations</h3>{item.limitations ? <HtmlText html={item.limitations} /> : <p>Contact the service for analytical limitations.</p>}</section>
    </div>
    <section className="space-y-2"><h3 className="type-section-title">Ordering information</h3><p className="whitespace-pre-wrap">{item.ordering_information || "Contact the center for eligibility and submission instructions."}</p></section>
  </article>
}

function Select({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: [string, string][] }) {
  return <label className="flex flex-col gap-1 type-supporting">{label}<select aria-label={label} className={control} value={value} onChange={(e) => onChange(e.target.value)}><option value="">All — none selected</option>{options.map(([id, text]) => <option key={id} value={id}>{text}</option>)}</select></label>
}

export function PublicCatalog({ previewDocument, onMatrix }: { previewDocument?: Catalog; onMatrix?: () => void }) {
  const [params, setParams] = useSearchParams()
  const [mode, setMode] = useState("diagnosis")
  const [query, setQuery] = useState("")
  const [group, setGroup] = useState("")
  const [diagnosis, setDiagnosis] = useState("")
  const [assay, setAssay] = useState("")
  const [family, setFamily] = useState("")
  const [modality, setModality] = useState("")
  const [analysis, setAnalysis] = useState("")
  const [sort, setSort] = useState("published")
  const [compare, setCompare] = useState<string[]>([])
  const { data, isLoading, error } = useQuery<Discovery>({
    queryKey: previewDocument ? ["catalog-offering-preview", previewDocument] : ["public-catalog-offerings"],
    queryFn: async () => (previewDocument ? await api.post("/admin/assay-catalog/preview/offerings", { document: previewDocument }) : await api.get("/public/assay-catalog/offerings")).data,
  })
  const offerings = data?.offerings || []
  const eligible = offerings.filter((item) => !group || item.group_id === group)
  const priceKinds = new Set(eligible.flatMap((item) => item.price ? [item.price.kind] : []))
  const currencies = new Set(eligible.flatMap((item) => item.price ? [item.price.currency] : []))
  const visible = eligible.filter((item) => (!assay || item.assay_id === assay) && (!diagnosis || item.diagnosis_id === diagnosis) && (!family || item.family === family) && (!modality || item.modality === modality) && (!analysis || item.analysis.includes(analysis)) && (!query.trim() || matchOffering(item, query).length))
    .sort((a, b) => sort === "name" ? a.title.localeCompare(b.title) : sort === "price" && currencies.size === 1 && priceKinds.size === 1 ? Number(a.price?.amount ?? Infinity) - Number(b.price?.amount ?? Infinity) : 0)
  const selected = offerings.find((item) => item.offering_id === params.get("offering"))
  const compared = offerings.filter((item) => compare.includes(item.offering_id))
  const select = (id?: string) => { const next = new URLSearchParams(params); if (id) next.set("offering", id); else next.delete("offering"); setParams(next) }
  const diagnosisSelect = <Select label="Diagnosis" value={diagnosis} onChange={setDiagnosis} options={[...new Map(eligible.filter((item) => !assay || item.assay_id === assay).map((item) => [item.diagnosis_id, item.diagnosis_label])).entries()]} />
  const technology = <><Select label="Molecular modality" value={modality} onChange={setModality} options={[...new Set(eligible.map((item) => item.modality))].map((id) => [id, id.toUpperCase()])} /><Select label="Technical family" value={family} onChange={setFamily} options={[...new Set(eligible.map((item) => item.family))].map((id) => [id, families[id] || id])} /></>
  return <PageShell title={data?.header || "Genomic test catalog"} description="Find published services by diagnosis or assay. Compare methods, clinical gene scope and service information."
    actions={onMatrix ? <Button variant="outline" onClick={onMatrix}>Matrix</Button> : <Button variant="outline" nativeButton={false} render={<Link to="/public/matrix" />}>Gene coverage matrix</Button>}>
    {isLoading ? <AppLoader label="Loading published tests" /> : error ? <div role="alert" className="surface-panel p-4">Unable to load published services. {error instanceof Error ? error.message : ""}</div>
      : selected ? <div className="space-y-4"><button className={`${control} inline-flex items-center gap-2`} onClick={() => select()}><ArrowLeft className="size-4" />Back to available tests</button><Details offering={selected} /></div>
      : params.has("offering") ? <section role="status" className="surface-panel space-y-3 p-5"><p>This offering is not part of the current publication.</p><button className={control} onClick={() => select()}>Browse available tests</button></section>
      : !offerings.length ? <section role="status" className="surface-panel space-y-2 p-5"><h2 className="type-section-title">No published services</h2><p>Published genomic test offerings will appear here.</p></section> : <div className="space-y-5">
        {data?.description && <HtmlText html={data.description} />}
        <section className="surface-panel space-y-4 p-4" aria-label="Find a genomic test">
          <label className="flex flex-col gap-1 type-supporting">Search diagnoses, genes and assays<input className={`${control} w-full`} placeholder="Search diagnoses, genes, assays…" value={query} onChange={(e) => setQuery(e.target.value)} /></label>
          <div className="flex flex-wrap gap-2" aria-label="Browse by">{["diagnosis", "assay"].map((value) => <button key={value} aria-pressed={mode === value} className={`${control} ${mode === value ? "border-primary bg-primary/10 text-primary" : ""}`} onClick={() => setMode(value)}>By {value === "diagnosis" ? "Diagnosis" : "Assay"}</button>)}</div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <Select label="Biological group" value={group} options={[...new Map(offerings.map((item) => [item.group_id, item.group_label])).entries()]} onChange={(value) => { setGroup(value); setAssay(""); setDiagnosis(""); setFamily(""); setModality(""); setAnalysis("") }} />
            {mode === "diagnosis" ? <>{diagnosisSelect}{technology}</> : <>{technology}<Select label="Assay" value={assay} onChange={(value) => { setAssay(value); setDiagnosis("") }} options={[...new Map(eligible.filter((item) => (!modality || item.modality === modality) && (!family || item.family === family)).map((item) => [item.assay_id, item.assay_label])).entries()]} />{diagnosisSelect}</>}
            <Select label="Analysis capability" value={analysis} onChange={setAnalysis} options={[...new Set(eligible.flatMap((item) => item.analysis))].map((id) => [id, id])} />
            <label className="flex flex-col gap-1 type-supporting">Sort<select className={control} value={sort} onChange={(e) => setSort(e.target.value)}><option value="published">Published order</option><option value="name">Test name</option>{currencies.size === 1 && priceKinds.size === 1 && <option value="price">Price ({[...currencies][0]})</option>}</select></label>
          </div>
        </section>
        <p role="status" className="type-supporting">{visible.length} available tests · publication {data?.version}</p>
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">{visible.map((item) => <article key={item.offering_id} data-modality={item.modality} className="surface-panel catalog-service-card flex min-w-0 flex-col gap-4 p-5">
          <header className="space-y-3">
            <div className="flex flex-wrap items-center gap-2"><Badge className="catalog-modality-badge">{item.modality === "dna" ? <Dna /> : <FlaskConical />}{item.modality.toUpperCase()}</Badge><span className="type-body-sm text-muted-foreground">{item.group_label} · {item.diagnosis_label}</span></div>
            <h2 className="type-title break-words font-semibold">{item.title}</h2>
            <p className="type-body-sm font-medium text-muted-foreground">{item.assay_label || item.assay_id}</p>
          </header>
          <div className="space-y-2"><p className="type-body font-medium">{families[item.family] || item.family}</p><BadgeList values={item.analysis} tone={item.modality === "rna" ? "secondary" : "primary"} /></div>
          <div className="flex flex-wrap gap-x-5 gap-y-2 border-y border-border/60 py-3 type-body-sm">
            {item.turnaround && <p className="flex items-center gap-2"><Clock3 className="size-4 text-muted-foreground" /><span>Turnaround: <strong className="font-semibold">{item.turnaround}</strong></span></p>}
            {item.gene_scopes.length > 0 && <p className="flex items-center gap-2"><Layers className="size-4 text-muted-foreground" /><span>Published genes: <strong className="font-semibold">{new Set(item.gene_scopes.flatMap(scope => scope.genes)).size}</strong></span></p>}
          </div>
          <HtmlText html={item.description} />
          <p className={item.price ? "type-title font-semibold" : "type-body-sm text-muted-foreground"}>{offeringPrice(item)}</p>
          {query.trim() && <p className="type-supporting text-muted-foreground">Matched: {matchOffering(item, query).join(", ")}</p>}
          <div className="mt-auto flex flex-wrap items-center justify-between gap-3 pt-1"><Button variant="outline" className="catalog-details-button" onClick={() => select(item.offering_id)}>View details<ArrowRight className="size-4" /></Button><label className="flex items-center gap-2 type-body-sm"><input type="checkbox" aria-label={`Compare ${item.title}`} checked={compare.includes(item.offering_id)} disabled={!compare.includes(item.offering_id) && compare.length >= 3} onChange={(e) => setCompare(e.target.checked ? [...compare, item.offering_id] : compare.filter((id) => id !== item.offering_id))} />Compare</label></div>
        </article>)}</div>
        {compared.length > 1 && <section className="surface-panel space-y-3 overflow-x-auto p-4"><h2 className="type-section-title">Compare published services</h2><table className="w-full text-left type-body-sm"><thead><tr><th className="p-3">Property</th>{compared.map((item) => <th className="p-3" key={item.offering_id}>{item.title}</th>)}</tr></thead><tbody>{["Method", "Analysis", "Gene scope", "Reports", "Price", "Limitations"].map((label) => <tr className="border-t border-border" key={label}><th className="p-3">{label}</th>{compared.map((item) => <td className="p-3" key={item.offering_id}>{label === "Method" ? families[item.family] || item.family : label === "Analysis" ? item.analysis.join(", ") : label === "Gene scope" ? item.gene_scopes.map((scope) => `${scope.analysis}: ${scope.genes.length} genes`).join("; ") : label === "Reports" ? item.report_deliverables.join(", ") : label === "Price" ? offeringPrice(item) : <HtmlText html={item.limitations} />}</td>)}</tr>)}</tbody></table></section>}
      </div>}
  </PageShell>
}
