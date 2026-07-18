import { useMemo, useState, type FormEvent, type ReactNode } from "react"
import { Link } from "react-router-dom"
import { useMutation, useQuery } from "@tanstack/react-query"
import { Activity, Check, Download, Grid2X2, Info, ListTree, Search, X } from "lucide-react"
import { api } from "@/lib/api"
import { DataTable } from "@/components/data-table/DataTable"
import { PageShell } from "@/components/layout/PageShell"
import { ColumnDef } from "@tanstack/react-table"
import { GeneWithOncoKbBadge } from "@/components/knowledgebase/OncoKbGeneBadge"

export function PublicCatalog() {
  const [selection, setSelection] = useState<{ mod?: string; cat?: string; isgl_key?: string }>({})
  const params = new URLSearchParams()
  if (selection.mod) params.set("mod", selection.mod)
  if (selection.cat) params.set("cat", selection.cat)
  if (selection.isgl_key) params.set("isgl_key", selection.isgl_key)

  const { data, isLoading, error } = useQuery({
    queryKey: ["public-catalog", selection],
    queryFn: () => api.get(`/public/assay-catalog/context?${params.toString()}`).then((res) => res.data),
  })

  const downloadCsv = useMutation({
    mutationFn: () => {
      const csvParams = new URLSearchParams()
      if (selection.mod) csvParams.set("mod", selection.mod)
      if (selection.cat) csvParams.set("cat", selection.cat)
      if (selection.isgl_key) csvParams.set("isgl_key", selection.isgl_key)
      return api.get(`/public/assay-catalog/genes.csv/context?${csvParams.toString()}`).then((res) => res.data)
    },
    onSuccess: (payload) => {
      const blob = new Blob([payload.content || ""], { type: "text/csv;charset=utf-8" })
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = payload.filename || "assay_catalog_genes.csv"
      link.click()
      URL.revokeObjectURL(url)
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
    const availableKeys = new Set<string>(genes.flatMap((gene: any) => Object.keys(gene || {})))
    const keys = preferredKeys
      .filter((key) => availableKeys.has(key))
      .concat(Array.from(availableKeys).filter((key) => !preferredKeys.includes(key)))
      .slice(0, 8)
    return keys.map((key) => ({
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
  }, [data])
  const right = data?.right || {}

  return (
    <PageShell
      eyebrow="Public"
      title="Assay Catalog"
      description="Explore assay modalities, categories, gene lists, and covered genes."
      actions={
        <>
          <button
            onClick={() => downloadCsv.mutate()}
            disabled={!selection.mod || downloadCsv.isPending}
            className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted disabled:opacity-50"
          >
            {downloadCsv.isPending ? <Activity className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            Catalog CSV
          </button>
          <Link to="/public/matrix" className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted">
            <Grid2X2 className="h-4 w-4" />
            Matrix
          </Link>
        </>
      }
    >
      {isLoading ? (
        <div className="flex justify-center p-10"><Activity className="animate-spin text-muted-foreground" /></div>
      ) : error ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          {error instanceof Error ? error.message : "Unable to load catalog"}
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[22rem_1fr]">
          <div className="space-y-3 rounded-xl border border-border bg-card p-3 shadow-sm">
            <h2 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-muted-foreground">
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
                          className="mb-2 rounded-md bg-muted/45 px-2 py-1.5 text-[11px] leading-relaxed text-muted-foreground"
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
                                  className={`mb-1 block w-full rounded-md px-2 py-1 text-left text-[11px] font-semibold hover:bg-muted ${selection.isgl_key === gl.key ? "bg-genelist/10 text-genelist" : "text-muted-foreground"}`}
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

          <div className="space-y-4">
            <section className="rounded-xl border border-border bg-card p-4 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="text-xl font-bold">{right.title || right.label || "Assay Catalog"}</h2>
                  {right.subheading && <p className="mt-1 text-sm font-semibold text-primary">{right.subheading}</p>}
                  {right.description && <HtmlText html={right.description} className="mt-2 max-w-5xl text-sm leading-relaxed text-muted-foreground" />}
                </div>
                {(right.catalog_id || right.asp_id || right.aspc_id || right.subpanel_id) && (
                  <div className="flex max-w-full flex-wrap justify-end gap-1.5">
                    {right.catalog_id && <CatalogBadge label="Catalog" value={right.catalog_id} />}
                    {right.asp_id && <CatalogBadge label="ASP" value={right.asp_id} />}
                    {right.aspc_id && <CatalogBadge label="ASPC" value={right.aspc_id} />}
                    {right.subpanel_id && right.subpanel_id !== "base" && <CatalogBadge label="Subpanel" value={right.subpanel_id} />}
                  </div>
                )}
              </div>

              <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                <CatalogField label="Input material">
                  <BadgeList values={right.input_material} empty="Not configured" />
                </CatalogField>
                <CatalogField label="TAT">
                  <span className="font-semibold">{formatScalar(right.tat)}</span>
                </CatalogField>
                <CatalogField label="Sample types">
                  <BadgeList values={right.sample_modes} empty="Not configured" />
                </CatalogField>
                <CatalogField label="Genes">
                  <span className="font-black text-primary">{data?.stats?.total ?? 0}</span>
                  <span className="ml-2 text-xs text-muted-foreground">
                    covered {data?.stats?.covered_total ?? 0}
                    {typeof data?.stats?.germline_total === "number" ? `, germline ${data.stats.germline_total}` : ""}
                  </span>
                </CatalogField>
              </div>

              <div className="mt-3 grid gap-2 md:grid-cols-2">
                <CatalogField label="Available analysis">
                  <BadgeList values={right.analysis} empty="Not configured" tone="primary" />
                </CatalogField>
                <CatalogField label="Reporting sections">
                  <BadgeList values={right.report_sections} empty="Not configured" tone="secondary" />
                </CatalogField>
              </div>

              {(right.clinical_indications?.length || right.limitations || right.public_notes || right.asp) && (
                <div className="mt-3 grid gap-2 lg:grid-cols-3">
                  <CatalogField label="Clinical indications">
                    <BadgeList values={right.clinical_indications} empty="Not configured" tone="success" />
                  </CatalogField>
                  <CatalogField label="Limitations">
                    <HtmlText html={right.limitations || "Not configured"} className="text-sm leading-relaxed text-foreground" />
                  </CatalogField>
                  <CatalogField label="Technical assay details">
                    <div className="flex flex-wrap gap-1.5">
                      {right.asp?.platform && <CatalogBadge label="Platform" value={right.asp.platform} />}
                      {right.asp?.read_mode && <CatalogBadge label="Read mode" value={right.asp.read_mode} />}
                      {right.asp?.read_length && <CatalogBadge label="Read length" value={right.asp.read_length} />}
                      {!right.asp?.platform && !right.asp?.read_mode && !right.asp?.read_length && <span className="text-sm text-muted-foreground">Not configured</span>}
                    </div>
                  </CatalogField>
                </div>
              )}

              {right.public_notes && (
                <div className="mt-3 rounded-lg border border-primary/20 bg-primary/5 p-3">
                  <div className="mb-1 flex items-center gap-2 text-xs font-black uppercase tracking-wide text-primary">
                    <Info className="h-3.5 w-3.5" />
                    Notes
                  </div>
                  <HtmlText html={right.public_notes} className="text-sm leading-relaxed text-foreground" />
                </div>
              )}

              <AdditionalCatalogDetails value={right} />

              {Array.isArray(right.gene_lists) && right.gene_lists.length > 0 && (
                <div className="mt-4">
                  <h3 className="mb-2 text-xs font-black uppercase tracking-wide text-muted-foreground">Configured gene lists</h3>
                  <div className="grid gap-2 lg:grid-cols-2">
                    {right.gene_lists.filter((gl: any) => gl?.key || gl?.label).map((gl: any) => (
                      <button
                        key={gl.key || gl.label}
                        type="button"
                        onClick={() => gl.key && setSelection({ mod: selection.mod, cat: selection.cat, isgl_key: gl.key })}
                        className={`rounded-lg border p-3 text-left transition-colors hover:bg-muted/60 ${
                          selection.isgl_key === gl.key ? "border-primary bg-primary/5" : "border-border bg-background/60"
                        }`}
                      >
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <span className="font-bold text-foreground">{gl.label || gl.key}</span>
                          {gl.tat && <CatalogBadge label="TAT" value={gl.tat} />}
                        </div>
                        {gl.description && <HtmlText html={gl.description} className="mt-1 line-clamp-3 text-xs leading-relaxed text-muted-foreground" />}
                        <div className="mt-2 flex flex-wrap gap-1">
                          <BadgeList values={gl.analysis} empty="" tone="primary" compact />
                          <BadgeList values={gl.sample_modes} empty="" compact />
                          <BadgeList values={gl.input_material} empty="" tone="secondary" compact />
                          <BadgeList values={gl.list_type} empty="" tone="success" compact />
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </section>

            <section className="rounded-xl border border-border bg-card p-3 shadow-sm">
              <DataTable columns={geneColumns} data={data?.genes || []} filename="assay_catalog_genes.csv" />
            </section>
          </div>
        </div>
      )}
    </PageShell>
  )
}

function asArray(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((item) => String(item ?? "").trim()).filter(Boolean)
  if (value === null || value === undefined || value === "") return []
  return [String(value)]
}

function formatScalar(value: unknown) {
  const values = asArray(value)
  return values.length ? values.join(", ") : "-"
}

function HtmlText({ html, className }: { html: unknown; className?: string }) {
  const text = String(html ?? "").trim()
  if (!text) return null
  return <div className={className} dangerouslySetInnerHTML={{ __html: text }} />
}

function CatalogField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-muted/30 p-3">
      <span className="mb-1.5 block text-[10px] font-black uppercase tracking-wide text-muted-foreground">{label}</span>
      {children}
    </div>
  )
}

const FIRST_CLASS_CATALOG_FIELDS = new Set([
  "analysis",
  "asp",
  "asp_id",
  "aspc_id",
  "aspc_ids",
  "catalog_id",
  "clinical_indications",
  "description",
  "gene_lists",
  "input_material",
  "label",
  "limitations",
  "public_notes",
  "report_sections",
  "sample_modes",
  "sample_query",
  "subheading",
  "subpanel_id",
  "tat",
  "title",
])

function AdditionalCatalogDetails({ value }: { value: Record<string, unknown> }) {
  const entries = Object.entries(value || {})
    .filter(([key, item]) => !FIRST_CLASS_CATALOG_FIELDS.has(key) && item !== null && item !== undefined && item !== "")
    .filter(([, item]) => {
      if (Array.isArray(item)) return item.length > 0
      if (typeof item === "object") return Object.keys(item as Record<string, unknown>).length > 0
      return true
    })

  if (!entries.length) return null

  return (
    <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
      {entries.map(([key, item]) => (
        <CatalogField key={key} label={key.replaceAll("_", " ")}>
          {Array.isArray(item) ? (
            <BadgeList values={item} empty="-" />
          ) : typeof item === "object" ? (
            <div className="space-y-1 text-xs text-muted-foreground">
              {Object.entries(item as Record<string, unknown>).map(([innerKey, innerValue]) => (
                <div key={innerKey} className="flex gap-2">
                  <span className="font-bold uppercase text-foreground/70">{innerKey.replaceAll("_", " ")}</span>
                  <span>{formatScalar(innerValue)}</span>
                </div>
              ))}
            </div>
          ) : (
            <HtmlText html={item} className="text-sm leading-relaxed text-foreground" />
          )}
        </CatalogField>
      ))}
    </div>
  )
}

function CatalogBadge({ label, value }: { label?: string; value: unknown }) {
  return (
    <span className="inline-flex max-w-full items-center gap-1 rounded-full border border-primary/20 bg-primary/8 px-2 py-0.5 text-xs font-semibold text-primary">
      {label && <span className="text-primary/70">{label}</span>}
      <span className="truncate">{formatScalar(value)}</span>
    </span>
  )
}

function BadgeList({
  values,
  empty = "-",
  tone = "default",
  compact = false,
}: {
  values: unknown
  empty?: string
  tone?: "default" | "primary" | "secondary" | "success"
  compact?: boolean
}) {
  const list = asArray(values)
  if (!list.length) {
    return empty ? <span className="text-sm text-muted-foreground">{empty}</span> : null
  }
  const toneClass = {
    default: "border-border bg-background text-foreground",
    primary: "border-primary/25 bg-primary/8 text-primary",
    secondary: "border-rna/25 bg-rna/10 text-rna",
    success: "border-pass/25 bg-pass/10 text-pass",
  }[tone]
  return (
    <div className="flex flex-wrap gap-1.5">
      {list.map((item) => (
        <span
          key={item}
          className={`${toneClass} rounded-full border px-2 ${compact ? "py-0 text-[10px]" : "py-0.5 text-xs"} font-semibold`}
        >
          {item}
        </span>
      ))}
    </div>
  )
}

export function PublicCatalogMatrix() {
  const [filters, setFilters] = useState<Record<string, string>>({})
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(100)
  const [geneSearch, setGeneSearch] = useState("")
  const [appliedGeneSearch, setAppliedGeneSearch] = useState("")
  const { data, isLoading, error } = useQuery({
    queryKey: ["public-catalog-matrix", page, perPage, appliedGeneSearch],
    queryFn: () => {
      const params = new URLSearchParams()
      params.set("page", String(page))
      params.set("per_page", String(perPage))
      if (appliedGeneSearch.trim()) params.set("gene", appliedGeneSearch.trim())
      return api.get(`/public/assay-catalog-matrix/context?${params.toString()}`).then((res) => res.data)
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
      description="Gene coverage matrix across public assay catalog modalities and gene lists."
      actions={
        <Link to="/public/catalog" className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted">
          Catalog
        </Link>
      }
    >
      {isLoading ? (
        <div className="flex justify-center p-10"><Activity className="animate-spin text-muted-foreground" /></div>
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
            setPerPage(next)
            setPage(1)
          }}
        />
      )}
    </PageShell>
  )
}

function labelText(value: unknown) {
  const text = String(value || "-").trim()
  if (text.toLowerCase() === "base") return "Assay-wide"
  return text.replaceAll("_", " ").replaceAll("-", " ")
}

function uniqueOptions(values: string[]) {
  return Array.from(new Set(values.filter((value) => value && value !== "-"))).sort((a, b) => a.localeCompare(b))
}

function contiguousSpans<T>(
  items: T[],
  keyFn: (item: T) => string,
  labelFn: (item: T) => string = keyFn,
) {
  const spans: Array<{ key: string; label: string; span: number }> = []
  for (const item of items) {
    const key = keyFn(item)
    const label = labelFn(item)
    const last = spans[spans.length - 1]
    if (last?.key === key) last.span += 1
    else spans.push({ key, label, span: 1 })
  }
  return spans
}

function matrixBoundaryClass(columns: any[], index: number) {
  if (index <= 0) return ""
  const previous = columns[index - 1]
  const current = columns[index]
  if (previous?.mod !== current?.mod) return "matrix-section"
  if (`${previous?.mod}::${previous?.assayGroup}` !== `${current?.mod}::${current?.assayGroup}`) {
    return "matrix-group"
  }
  return ""
}

function matrixBoundaryStyle(boundary: string) {
  if (boundary === "matrix-section") {
    return {
      boxShadow: "inset 4px 0 0 color-mix(in srgb, var(--primary) 58%, var(--border))",
    }
  }
  if (boundary === "matrix-group") {
    return {
      boxShadow: "inset 3px 0 0 color-mix(in srgb, var(--primary) 38%, var(--border))",
    }
  }
  return undefined
}

function AssayMatrixTable({
  columns,
  filters,
  filterOptions,
  onFilterChange,
  genes,
  matrix,
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

  return (
    <div className="rounded-xl border border-border bg-card p-3 shadow-sm">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-black text-foreground">Assay Catalog - Gene Coverage Matrix</h2>
        <div className="flex flex-wrap items-center justify-end gap-1.5">
          <label className="flex items-center gap-2 text-[10px] font-black uppercase tracking-wide text-muted-foreground">
            Rows
            <select
              value={perPage}
              disabled={Boolean(appliedGeneSearch)}
              onChange={(event) => onPerPageChange(Number(event.target.value))}
              className="h-8 rounded-lg border border-input bg-background px-2 text-xs font-semibold text-foreground disabled:opacity-50"
            >
              {[50, 100, 200, 500].map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <button
            type="button"
            disabled={!hasPrevious}
            onClick={() => onPageChange(Math.max(1, page - 1))}
            className="h-8 rounded-lg border border-border px-3 text-xs font-bold hover:bg-muted disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-xs font-semibold text-muted-foreground">Page {page}</span>
          <button
            type="button"
            disabled={!hasNext}
            onClick={() => onPageChange(page + 1)}
            className="h-8 rounded-lg border border-border px-3 text-xs font-bold hover:bg-muted disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <form onSubmit={onGeneSearchSubmit} className="flex min-w-[18rem] max-w-[34rem] flex-1 flex-wrap items-end gap-2">
          <label className="grid min-w-[14rem] flex-1 gap-1 text-[10px] font-black uppercase tracking-wide text-muted-foreground">
            Gene search
            <input
              value={geneSearch}
              onChange={(event) => onGeneSearchChange(event.target.value)}
              className="h-8 rounded-lg border border-input bg-background px-2.5 text-xs font-semibold normal-case tracking-normal text-foreground"
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

      <div className="mb-3 grid gap-2 md:grid-cols-3">
        {[
          ["mod", "Modality"],
          ["assayGroup", "Section"],
          ["list", "Gene list"],
        ].map(([key, label]) => (
          <label key={key} className="grid gap-1 text-[10px] font-black uppercase tracking-wide text-muted-foreground">
            {label}
            <select
              value={filters[key] || ""}
              onChange={(event) => updateFilter(key, event.target.value)}
              className="h-8 rounded-lg border border-input bg-background px-2 text-xs font-semibold normal-case tracking-normal text-foreground"
            >
              <option value="">All</option>
              {(filterOptions[key] || []).map((option) => (
                <option key={option} value={option}>{labelText(option)}</option>
              ))}
            </select>
          </label>
        ))}
      </div>
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full min-w-max table-fixed border-collapse text-left text-xs">
          <colgroup>
            <col className="w-44" />
            {columns.map((col) => (
              <col key={col.key} className="w-32" />
            ))}
          </colgroup>
          <thead className="sticky top-0 z-20 bg-card shadow-sm">
            <tr>
              <th rowSpan={3} className="sticky left-0 z-30 border border-border matrix-head-list px-3 py-2 text-center align-middle text-xs font-black uppercase text-foreground">
                Gene
              </th>
              {headerSpans.mod.map((span, index) => (
                <th
                  key={span.key}
                  colSpan={span.span}
                  className="matrix-head-mod border border-border px-3 py-3 text-center align-middle text-xs font-black uppercase tracking-wider text-primary"
                  style={index > 0 ? matrixBoundaryStyle("matrix-section") : undefined}
                >
                  <span className="inline-block max-w-full truncate">
                    {labelText(span.label)}
                  </span>
                </th>
              ))}
            </tr>
            <tr>
              {headerSpans.assayGroup.map((span, index) => (
                <th
                  key={span.key}
                  colSpan={span.span}
                  className="matrix-head-group border border-border px-3 py-2.5 text-center align-middle text-[11px] font-black uppercase tracking-wider text-foreground"
                  style={index > 0 ? matrixBoundaryStyle("matrix-group") : undefined}
                >
                  <span className="inline-block max-w-full truncate">
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
                    className="matrix-head-list border border-border px-2 py-2 text-center align-middle text-[10px] font-black uppercase text-foreground"
                    title={col.isgl_key}
                    style={matrixBoundaryStyle(boundary)}
                  >
                    <span className="block truncate whitespace-normal leading-tight">{col.isgl_label || col.isgl_key}</span>
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {genes.map((gene) => (
              <tr key={gene} className="hover:bg-primary/5">
                <th className="sticky left-0 z-10 border border-border bg-card px-3 py-1.5 text-xs font-black text-primary">
                  {gene}
                </th>
                {columns.map((col) => {
                  const present = Boolean(matrix?.[gene]?.[col.mod]?.[col.cat]?.[col.isgl_key])
                  return (
                    <td
                      key={`${gene}:${col.key}`}
                      className="h-7 border border-border px-2 py-1 text-center"
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
      <div className="mt-2 text-right text-xs font-semibold text-muted-foreground">
        Showing {genes.length} of {total} gene(s) across {columns.length} visible catalog column(s)
        {appliedGeneSearch ? ` for "${appliedGeneSearch}"` : ""}
      </div>
    </div>
  )
}
