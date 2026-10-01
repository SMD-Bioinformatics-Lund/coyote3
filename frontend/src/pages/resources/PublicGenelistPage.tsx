import { DataTable } from "@/components/data-table/DataTable"
import { PageShell } from "@/components/layout/PageShell"
import { api } from "@/lib/api"
import { useQuery } from "@tanstack/react-query"
import { useMemo } from "react"
import { useParams, useSearchParams } from "react-router-dom"
import { ErrorBox, Loading } from "./resource-presentation"
import { columnsFor } from "./resource-values"

export function PublicGenelistPage() {
  const { genelistId = "" } = useParams()
  const [params] = useSearchParams()
  const assay = params.get("assay") || undefined
  const { data, isLoading, error } = useQuery({
    queryKey: ["public-genelist", genelistId, assay],
    queryFn: () => api.get(`/public/genelists/${genelistId}/view_context${assay ? `?assay=${encodeURIComponent(assay)}` : ""}`).then((res) => res.data),
    enabled: Boolean(genelistId),
  })
  const genes = useMemo(() => data?.filtered_genes || data?.genes || data?.gene_objects || data?.rows || [], [data])
  const rows = useMemo(() => Array.isArray(genes) ? genes.map((gene: any) => {
    const row = typeof gene === "string" ? { gene } : gene
    const symbol = typeof gene === "string" ? gene : gene?.hgnc_symbol || gene?.symbol || gene?.gene
    return { ...row, knowledgebase_markers: data?.gene_markers?.[symbol] || row.knowledgebase_markers }
  }) : [], [data?.gene_markers, genes])
  const columns = useMemo(() => columnsFor(rows, ["hgnc_symbol", "symbol", "gene"]), [rows])

  return (
    <PageShell eyebrow="Public" title={data?.genelist?.name || data?.title || genelistId}>
      {isLoading ? <Loading /> : error ? <ErrorBox error={error} /> : (
        <section className="surface-panel p-3">
          <DataTable columns={columns} data={rows} filename={`${genelistId}_genes.csv`} />
        </section>
      )}
    </PageShell>
  )
}
