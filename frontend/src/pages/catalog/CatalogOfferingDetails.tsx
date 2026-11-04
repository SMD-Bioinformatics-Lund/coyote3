import { DataTable } from "@/components/data-table/DataTable"
import { GeneWithOncoKbBadge, type KnowledgebaseGeneMarkers } from "@/components/knowledgebase/OncoKbGeneBadge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import { valueBadgeClass } from "@/lib/badge-colors"
import { cn } from "@/lib/utils"
import { useQuery } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"
import { icon as appIcon } from "@/lib/assets"
import { useId, useMemo, useState } from "react"
import { CatalogInformation } from "./CatalogInformation"
import { type CatalogNavigationNode, type Offering } from "./offering-types"
import { offeringInformation } from "./catalog-information"
import { catalogGeneTranscript, type GeneTranscriptMetadata } from "./gene-transcript"

type GeneMetadata = GeneTranscriptMetadata & {
  hgnc_symbol: string
  display_symbol?: string
  hgnc_id?: string | null
  gene_name?: string
  chromosome?: string
  locus?: string
  knowledgebase_markers?: KnowledgebaseGeneMarkers
}
const geneColumns: ColumnDef<GeneMetadata>[] = [
  { accessorKey: "hgnc_symbol", header: "HGNC symbol", cell: ({ row }) =>
    <GeneWithOncoKbBadge gene={row.original.hgnc_symbol} displayGene={row.original.display_symbol}
      hgncId={row.original.hgnc_id} markers={row.original.knowledgebase_markers} showOncoKbBadge={false} /> },
  { accessorKey: "gene_name", header: "Gene name", cell: ({ getValue }) =>
    <span className="block max-w-80 whitespace-normal">{String(getValue() || "-")}</span> },
  { accessorKey: "hgnc_id", header: "HGNC ID", cell: ({ getValue }) => String(getValue() || "-") },
  { accessorKey: "chromosome", header: "Chromosome", cell: ({ getValue }) => String(getValue() || "-") },
  { accessorKey: "locus", header: "Locus", cell: ({ getValue }) => String(getValue() || "-") },
  { id: "transcript", header: "Transcript", accessorFn: row => catalogGeneTranscript(row)?.id || "",
    cell: ({ row }) => {
      const transcript = catalogGeneTranscript(row.original)
      return transcript ? <span className="flex flex-wrap items-center gap-1.5">
        <span className="type-numeric">{transcript.id}</span>
        <Badge variant="outline" className={transcript.className} title={transcript.description}
          aria-label={transcript.description}>{transcript.badge}</Badge>
      </span> : <span className="text-muted-foreground">-</span>
    },
    meta: { exportValue: (row: GeneMetadata) => {
      const transcript = catalogGeneTranscript(row)
      return transcript ? `${transcript.id} (${transcript.description})` : ""
    } },
  },
]

export function CatalogOfferingDetails({ offering: item, information, showInformation = true }: {
  offering: Offering; information?: CatalogNavigationNode; showInformation?: boolean
}) {
  const id = useId()
  const analyses = [...new Set([...item.analysis, ...item.gene_scopes.map(scope => scope.analysis)])]
  const [chosenAnalysis, setChosenAnalysis] = useState("SNV")
  const analysis = analyses.includes(chosenAnalysis) ? chosenAnalysis : analyses[0] || ""
  const scopes = item.gene_scopes.filter(scope => scope.analysis === analysis)
  const { data, isLoading, error } = useQuery<{ gene_details: GeneMetadata[] }>({
    queryKey: ["public-asp-genes", item.assay_id],
    queryFn: () => api.get(`/public/asp/${encodeURIComponent(item.assay_id)}/genes`).then(res => res.data),
    enabled: item.gene_scopes.length > 0,
    retry: false,
  })
  const rows = useMemo(() => {
    const metadata = new Map<string, GeneMetadata>()
    for (const gene of data?.gene_details || []) {
      metadata.set(gene.hgnc_symbol, gene)
      if (gene.display_symbol) metadata.set(gene.display_symbol, gene)
    }
    const symbols = new Set(item.gene_scopes.filter(scope => scope.analysis === analysis)
      .flatMap(scope => scope.genes))
    return [...symbols].sort((a, b) => a.localeCompare(b)).map(symbol => ({
      ...metadata.get(symbol), hgnc_symbol: metadata.get(symbol)?.hgnc_symbol || symbol,
      display_symbol: symbol,
    }))
  }, [data, item.gene_scopes, analysis])

  return <article className="min-w-0 space-y-5">
    {showInformation && <CatalogInformation information={offeringInformation(item, information)} offerings={[item]} />}

    <section className="surface-panel catalog-service-card catalog-information min-w-0 space-y-4 p-5"
      data-modality={item.modality} data-family={item.family} aria-labelledby={`${id}-scope`}>
      <div className="space-y-2">
        {!showInformation && <p className="type-section-title">{item.assay_display_name || item.assay_label} · {item.diagnosis_label}</p>}
        <h3 id={`${id}-scope`} className="type-section-title flex items-center gap-2"><appIcon.layers className="size-4 text-primary" />Clinical gene scope</h3>
        <p className="type-body-sm text-muted-foreground">Choose an analysis to explore its published genes and HGNC reference information. Gene scope is limited to the published lists and validated assay coverage.</p>
      </div>
      <div role="tablist" aria-label="Gene scope by analysis" className="flex flex-wrap gap-2">
        {analyses.map((value, index) => <Button key={value} variant="outline" role="tab"
          id={`${id}-tab-${value}`} aria-controls={`${id}-genes`} aria-selected={value === analysis}
          tabIndex={value === analysis ? 0 : -1}
          className={cn(valueBadgeClass(value), value === analysis && "ring-2 ring-ring ring-offset-2 ring-offset-background")}
          onClick={() => setChosenAnalysis(value)}
          onKeyDown={event => {
            if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) return
            event.preventDefault()
            const next = event.key === "Home" ? 0 : event.key === "End" ? analyses.length - 1
              : (index + (event.key === "ArrowRight" ? 1 : -1) + analyses.length) % analyses.length
            setChosenAnalysis(analyses[next])
            document.getElementById(`${id}-tab-${analyses[next]}`)?.focus()
          }}>
          {value.toLowerCase() === "fusion" ? "Fusion" : value}
          <span className="rounded-full bg-background/70 px-1.5 type-meta">{new Set(item.gene_scopes.filter(scope => scope.analysis === value).flatMap(scope => scope.genes)).size}</span>
        </Button>)}
      </div>
      <div id={`${id}-genes`} role="tabpanel" aria-labelledby={analysis ? `${id}-tab-${analysis}` : `${id}-scope`} className="min-w-0 space-y-4">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {scopes.map(scope => <div key={`${scope.list_id}:${scope.analysis}`} className="paper-surface space-y-1 rounded-lg p-3">
            <h4 className="type-body-sm font-semibold">{scope.label}</h4>
            <p className="type-meta text-muted-foreground">Revision {scope.revision} · {scope.genes.length} eligible {scope.genes.length === 1 ? "gene" : "genes"}</p>
            {scope.excluded_gene_count > 0 && <p className="type-meta text-muted-foreground">{scope.excluded_gene_count} list genes outside validated assay coverage</p>}
          </div>)}
        </div>
        {isLoading && <p role="status" className="type-body-sm text-muted-foreground">Loading HGNC reference information…</p>}
        {error && <p role="status" className="type-body-sm text-muted-foreground">HGNC reference information is unavailable. Published gene symbols are still shown.</p>}
        {rows.length ? <DataTable key={`${item.offering_id}:${analysis}`} columns={geneColumns} data={rows}
          filename={`${item.offering_id}_${analysis.toLowerCase()}_genes.csv`} />
          : <p className="paper-inset rounded-lg p-4 type-body-sm text-muted-foreground">No public gene list is published for {analysis || "this offering"}.</p>}
        <p className="type-meta text-muted-foreground">HGNC annotations reflect the current reference database. Published genes and gene-list revisions remain fixed to this catalog publication. A dash indicates unavailable metadata.</p>
      </div>
    </section>

  </article>
}
