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
import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { useAnnotationVisibility } from "./annotation-visibility"
import { AdditionalCatalogDetails, BadgeList, CatalogBadge, CatalogField, HtmlText } from "./catalog-presentation"
import { formatScalar } from "./catalog-values"
import { CatalogTree } from "./CatalogTree"

export function PublicCatalog({ previewDocument, onMatrix }: { previewDocument?: Catalog; onMatrix?: () => void }) {
  const annotations = useAnnotationVisibility("catalog")
  const [selection, setSelection] = useState<{ mod?: string; cat?: string; isgl_key?: string; analysis?: string }>({})
  const params = new URLSearchParams()
  if (selection.mod) params.set("mod", selection.mod)
  if (selection.cat) params.set("cat", selection.cat)
  if (selection.isgl_key) params.set("isgl_key", selection.isgl_key)

  const { data, isLoading, isFetching, isPlaceholderData, error } = useQuery({
    queryKey: previewDocument ? ["catalog-preview", previewDocument, selection] : ["public-catalog", selection],
    queryFn: () => previewDocument
      ? api.post(`/admin/assay-catalog/preview?${params.toString()}`, { document: previewDocument }).then((res) => res.data)
      : api.get(`/public/assay-catalog/context?${params.toString()}`).then((res) => res.data),
    placeholderData: (previous, query) => {
      const prior = query?.queryKey.at(-1) as typeof selection | undefined
      return prior?.mod === selection.mod && prior?.cat === selection.cat ? previous : undefined
    },
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
    const labels: Record<string, string> = {
      display_symbol: "Gene symbol",
      hgnc_id: "HGNC ID",
      hgnc_symbol: "Approved symbol",
      omim_id: "OMIM",
      locus: "Locus",
      refseq_mane_select: "MANE Select (RefSeq)",
      ensembl_mane_select: "MANE Select (Ensembl)",
      refseq_mane_plus_clinical: "MANE Plus Clinical (RefSeq)",
      ensembl_canonical: "Ensembl canonical",
      gene_name: "Gene name",
      status: "HGNC status",
      alias_symbol: "Aliases",
    }
    const availableKeys = new Set<string>(
      genes.flatMap((gene: any) => Object.keys(gene || {})).filter((key: string) => key !== "knowledgebase_markers"),
    )
    const keys = Object.keys(labels).filter((key) => availableKeys.has(key))
    const columns: ColumnDef<any, any>[] = keys.map((key) => ({
      id: key,
      header: labels[key],
      accessorFn: (row: any) => formatScalar(row[key]),
      cell: ({ row }) => {
        const raw = row.original[key]
        const value = typeof raw === "boolean" ? (raw ? "Yes" : "No") : formatScalar(raw)
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
  useEffect(() => {
    if (!data || isPlaceholderData || !selection.mod || selection.analysis || selection.isgl_key) return
    const analysis: string | undefined = data.right?.analysis?.[0]
    const list = (data.right?.gene_lists || []).find((item: { analysis?: string[] }) =>
      analysis ? item.analysis?.includes(analysis) : !item.analysis?.length)
    if (analysis || list?.key) setSelection((current) => ({ ...current, analysis, isgl_key: list?.key }))
  }, [data, isPlaceholderData, selection.mod, selection.analysis, selection.isgl_key])
  const selectedGeneList = useMemo(() => {
    if (!selection.isgl_key) return null
    return (right.gene_lists || []).find((geneList: any) => geneList?.key === selection.isgl_key) || null
  }, [right.gene_lists, selection.isgl_key])

  return (
    <PageShell
      className="flex-1"
      eyebrow="Public"
      title="Assay Catalog"
      description="Explore assay modalities, categories, gene lists, and covered genes."
      actions={
        <>
          <button
            onClick={() => downloadCsv.mutate()}
            disabled={!selection.mod || (Boolean(selection.cat) && !selection.isgl_key) || downloadCsv.isPending || isLoading}
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
      ) : !data?.order?.length ? (
        <section role="status" className="surface-panel space-y-2 rounded-lg border p-4">
          <h2 className="type-section-title">{previewDocument ? "Add catalog entries" : "Add catalog"}</h2>
          <p className="type-supporting text-muted-foreground">{previewDocument
            ? "Add a modality and its assays to preview this catalog."
            : "No assay catalog is available yet. An administrator can create and publish one under Administration → Assay catalog."}</p>
        </section>
      ) : (
        <div className="grid items-start gap-4 xl:flex-1 xl:grid-cols-[22rem_minmax(0,1fr)] xl:items-stretch">
          <div className="surface-panel dashboard-panel dashboard-panel--blue space-y-3 p-3">
            {selection.mod && <button className="type-body-sm font-semibold text-primary hover:underline"
              onClick={() => setSelection({})}>Catalog overview</button>}
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
                    className={`w-full px-3 py-2 text-left type-section-title ${activeMod ? "text-primary" : ""}`}
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
                      <CatalogTree categories={mod.categories || {}} selected={selection.cat}
                        onSelect={(cat) => setSelection({ mod: modKey, cat })} />
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          <div className="flex min-w-0 flex-col gap-4">
            {!selection.mod ? (
              <section aria-label="Catalog introduction" className="surface-panel dashboard-panel dashboard-panel--teal flex-1 space-y-4 p-6">
                <h2 className="type-section-title">{right.title || "Assay Catalog"}</h2>
                <HtmlText html={right.description} className="max-w-5xl type-body leading-relaxed text-foreground" />
                <p className="border-t border-border pt-4 type-supporting text-muted-foreground">
                  Browse the categories to explore offered analyses, sample requirements,
                  turnaround times and included genes. Use the matrix to compare gene coverage.
                </p>
              </section>
            ) : <>
            <section aria-label="Catalog entry details" className="surface-panel dashboard-panel dashboard-panel--teal p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="text-xl font-semibold">{right.title || right.label || "Assay Catalog"}</h2>
                  {right.subheading && <p className="mt-1 text-sm font-semibold text-primary">{right.subheading}</p>}
                  {right.description && <HtmlText html={right.description} className="mt-2 max-w-5xl text-sm leading-relaxed text-muted-foreground" />}
                </div>
              </div>

              <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                <CatalogField label="Input material">
                  <BadgeList values={right.input_material} empty="No Info" />
                </CatalogField>
                <CatalogField label="Turnaround time">
                  <span className="font-semibold">{formatScalar(right.tat)}</span>
                </CatalogField>
                <CatalogField label="Sample types">
                  <BadgeList values={right.sample_modes} empty="No Info" />
                </CatalogField>
                <CatalogField label="Assay gene coverage">
                  <span className="font-semibold text-primary">{right.asp?.covered_genes_count ?? "—"}</span>
                  <span className="ml-2 text-xs text-muted-foreground">
                    {typeof right.asp?.covered_genes_count === "number" ? "covered" : "Not specified"}
                    {typeof right.asp?.germline_genes_count === "number" ? `, germline ${right.asp.germline_genes_count}` : ""}
                  </span>
                </CatalogField>
              </div>

              <div className="mt-3">
                <CatalogField label="Available analysis">
                  <BadgeList values={right.analysis} empty="No Info" tone="primary" />
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
                      {right.asp?.platform && <CatalogBadge label="Platform" value={right.asp.platform === "illumina" ? "Illumina" : right.asp.platform} />}
                      {right.asp?.read_mode && <CatalogBadge label="Read mode" value={right.asp.read_mode === "PE" ? "Paired-end (PE)" : right.asp.read_mode === "SE" ? "Single-end (SE)" : right.asp.read_mode} />}
                      {right.asp?.read_length && <CatalogBadge label="Read length" value={`${right.asp.read_length} bp`} />}
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
            </section>
            <section aria-label="Gene table" className="surface-panel dashboard-panel dashboard-panel--rose flex-1 border-border/50 p-3">
              {selectedGeneList && (
                <section className="mb-3">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Selected gene list</p>
                      <h3 className="mt-1 text-base font-semibold text-foreground">{selectedGeneList.label || selectedGeneList.key}</h3>
                    </div>
                    {selectedGeneList.tat && <CatalogBadge label="TAT" value={selectedGeneList.tat} />}
                  </div>
                  {selectedGeneList.description && <HtmlText html={selectedGeneList.description} className="max-w-5xl text-sm leading-relaxed text-muted-foreground" />}
                </section>
              )}
              {!!right.analysis?.length && <p className="mb-2 type-label text-muted-foreground">Analysis</p>}
              <div role="tablist" aria-label="Available analyses" className="mb-3 flex flex-wrap gap-2 border-b border-border pb-3">
                {(right.analysis || []).map((analysis: string) => <button key={analysis} role="tab"
                  aria-selected={selection.analysis === analysis}
                  className={`rounded-lg border border-border px-3 py-2 type-label ${selection.analysis === analysis ? "bg-primary/10 text-primary" : "hover:bg-muted"}`}
                  onClick={() => setSelection({ ...selection, analysis,
                    isgl_key: (right.gene_lists || []).find((list: { key?: string; analysis?: string[] }) => list.analysis?.includes(analysis))?.key,
                  })}>{analysis}</button>)}
              </div>
              <div aria-label="Choose gene list" className="mb-3 flex flex-wrap items-center gap-2">
                {!!right.gene_lists?.length && <span className="type-label text-muted-foreground">Gene list</span>}
                {(right.gene_lists || []).filter((list: { analysis?: string[] }) => selection.analysis ? list.analysis?.includes(selection.analysis) : !right.analysis?.length && !list.analysis?.length)
                  .map((list: { key: string; label?: string }) => <button key={list.key}
                    aria-pressed={selection.isgl_key === list.key}
                    className={`rounded-lg border border-border px-2 py-1 type-body-sm ${selection.isgl_key === list.key ? "bg-genelist/10 text-genelist" : "hover:bg-muted"}`}
                    onClick={() => setSelection({ ...selection, isgl_key: list.key })}>{list.label || list.key}</button>)}
              </div>
              {selection.analysis && right.no_gene_list?.includes(selection.analysis) && <p className="type-body-sm text-muted-foreground">No gene list for {selection.analysis}.</p>}
              <div className="mb-2 flex justify-end">{annotations.toggle}</div>
              {isFetching ? <AppLoader label="Loading genes" /> : selection.mod && !selection.isgl_key
                ? <p className="type-body-sm text-muted-foreground">{selection.analysis ? "No gene list is selected for this analysis." : "No general gene list is defined for this entry or its parents."}</p>
                : <DataTable columns={geneColumns} data={data?.genes || []} filename="assay_catalog_genes.csv" />}
            </section>
            </>}
          </div>
        </div>
      )}
    </PageShell>
  )
}
