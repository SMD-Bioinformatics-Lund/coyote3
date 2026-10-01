import { DataTable } from "@/components/data-table/DataTable"
import { GeneWithOncoKbBadge, KnowledgebaseGeneTags } from "@/components/knowledgebase/OncoKbGeneBadge"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { api } from "@/lib/api"
import { downloadText } from "@/lib/browser-download"
import { rowsToCsv } from "@/lib/chart-export"
import type { Catalog } from "@/pages/admin/catalog-types"
import { useMutation, useQuery } from "@tanstack/react-query"
import { ColumnDef } from "@tanstack/react-table"
import { Activity, Download, Grid2X2, Info, ListTree } from "lucide-react"
import { useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { useAnnotationVisibility } from "./annotation-visibility"
import { AdditionalCatalogDetails, BadgeList, CatalogBadge, CatalogField, HtmlText } from "./catalog-presentation"
import { formatScalar } from "./catalog-values"

export function PublicCatalog({ previewDocument, onMatrix }: { previewDocument?: Catalog; onMatrix?: () => void }) {
  const annotations = useAnnotationVisibility("catalog")
  const [selection, setSelection] = useState<{ mod?: string; cat?: string; isgl_key?: string }>({})
  const params = new URLSearchParams()
  if (selection.mod) params.set("mod", selection.mod)
  if (selection.cat) params.set("cat", selection.cat)
  if (selection.isgl_key) params.set("isgl_key", selection.isgl_key)

  const { data, isLoading, error } = useQuery({
    queryKey: previewDocument ? ["catalog-preview", previewDocument, selection] : ["public-catalog", selection],
    queryFn: () => previewDocument
      ? api.post(`/admin/assay-catalog/preview?${params.toString()}`, { document: previewDocument }).then((res) => res.data)
      : api.get(`/public/assay-catalog/context?${params.toString()}`).then((res) => res.data),
  })

  const downloadCsv = useMutation({
    mutationFn: () => {
      if (previewDocument) return Promise.resolve({
        content: rowsToCsv(data?.genes || []), filename: "assay_catalog_preview_genes.csv",
      })
      const csvParams = new URLSearchParams()
      if (selection.mod) csvParams.set("mod", selection.mod)
      if (selection.cat) csvParams.set("cat", selection.cat)
      if (selection.isgl_key) csvParams.set("isgl_key", selection.isgl_key)
      return api.get(`/public/assay-catalog/genes.csv/context?${csvParams.toString()}`).then((res) => res.data)
    },
    onSuccess: (payload) => {
      downloadText(
        payload.content || "",
        payload.filename || "assay_catalog_genes.csv",
        "text/csv;charset=utf-8",
      )
    },
  })

  const geneColumns: ColumnDef<any, any>[] = useMemo(() => {
    const genes = data?.genes || []
    const preferredKeys = [
      "display_symbol",
      "hgnc_id",
      "hgnc_symbol",
      "gene_name",
      "status",
      "locus",
      "locus_sortable",
      "alias_symbol",
    ]
    const availableKeys = new Set<string>(
      genes.flatMap((gene: any) => Object.keys(gene || {})).filter((key: string) => key !== "knowledgebase_markers"),
    )
    const keys = preferredKeys
      .filter((key) => availableKeys.has(key))
      .concat(Array.from(availableKeys).filter((key) => !preferredKeys.includes(key)))
      .slice(0, 8)
    const columns: ColumnDef<any, any>[] = keys.map((key) => ({
      id: key,
      header: key.replaceAll("_", " "),
      accessorFn: (row: any) => row[key] ?? "",
      cell: ({ row }) => {
        const value = String(row.original[key] ?? "-")
        if (["display_symbol", "hgnc_symbol", "symbol", "gene"].includes(key)) {
          return (
            <GeneWithOncoKbBadge
              gene={row.original.resolved_symbol || row.original.hgnc_symbol || row.original.symbol}
              displayGene={row.original.display_symbol || value}
              resolvedGene={row.original.resolved_symbol || row.original.hgnc_symbol || row.original.symbol}
              hgncId={row.original.hgnc_id || row.original._id}
              matchSource={row.original.hgnc_match_source}
              showOncoKbBadge={false}
            />
          )
        }
        return <span className="text-xs">{value}</span>
      },
    }))
    if (annotations.visible) columns.splice(1, 0, {
      id: "annotations",
      header: "Annotations",
      enableSorting: false,
      cell: ({ row }) => <KnowledgebaseGeneTags markers={row.original.knowledgebase_markers} tiny />,
    })
    return columns
  }, [data, annotations.visible])
  const right = data?.right || {}
  const selectedGeneList = useMemo(() => {
    if (!selection.isgl_key) return null
    return (right.gene_lists || []).find((geneList: any) => geneList?.key === selection.isgl_key) || null
  }, [right.gene_lists, selection.isgl_key])

  return (
    <PageShell
      className="rounded-lg bg-card"
      eyebrow="Public"
      title="Assay Catalog"
      description="Explore assay modalities, categories, gene lists, and covered genes."
      actions={
        <>
          <button
            onClick={() => downloadCsv.mutate()}
            disabled={!selection.mod || downloadCsv.isPending || isLoading}
            className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted disabled:opacity-50"
          >
            {downloadCsv.isPending ? <Activity className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            Catalog CSV
          </button>
          {onMatrix ? <button onClick={onMatrix} className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted">
            <Grid2X2 className="h-4 w-4" /> Matrix
          </button> : <Link to="/public/matrix" className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted">
            <Grid2X2 className="h-4 w-4" />
            Matrix
          </Link>}
        </>
      }
    >
      {isLoading ? (
        <AppLoader label="Loading assay catalog" />
      ) : error ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          {error instanceof Error ? error.message : "Unable to load catalog"}
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[22rem_minmax(0,1fr)]">
          <div className="surface-panel dashboard-panel dashboard-panel--blue space-y-3 p-3">
            <h2 className="surface-panel-heading mb-0 flex items-center gap-2 text-sm font-semibold uppercase text-foreground">
              <ListTree className="h-4 w-4" />
              Modalities
            </h2>
            {(data?.order || []).map((modKey: string) => {
              const mod = data.modalities?.[modKey] || {}
              const activeMod = selection.mod === modKey
              return (
                <div key={modKey} className="rounded-lg border border-border bg-background">
                  <button
                    onClick={() => setSelection({ mod: modKey })}
                    className={`w-full px-3 py-2 text-left text-sm font-bold ${activeMod ? "text-primary" : ""}`}
                  >
                    {mod.label || mod.title || modKey}
                  </button>
                  {activeMod && (
                    <div className="border-t border-border p-2">
                      {mod.description && (
                        <HtmlText
                          html={mod.description}
                          className="mb-2 rounded-md bg-muted/45 px-2 py-1.5 type-meta leading-relaxed text-muted-foreground"
                        />
                      )}
                      {Object.entries(mod.categories || {}).map(([catKey, cat]: [string, any]) => (
                        <div key={catKey} className="mb-1">
                          <button
                            onClick={() => setSelection({ mod: modKey, cat: catKey })}
                            className={`block w-full rounded-md px-2 py-1.5 text-left text-xs font-semibold hover:bg-muted ${selection.cat === catKey ? "bg-primary/10 text-primary" : "text-muted-foreground"}`}
                          >
                            {cat.label || cat.title || catKey}
                          </button>
                          {selection.cat === catKey && (cat.gene_lists || []).length > 0 && (
                            <div className="ml-2 mt-1 border-l border-border pl-2">
                              {(cat.gene_lists || []).filter((gl: any) => gl.key).map((gl: any) => (
                                <button
                                  key={gl.key}
                                  onClick={() => setSelection({ mod: modKey, cat: catKey, isgl_key: gl.key })}
                                  className={`mb-1 block w-full rounded-md px-2 py-1 text-left type-meta font-semibold hover:bg-muted ${selection.isgl_key === gl.key ? "bg-genelist/10 text-genelist" : "text-muted-foreground"}`}
                                >
                                  {gl.label || gl.key}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          <div className="min-w-0 space-y-4">
            <section className="surface-panel dashboard-panel dashboard-panel--teal p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="text-xl font-semibold">{right.title || right.label || "Assay Catalog"}</h2>
                  {right.subheading && <p className="mt-1 text-sm font-semibold text-primary">{right.subheading}</p>}
                  {right.description && <HtmlText html={right.description} className="mt-2 max-w-5xl text-sm leading-relaxed text-muted-foreground" />}
                </div>
                {(right.catalog_id || right.asp_id || right.aspc_id || right.subpanel_id) && (
                  <div className="flex max-w-full flex-wrap justify-end gap-1.5">
                    {right.catalog_id && <CatalogBadge label="Catalog" value={right.catalog_id} />}
                    {right.asp_id && <CatalogBadge label="Assay" value={right.asp_id} />}
                    {right.aspc_id && <CatalogBadge label="Configuration" value={right.aspc_id} />}
                    {right.subpanel_id && right.subpanel_id !== "base" && <CatalogBadge label="Subpanel" value={right.subpanel_id} />}
                  </div>
                )}
              </div>

              <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                <CatalogField label="Input material">
                  <BadgeList values={right.input_material} empty="No Info" />
                </CatalogField>
                <CatalogField label="TAT">
                  <span className="font-semibold">{formatScalar(right.tat)}</span>
                </CatalogField>
                <CatalogField label="Sample types">
                  <BadgeList values={right.sample_modes} empty="No Info" />
                </CatalogField>
                <CatalogField label="Genes">
                  <span className="font-semibold text-primary">{data?.stats?.total ?? 0}</span>
                  <span className="ml-2 text-xs text-muted-foreground">
                    covered {data?.stats?.covered_total ?? 0}
                    {typeof data?.stats?.germline_total === "number" ? `, germline ${data.stats.germline_total}` : ""}
                  </span>
                </CatalogField>
              </div>

              <div className="mt-3 grid gap-2 md:grid-cols-2">
                <CatalogField label="Available analysis">
                  <BadgeList values={right.analysis} empty="No Info" tone="primary" />
                </CatalogField>
                <CatalogField label="Reporting sections">
                  <BadgeList values={right.report_sections} empty="No Info" tone="secondary" />
                </CatalogField>
              </div>

              {(right.clinical_indications?.length || right.limitations || right.public_notes || right.asp) && (
                <div className="mt-3 grid gap-2 lg:grid-cols-3">
                  <CatalogField label="Clinical indications">
                    <BadgeList values={right.clinical_indications} empty="No Info" tone="success" />
                  </CatalogField>
                  <CatalogField label="Limitations">
                    <HtmlText html={right.limitations || "No Info"} className="text-sm leading-relaxed text-foreground" />
                  </CatalogField>
                  <CatalogField label="Technical assay details">
                    <div className="flex flex-wrap gap-1.5">
                      {right.asp?.platform && <CatalogBadge label="Platform" value={right.asp.platform} />}
                      {right.asp?.read_mode && <CatalogBadge label="Read mode" value={right.asp.read_mode} />}
                      {right.asp?.read_length && <CatalogBadge label="Read length" value={right.asp.read_length} />}
                      {!right.asp?.platform && !right.asp?.read_mode && !right.asp?.read_length && <span className="text-sm text-muted-foreground">No Info</span>}
                    </div>
                  </CatalogField>
                </div>
              )}

              {right.public_notes && (
                <div className="mt-3 rounded-lg border border-primary/20 bg-primary/5 p-3">
                  <div className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-primary">
                    <Info className="h-3.5 w-3.5" />
                    Notes
                  </div>
                  <HtmlText html={right.public_notes} className="text-sm leading-relaxed text-foreground" />
                </div>
              )}

              <AdditionalCatalogDetails value={right} />

              {selectedGeneList && (
                <section className="mt-4 border-t border-border pt-4">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Selected gene list</p>
                      <h3 className="mt-1 text-base font-semibold text-foreground">{selectedGeneList.label || selectedGeneList.key}</h3>
                    </div>
                    {selectedGeneList.tat && <CatalogBadge label="TAT" value={selectedGeneList.tat} />}
                  </div>
                  {selectedGeneList.description && <HtmlText html={selectedGeneList.description} className="max-w-5xl text-sm leading-relaxed text-muted-foreground" />}
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    <BadgeList values={selectedGeneList.analysis} empty="" tone="primary" compact />
                    <BadgeList values={selectedGeneList.sample_modes} empty="" compact />
                    <BadgeList values={selectedGeneList.input_material} empty="" tone="secondary" compact />
                    <BadgeList values={selectedGeneList.list_type} empty="" tone="success" compact />
                  </div>
                </section>
              )}
            </section>

            <section className="surface-panel dashboard-panel dashboard-panel--rose border-border/50 p-3">
              <div className="mb-2 flex justify-end">{annotations.toggle}</div>
              <DataTable columns={geneColumns} data={data?.genes || []} filename="assay_catalog_genes.csv" />
            </section>
          </div>
        </div>
      )}
    </PageShell>
  )
}
