import { DataTable } from "@/components/data-table/DataTable"
import { PageShell } from "@/components/layout/PageShell"
import { api } from "@/lib/api"
import { useQuery } from "@tanstack/react-query"
import { ExternalLink, Tags } from "lucide-react"
import { useMemo } from "react"
import { Link, useParams } from "react-router-dom"
import { BadgeList, ErrorBox, HtmlText, InfoTile, Loading, SectionTitle } from "./resource-presentation"
import { columnsFor, stripHtml } from "./resource-values"

export function PublicAspGenesPage() {
  const { aspId = "" } = useParams()
  const { data, isLoading, error } = useQuery({
    queryKey: ["public-asp-genes", aspId],
    queryFn: () => api.get(`/public/asp/${aspId}/genes`).then((res) => res.data),
    enabled: Boolean(aspId),
  })
  const genes = useMemo(() => data?.gene_details || data?.genes || data?.gene_objects || [], [data])
  const rows = useMemo(() => Array.isArray(genes) ? genes.map((gene: any) => typeof gene === "string" ? { gene } : gene) : [], [genes])
  const columns = useMemo(() => columnsFor(rows, ["hgnc_symbol", "symbol", "gene", "hgnc_id", "ensembl_gene_id"]), [rows])
  const catalog = data?.catalog || {}
  const asp = data?.asp || {}
  const stats = data?.stats || {}
  const geneLists = Array.isArray(catalog.gene_lists) ? catalog.gene_lists.filter((item: any) => item?.key || item?.label) : []
  const title = catalog.title || catalog.label || asp.display_name || asp.assay_name || aspId
  const description = catalog.description || asp.description || "Assay-panel gene table."
  const subpanel = catalog.subpanel_id && catalog.subpanel_id !== "base" ? catalog.subpanel_id : null

  return (
    <PageShell eyebrow="Public" title={title} description={stripHtml(description) || "Assay-panel gene table."}>
      {isLoading ? <Loading /> : error ? <ErrorBox error={error} /> : (
        <div className="space-y-3">
          <section className="surface-panel p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="mb-2 flex flex-wrap gap-1.5">
                  <span className="rounded-full border border-primary/25 bg-primary/10 px-2.5 py-1 text-xs font-semibold uppercase text-primary">
                    {catalog.modality_label || catalog.modality || asp.asp_category || "Assay"}
                  </span>
                  {catalog.family && (
                    <span className="rounded-full border border-border bg-muted px-2.5 py-1 text-xs font-semibold uppercase text-muted-foreground">
                      {catalog.family}
                    </span>
                  )}
                  {catalog.assay_group && (
                    <span className="rounded-full border border-border bg-muted px-2.5 py-1 text-xs font-semibold uppercase text-muted-foreground">
                      {catalog.assay_group}
                    </span>
                  )}
                  {subpanel && (
                    <span className="rounded-full border border-tier3/30 bg-tier3/10 px-2.5 py-1 text-xs font-semibold uppercase text-tier3">
                      {subpanel}
                    </span>
                  )}
                </div>
                <h2 className="text-xl font-semibold">{title}</h2>
                <HtmlText value={description} className="mt-1" />
              </div>
              <Link to="/public/catalog" className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted">
                Catalog
                <ExternalLink className="h-4 w-4" />
              </Link>
            </div>

            <div className="mt-4 grid gap-3 lg:grid-cols-4">
              <div className="rounded-lg border border-border bg-background/70 p-3">
                <p className="mb-2 type-label font-semibold uppercase tracking-wide text-muted-foreground">Input material</p>
                <BadgeList values={catalog.input_material} tone="material" />
              </div>
              <div className="rounded-lg border border-border bg-background/70 p-3">
                <p className="mb-2 type-label font-semibold uppercase tracking-wide text-muted-foreground">Sample types</p>
                <BadgeList values={catalog.sample_modes} tone="sample" />
              </div>
              <InfoTile label="Turnaround time" value={catalog.tat} />
              <InfoTile label="Covered genes" value={stats.covered_total ?? rows.length} />
              <div className="rounded-lg border border-border bg-background/70 p-3">
                <p className="mb-2 type-label font-semibold uppercase tracking-wide text-muted-foreground">Analysis</p>
                <BadgeList values={catalog.analysis} tone="analysis" />
              </div>
              <div className="rounded-lg border border-border bg-background/70 p-3">
                <p className="mb-2 type-label font-semibold uppercase tracking-wide text-muted-foreground">Report sections</p>
                <BadgeList values={catalog.report_sections} />
              </div>
              <InfoTile label="Germline genes" value={stats.germline_total ?? data?.germline_gene_symbols?.length ?? 0} />
              <InfoTile label="Platform / read mode" value={[asp.platform, asp.read_mode].filter(Boolean).join(" / ") || "-"} />
            </div>

            {(catalog.clinical_indications?.length > 0 || catalog.limitations || catalog.public_notes) && (
              <div className="mt-4 grid gap-3 lg:grid-cols-3">
                {catalog.clinical_indications?.length > 0 && (
                  <div className="rounded-lg border border-border bg-background/70 p-3">
                    <p className="mb-2 type-label font-semibold uppercase tracking-wide text-muted-foreground">Clinical indications</p>
                    <BadgeList values={catalog.clinical_indications} />
                  </div>
                )}
                {catalog.limitations && (
                  <div className="rounded-lg border border-border bg-background/70 p-3">
                    <p className="mb-2 type-label font-semibold uppercase tracking-wide text-muted-foreground">Limitations</p>
                    <HtmlText value={catalog.limitations} />
                  </div>
                )}
                {catalog.public_notes && (
                  <div className="rounded-lg border border-border bg-background/70 p-3">
                    <p className="mb-2 type-label font-semibold uppercase tracking-wide text-muted-foreground">Notes</p>
                    <HtmlText value={catalog.public_notes} />
                  </div>
                )}
              </div>
            )}
          </section>

          {geneLists.length > 0 && (
            <section className="surface-panel p-4">
              <SectionTitle icon={Tags}>Catalog Gene Lists</SectionTitle>
              <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
                {geneLists.map((list: any) => (
                  <div key={list.key || list.label} className="rounded-lg border border-border bg-background/70 p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h3 className="text-sm font-semibold">{list.label || list.key}</h3>
                        {list.key && <p className="type-meta font-semibold text-muted-foreground">{list.key}</p>}
                      </div>
                      {list.tat && (
                        <span className="rounded-full border border-border bg-muted px-2 py-1 type-label font-semibold uppercase text-muted-foreground">
                          {list.tat}
                        </span>
                      )}
                    </div>
                    <HtmlText value={list.description} className="mt-2" />
                    <div className="mt-3 space-y-2">
                      <BadgeList values={list.analysis} empty="Analysis follows assay default" tone="analysis" />
                      <BadgeList values={list.sample_modes} empty="Sample types follow assay default" tone="sample" />
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="surface-panel p-3">
            <DataTable columns={columns} data={rows} filename={`${aspId}_genes.csv`} />
          </section>
        </div>
      )}
    </PageShell>
  )
}
