import { PageSizeSelect } from "@/components/data-table/PageSizeSelect"
import { KnowledgebaseGeneTags } from "@/components/knowledgebase/OncoKbGeneBadge"
import { Check, Search, X } from "lucide-react"
import { type FormEvent } from "react"
import { Link } from "react-router-dom"
import { useAnnotationVisibility } from "./annotation-visibility"
import { labelText, matrixBoundaryClass, matrixBoundaryStyle, matrixColumnWidth, matrixModalityLabel } from "./matrix-layout"

export function AssayMatrixTable({
  columns,
  filters,
  filterOptions,
  onFilterChange,
  genes,
  matrix,
  geneMarkers,
  headerSpans,
  page,
  perPage,
  total,
  hasNext,
  hasPrevious,
  geneSearch,
  appliedGeneSearch,
  onGeneSearchChange,
  onGeneSearchSubmit,
  onGeneSearchClear,
  onPageChange,
  onPerPageChange,
}: {
  columns: any[]
  filters: Record<string, string>
  filterOptions: Record<string, string[]>
  onFilterChange: (next: Record<string, string>) => void
  genes: string[]
  matrix: Record<string, any>
  geneMarkers: Record<string, any>
  headerSpans: {
    mod: Array<{ key: string; label: string; span: number }>
    assayGroup: Array<{ key: string; label: string; span: number }>
  }
  page: number
  perPage: number
  total: number
  hasNext: boolean
  hasPrevious: boolean
  geneSearch: string
  appliedGeneSearch: string
  onGeneSearchChange: (value: string) => void
  onGeneSearchSubmit: (event: FormEvent) => void
  onGeneSearchClear: () => void
  onPageChange: (page: number) => void
  onPerPageChange: (perPage: number) => void
}) {
  const updateFilter = (key: string, value: string) => {
    onFilterChange({ ...filters, [key]: value })
  }
  const annotations = useAnnotationVisibility("matrix")

  return (
    <div className="surface-panel dashboard-panel dashboard-panel--blue border-border/50 p-3">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-border/60 pb-3">
        <div className="flex min-w-0 items-center gap-2">
          <span className="rounded-lg border border-border bg-muted/60 px-2.5 py-1.5 text-xs font-semibold text-foreground shadow-sm">
            {genes.length} genes
          </span>
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-foreground">Assay Catalog - Gene Coverage Matrix</h2>
            <p className="text-xs font-normal text-muted-foreground">
              {columns.length} visible catalog column(s)
              {appliedGeneSearch ? ` for "${appliedGeneSearch}"` : ""}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-1.5">
          {annotations.toggle}
          <label className="flex items-center gap-2 type-label font-semibold uppercase tracking-wide text-muted-foreground">
            Rows
            <PageSizeSelect
              value={perPage}
              disabled={Boolean(appliedGeneSearch)}
              onValueChange={onPerPageChange}
              className="h-8 rounded-lg border border-input bg-background px-2 text-xs font-semibold text-foreground disabled:opacity-50"
            />
          </label>
          <button
            type="button"
            disabled={!hasPrevious}
            onClick={() => onPageChange(Math.max(1, page - 1))}
            className="h-8 rounded-lg border border-border px-3 text-xs font-semibold hover:bg-muted disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-xs font-semibold text-muted-foreground">Page {page}</span>
          <button
            type="button"
            disabled={!hasNext}
            onClick={() => onPageChange(page + 1)}
            className="h-8 rounded-lg border border-border px-3 text-xs font-semibold hover:bg-muted disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <form onSubmit={onGeneSearchSubmit} className="flex min-w-[18rem] max-w-[34rem] flex-1 flex-wrap items-end gap-2">
          <label className="grid min-w-[14rem] flex-1 gap-1 type-label font-semibold uppercase tracking-wide text-muted-foreground">
            Gene search
            <input
              value={geneSearch}
              onChange={(event) => onGeneSearchChange(event.target.value)}
              className="h-8 rounded-lg border border-input bg-background px-2.5 text-xs font-normal normal-case tracking-normal text-foreground"
              placeholder="TP53"
            />
          </label>
          <button type="submit" className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-primary px-3 text-xs font-bold text-primary-foreground shadow-sm hover:bg-primary/90">
            <Search className="h-3.5 w-3.5" />
            Search
          </button>
          <button type="button" onClick={onGeneSearchClear} className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-border px-3 text-xs font-bold hover:bg-muted">
            <X className="h-3.5 w-3.5" />
            Clear
          </button>
        </form>
      </div>

      <div className="mb-3 grid gap-2 rounded-xl border border-border/70 bg-muted/25 p-3 md:grid-cols-3">
        {[
          ["mod", "Modality"],
          ["assayGroup", "Section"],
          ["list", "Gene list"],
        ].map(([key, label]) => (
          <label key={key} className="grid gap-1 type-label font-semibold uppercase tracking-wide text-muted-foreground">
            {label}
            <select
              value={filters[key] || ""}
              onChange={(event) => updateFilter(key, event.target.value)}
              className="h-8 rounded-lg border border-input bg-background px-2 text-xs font-normal normal-case tracking-normal text-foreground"
            >
              <option value="">All</option>
              {(filterOptions[key] || []).map((option) => (
                <option key={option} value={option}>{labelText(option)}</option>
              ))}
            </select>
          </label>
        ))}
      </div>
      <div className="overflow-hidden rounded-xl border border-border/80 bg-card shadow-sm [contain:paint]">
        <div className="overflow-x-auto">
        {/* Explicit column totals avoid Firefox's max-content overflow with spanning headers. */}
        <table
          className="type-table-cell min-w-full table-fixed border-separate border-spacing-0 text-left type-numeric"
          style={{ width: `calc(${annotations.visible ? 18 : 11}rem + ${columns.reduce((width, col) => width + matrixColumnWidth(col.isgl_label || col.isgl_key), 0)}px)` }}
        >
          <colgroup>
            <col className="w-44" />
            {annotations.visible && <col className="w-28" />}
            {columns.map((col) => (
              <col
                key={col.key}
                style={{ width: matrixColumnWidth(col.isgl_label || col.isgl_key) }}
              />
            ))}
          </colgroup>
          <thead className="catalog-matrix-header type-table-header sticky top-0 z-20 border-b-2 border-border text-foreground shadow-sm">
            <tr>
              <th rowSpan={3} className="sticky left-0 z-30 border-b-2 border-r border-border matrix-head-list px-3 py-1.5 text-center align-middle text-xs font-medium uppercase text-foreground">
                Gene
              </th>
              {annotations.visible && (
                <th rowSpan={3} className="matrix-head-list border-b-2 border-r border-border px-2 py-1.5 text-center align-middle whitespace-normal [overflow-wrap:anywhere]">
                  Annotations
                </th>
              )}
              {headerSpans.mod.map((span, index) => (
                <th
                  key={span.key}
                  colSpan={span.span}
                  className="matrix-head-mod border-b border-r border-border px-3 py-2.5 text-center align-middle text-xs font-medium uppercase text-primary last:border-r-0"
                  title={span.label}
                  style={index > 0 ? matrixBoundaryStyle("matrix-section") : undefined}
                >
                  <span className="block whitespace-normal leading-tight [overflow-wrap:anywhere]">
                    {matrixModalityLabel(span.label)}
                  </span>
                </th>
              ))}
            </tr>
            <tr>
              {headerSpans.assayGroup.map((span, index) => (
                <th
                  key={span.key}
                  colSpan={span.span}
                  className="matrix-head-group border-b border-r border-border px-3 py-2 text-center align-middle text-foreground last:border-r-0"
                  style={index > 0 ? matrixBoundaryStyle("matrix-group") : undefined}
                >
                  <span className="block whitespace-normal leading-tight [overflow-wrap:anywhere]">
                    {labelText(span.label)}
                  </span>
                </th>
              ))}
            </tr>
            <tr>
              {columns.map((col, index) => {
                const boundary = matrixBoundaryClass(columns, index)
                return (
                  <th
                    key={col.key}
                    className="matrix-head-list border-b-2 border-r border-border px-1.5 py-1.5 text-center align-middle type-label font-medium uppercase text-foreground last:border-r-0"
                    title={col.isgl_key}
                    style={matrixBoundaryStyle(boundary)}
                  >
                    <span className="block whitespace-normal leading-tight [overflow-wrap:anywhere]">
                      {col.isgl_label || col.isgl_key}
                    </span>
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {genes.map((gene) => (
              <tr key={gene} className="bg-[var(--paper-raised)] transition-colors duration-75 hover:bg-primary/10 dark:hover:bg-primary/20">
                <th className="sticky left-0 z-10 border-b border-r border-border/40 bg-card px-3 py-1 text-sm font-semibold">
                  <div className="flex max-w-40 flex-wrap items-center gap-1">
                    <Link
                      to={`/public/gene/${encodeURIComponent(gene)}/info`}
                      className="link-text transition-colors duration-100"
                    >
                      {gene}
                    </Link>
                  </div>
                </th>
                {annotations.visible && (
                  <td className="border-b border-r border-border/40 px-2 py-1">
                    <KnowledgebaseGeneTags markers={geneMarkers[gene]} tiny />
                  </td>
                )}
                {columns.map((col) => {
                  const present = Boolean(matrix?.[gene]?.[col.mod]?.[col.cat]?.[col.isgl_key])
                  return (
                    <td
                      key={`${gene}:${col.key}`}
                      className="h-7 border-b border-r border-border/40 px-0.5 py-1 text-center last:border-r-0"
                    >
                      {present ? (
                        <Check className="mx-auto h-4 w-4 rounded-full text-pass" strokeWidth={2.4} />
                      ) : (
                        <span className="text-muted-foreground/65">-</span>
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>
      <div className="mt-2 text-right text-xs font-normal text-muted-foreground">
        Showing {genes.length} of {total} gene(s) across {columns.length} visible catalog column(s)
        {appliedGeneSearch ? ` for "${appliedGeneSearch}"` : ""}
      </div>
    </div>
  )
}
