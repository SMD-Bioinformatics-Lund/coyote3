import { MetricCard, SurfacePanel } from "@/components/cards/Panel"
import { DataTable } from "@/components/data-table/DataTable"
import { AppLoader } from "@/components/layout/AppLoader"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"
import { shortCount } from "@/lib/detail-formatters"
import { sampleFilterSection } from "@/lib/sample-shape"
import { useQuery } from "@tanstack/react-query"
import { ColumnDef } from "@tanstack/react-table"
import { AlertTriangle, Search } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { coverageNumber, flattenCoverageTable, metric } from "./coverage-presentation"
import { CoverageGeneView } from "./CoverageGeneView"

export function CoverageTab({ sampleId, sample }: { sampleId: string; sample?: any }) {
  const configuredCutoff = Number(sampleFilterSection(sample, "coverage").warn_cov)
  const cutoff = Number.isFinite(configuredCutoff) && configuredCutoff > 0 ? configuredCutoff : 500
  const [selectedGene, setSelectedGene] = useState<string | null>(null)
  const [geneSearch, setGeneSearch] = useState("")
  const { data, isLoading, error } = useQuery({
    queryKey: ["sample-coverage", sampleId, cutoff],
    queryFn: () => api.get(`/samples/${sampleId}/coverage?cov_cutoff=${cutoff}`).then((res) => res.data),
    retry: false,
  })

  const rows = useMemo(() => flattenCoverageTable(data?.cov_table), [data])
  const coveredGenes = Object.keys(data?.coverage?.genes || {}).length
  const geneNames = useMemo(() => Object.keys(data?.coverage?.genes || {}).sort(), [data])
  const geneSummaries = useMemo(() => {
    return geneNames.map((gene) => {
      const geneRows = rows.filter((row) => row.gene === gene)
      const values = geneRows.map((row) => coverageNumber(row)).filter(Number.isFinite)
      const min = values.length ? Math.min(...values) : Number.NaN
      return { gene, count: geneRows.length, min }
    })
  }, [geneNames, rows])
  const filteredGeneSummaries = useMemo(() => {
    const query = geneSearch.trim().toLowerCase()
    if (!query) return geneSummaries
    return geneSummaries.filter((item) => item.gene.toLowerCase().includes(query))
  }, [geneSearch, geneSummaries])
  const selectedGeneData = selectedGene ? data?.coverage?.genes?.[selectedGene] : null
  const selectedRows = selectedGene ? rows.filter((row) => row.gene === selectedGene) : rows

  useEffect(() => {
    if (!geneNames.length) {
      setSelectedGene(null)
      return
    }
    setSelectedGene((current) => current && geneNames.includes(current) ? current : geneNames[0])
  }, [geneNames])

  const columns: ColumnDef<any, any>[] = [
    {
      id: "gene",
      header: "Gene",
      accessorFn: (row) => row.gene,
      cell: ({ row }) => (
        <button
          type="button"
          onClick={() => setSelectedGene(row.original.gene)}
          className="font-bold text-primary underline-offset-2 hover:underline"
        >
          {row.original.gene}
        </button>
      ),
    },
    {
      id: "region",
      header: "Region",
      accessorFn: (row) => row.region || row.nbr || "-",
      cell: ({ row }) => <span className="text-xs">{row.original.region || row.original.nbr || "-"}</span>,
    },
    {
      id: "chrom",
      header: "Chrom",
      accessorFn: (row) => row.chrom || row.chr || "-",
      cell: ({ row }) => <span className="text-xs">{row.original.chrom || row.original.chr || "-"}</span>,
    },
    {
      id: "start",
      header: "Start",
      accessorFn: (row) => Number(row.start || 0),
      cell: ({ row }) => <span className="text-xs">{metric(row.original.start)}</span>,
    },
    {
      id: "end",
      header: "End",
      accessorFn: (row) => Number(row.end || 0),
      cell: ({ row }) => <span className="text-xs">{metric(row.original.end)}</span>,
    },
    {
      id: "coverage",
      header: "Coverage",
      accessorFn: (row) => Number(row.cov || 0),
      cell: ({ row }) => {
        const value = Number(row.original.cov)
        return (
          <span className={`text-xs font-bold ${Number.isFinite(value) && value < cutoff ? "text-fail" : "text-pass"}`}>
            {Number.isFinite(value) ? value.toFixed(1) : "-"}
          </span>
        )
      },
    },
    {
      id: "exon",
      header: "Exon",
      accessorFn: (row) => row.exon || row.exon_nr || row.nbr || "-",
      cell: ({ row }) => {
        const value = row.original.exon_nr || row.original.exon || row.original.nbr
        return <span className="text-xs">{Array.isArray(value) ? value.map((item: any) => item.nbr || item).join(", ") : value || "-"}</span>
      },
    },
  ]

  if (isLoading) return <AppLoader label="Loading coverage" />
  if (error) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
        <AlertTriangle className="mr-2 inline h-4 w-4" />
        {error instanceof Error ? error.message : "Error loading coverage"}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <SurfacePanel
        title="Coverage"
        description="Low-covered genes, exon/CDS/probe coverage, and blacklist controls for the active assay design."
      >
        <div className="grid gap-2 sm:grid-cols-3">
          <MetricCard title="Low regions" value={shortCount(rows.length)} />
          <MetricCard title="Genes with coverage" value={shortCount(coveredGenes)} />
          <MetricCard title="Assay group" value={data?.smp_grp || "-"} className="uppercase" />
        </div>
      </SurfacePanel>

      <div className="coverage-split-layout flex min-w-0 flex-col gap-3 md:flex-row">
        <aside className="coverage-sidebar min-w-0 space-y-3">
          <SurfacePanel
            title="Low-Coverage Genes"
            description={geneSearch.trim()
              ? `${filteredGeneSummaries.length} of ${geneNames.length} gene(s) below ${cutoff}X`
              : `${geneNames.length} gene(s) below ${cutoff}X`}
            actions={
              <div className="relative w-full sm:w-48">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  type="search"
                  value={geneSearch}
                  onChange={(event) => setGeneSearch(event.target.value)}
                  placeholder="Search genes..."
                  aria-label="Search low-coverage genes"
                  className="h-8 pl-8 text-xs"
                />
              </div>
            }
          >
            <div className="max-h-[28rem] space-y-1 overflow-y-auto pr-1">
              {filteredGeneSummaries.map((item) => (
                <button
                  key={item.gene}
                  type="button"
                  onClick={() => setSelectedGene(item.gene)}
                  className={`flex w-full items-center justify-between gap-2 rounded-lg border px-2.5 py-2 text-left transition-colors ${
                    selectedGene === item.gene
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border bg-background/70 hover:bg-muted"
                  }`}
                >
                  <span className="min-w-0">
                    <span className="block truncate text-xs font-medium">{item.gene}</span>
                    <span className="type-label text-muted-foreground">{item.count} low region(s)</span>
                  </span>
                  <span className="rounded-md bg-fail/10 px-1.5 py-0.5 type-label font-bold text-fail">
                    {Number.isFinite(item.min) ? `${item.min.toFixed(1)}X` : "-"}
                  </span>
                </button>
              ))}
              {!geneSummaries.length && (
                <p className="rounded-lg border border-dashed border-border p-3 text-xs text-muted-foreground">
                  No low-covered genes for the current cutoff and selected gene lists.
                </p>
              )}
              {geneSummaries.length > 0 && !filteredGeneSummaries.length && (
                <p className="rounded-lg border border-dashed border-border p-3 text-xs text-muted-foreground">
                  No low-coverage genes match {geneSearch.trim()}.
                </p>
              )}
            </div>
          </SurfacePanel>

          <SurfacePanel title="Low Regions">
            <DataTable columns={columns} data={selectedRows} filename={`coverage_${sampleId}.csv`} />
          </SurfacePanel>
        </aside>

        <div className="coverage-main min-w-0 flex-1 space-y-3">
          {selectedGene && selectedGeneData ? (
            <CoverageGeneView gene={selectedGene} geneData={selectedGeneData} cutoff={cutoff} smpGrp={data?.smp_grp || ""} />
          ) : (
            <div className="rounded-xl border border-dashed border-border bg-card/60 px-4 py-8 text-center text-sm text-muted-foreground">
              Select a gene from the low-coverage list to inspect transcript coverage, exons, probes, and blacklist low regions.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
