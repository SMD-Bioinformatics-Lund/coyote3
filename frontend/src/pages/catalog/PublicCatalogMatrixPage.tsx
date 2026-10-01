import { useTablePreferences } from "@/components/data-table/table-preferences"
import { AppLoader } from "@/components/layout/AppLoader"
import { PageShell } from "@/components/layout/PageShell"
import { api } from "@/lib/api"
import type { Catalog } from "@/pages/admin/catalog-types"
import { useQuery } from "@tanstack/react-query"
import { useEffect, useMemo, useState, type FormEvent } from "react"
import { Link } from "react-router-dom"
import { AssayMatrixTable } from "./AssayMatrixTable"
import { contiguousSpans, uniqueOptions } from "./matrix-layout"

export function PublicCatalogMatrix({ previewDocument, onCatalog }: { previewDocument?: Catalog; onCatalog?: () => void }) {
  const { pageSize: preferredPageSize, setPageSize: persistPageSize } = useTablePreferences()
  const [filters, setFilters] = useState<Record<string, string>>({})
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(preferredPageSize)
  const [geneSearch, setGeneSearch] = useState("")
  const [appliedGeneSearch, setAppliedGeneSearch] = useState("")
  useEffect(() => {
    setPerPage(preferredPageSize)
    setPage(1)
  }, [preferredPageSize])
  const { data, isLoading, error } = useQuery({
    queryKey: previewDocument ? ["catalog-preview-matrix", previewDocument, page, perPage, appliedGeneSearch]
      : ["public-catalog-matrix", page, perPage, appliedGeneSearch],
    queryFn: () => {
      const params = new URLSearchParams()
      params.set("page", String(page))
      params.set("per_page", String(perPage))
      if (appliedGeneSearch.trim()) params.set("gene", appliedGeneSearch.trim())
      return previewDocument
        ? api.post(`/admin/assay-catalog/preview/matrix?${params.toString()}`, { document: previewDocument }).then((res) => res.data)
        : api.get(`/public/assay-catalog-matrix/context?${params.toString()}`).then((res) => res.data)
    },
  })

  const allMatrixColumns = useMemo(() => {
    return ((data?.columns || []) as any[])
      .filter((col) => !col.placeholder)
      .map((col) => {
        const [family = "-", assayGroup = "-", assay = "-", subpanel = "-"] = String(col.cat || "").split("::")
        return {
          ...col,
          family: col.family || family,
          modalityLabel: col.modality_label || col.modalityLabel || col.mod,
          assayGroup: col.assay_group || col.cat_label || assayGroup,
          assay: col.assay || assay,
          subpanel: col.subpanel || subpanel,
          key: `${col.mod}:${col.cat}:${col.isgl_key}`,
        }
      })
  }, [data])

  const matrixColumns = useMemo(() => {
    return allMatrixColumns.filter((col) => {
      if (filters.mod && col.mod !== filters.mod) return false
      if (filters.assayGroup && col.assayGroup !== filters.assayGroup) return false
      if (filters.list && String(col.isgl_label || col.isgl_key) !== filters.list) return false
      return true
    })
  }, [allMatrixColumns, filters])

  const filterOptions = useMemo(() => ({
    mod: uniqueOptions(allMatrixColumns.map((col) => col.mod)),
    assayGroup: uniqueOptions(allMatrixColumns.map((col) => col.assayGroup)),
    list: uniqueOptions(allMatrixColumns.map((col) => String(col.isgl_label || col.isgl_key))),
  }), [allMatrixColumns])

  const headerSpans = useMemo(() => {
    return {
      mod: contiguousSpans(matrixColumns, (col) => col.mod, (col) => col.modalityLabel || col.mod),
      assayGroup: contiguousSpans(matrixColumns, (col) => `${col.mod}::${col.assayGroup}`, (col) => col.assayGroup),
    }
  }, [matrixColumns])

  const genes = (data?.genes || []) as string[]
  const setMatrixFilter = (next: Record<string, string>) => {
    setFilters(next)
  }
  const submitGeneSearch = (event: FormEvent) => {
    event.preventDefault()
    setFilters({})
    setPage(1)
    setAppliedGeneSearch(geneSearch.trim())
  }
  const clearGeneSearch = () => {
    setGeneSearch("")
    setAppliedGeneSearch("")
    setPage(1)
  }

  return (
    <PageShell
      eyebrow="Public"
      title="Assay Catalog Matrix"
      className="rounded-lg bg-card"
      description="Gene coverage matrix across public assay catalog modalities and gene lists."
      actions={
        onCatalog ? <button onClick={onCatalog} className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted">Catalog</button> : <Link to="/public/catalog" className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted">
          Catalog
        </Link>
      }
    >
      {isLoading ? (
        <AppLoader label="Loading assay matrix" />
      ) : error ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          {error instanceof Error ? error.message : "Unable to load matrix"}
        </div>
      ) : (
        <AssayMatrixTable
          columns={matrixColumns}
          filters={filters}
          filterOptions={filterOptions}
          onFilterChange={setMatrixFilter}
          genes={genes}
          matrix={data?.matrix || {}}
          geneMarkers={data?.gene_markers || {}}
          headerSpans={headerSpans}
          page={data?.page || page}
          perPage={data?.per_page || perPage}
          total={data?.total || 0}
          hasNext={Boolean(data?.has_next)}
          hasPrevious={Boolean(data?.has_previous)}
          geneSearch={geneSearch}
          appliedGeneSearch={appliedGeneSearch}
          onGeneSearchChange={setGeneSearch}
          onGeneSearchSubmit={submitGeneSearch}
          onGeneSearchClear={clearGeneSearch}
          onPageChange={setPage}
          onPerPageChange={(next) => {
            persistPageSize(next)
            setPerPage(next)
            setPage(1)
          }}
        />
      )}
    </PageShell>
  )
}
