import { DataTable } from "@/components/data-table/DataTable"
import { GeneWithOncoKbBadge, type KnowledgebaseGeneMarkers } from "@/components/knowledgebase/OncoKbGeneBadge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import { valueBadgeClass } from "@/lib/badge-colors"
import { cn } from "@/lib/utils"
import { useQuery } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"
import { Clock3, Dna, FileText, FlaskConical, Layers, Microscope, Package, ShieldCheck } from "lucide-react"
import { useId, useMemo, useState, type ReactNode } from "react"
import { BadgeList, HtmlText } from "./catalog-presentation"
import { familyLabels, offeringPrice, type Offering } from "./offering-types"
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
type GeneRow = GeneMetadata & { lists: string[] }

const geneColumns: ColumnDef<GeneRow>[] = [
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
    meta: { exportValue: (row: GeneRow) => {
      const transcript = catalogGeneTranscript(row)
      return transcript ? `${transcript.id} (${transcript.description})` : ""
    } },
  },
  { id: "lists", header: "Published gene lists", accessorFn: row => row.lists.join(", "),
    cell: ({ row }) => <BadgeList values={row.original.lists} /> },
]

function DetailCard({ title, icon: Icon, children }: {
  title: string; icon: typeof FileText; children: ReactNode
}) {
  return <section className="paper-surface min-w-0 space-y-3 rounded-xl p-4">
    <h3 className="type-section-title flex items-center gap-2"><Icon className="size-4 text-primary" />{title}</h3>
    <div className="type-body-sm leading-relaxed">{children}</div>
  </section>
}

export function CatalogOfferingDetails({ offering: item }: { offering: Offering }) {
  const id = useId()
  const analyses = [...new Set([...item.analysis, ...item.gene_scopes.map(scope => scope.analysis)])]
  const [chosenAnalysis, setChosenAnalysis] = useState("SNV")
  const analysis = analyses.includes(chosenAnalysis) ? chosenAnalysis : analyses[0] || ""
  const scopes = item.gene_scopes.filter(scope => scope.analysis === analysis)
  const uniqueGenes = new Set(item.gene_scopes.flatMap(scope => scope.genes))
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
    const memberships = new Map<string, string[]>()
    for (const scope of item.gene_scopes.filter(scope => scope.analysis === analysis)) {
      for (const symbol of new Set(scope.genes)) {
        const labels = memberships.get(symbol) || []
        if (!labels.includes(scope.label)) labels.push(scope.label)
        memberships.set(symbol, labels)
      }
    }
    return [...memberships].sort(([a], [b]) => a.localeCompare(b)).map(([symbol, lists]) => ({
      ...metadata.get(symbol), hgnc_symbol: metadata.get(symbol)?.hgnc_symbol || symbol,
      display_symbol: symbol, lists,
    }))
  }, [data, item.gene_scopes, analysis])

  return <article className="min-w-0 space-y-5">
    <header data-modality={item.modality} data-family={item.family} className="surface-panel catalog-service-card space-y-5 p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className={valueBadgeClass(item.modality)}>{item.modality === "dna" ? <Dna /> : <FlaskConical />}{item.modality.toUpperCase()}</Badge>
            <Badge variant="outline" className={valueBadgeClass(item.family)}>{familyLabels[item.family] || item.family}</Badge>
            <span className="type-body-sm text-muted-foreground">{item.group_label} · {item.diagnosis_label}</span>
          </div>
          <h2 className="type-page-title break-words">{item.assay_display_name || item.title}</h2>
          {item.assay_display_name && item.assay_display_name !== item.title && <p className="type-body-sm text-muted-foreground">{item.title}</p>}
        </div>
        <div className="paper-surface max-w-full rounded-lg p-4">
          <p className="type-label mb-1 text-muted-foreground">Service pricing</p>
          <p className="type-title font-semibold">{offeringPrice(item)}</p>
          {item.price?.conditions && <p className="mt-1 type-body-sm">{item.price.conditions}</p>}
        </div>
      </div>
      <HtmlText html={item.description} className="type-body leading-relaxed" />
      <div className="grid gap-3 sm:grid-cols-3">
        <DetailCard title="Turnaround" icon={Clock3}>{item.turnaround || "Contact the service"}</DetailCard>
        <DetailCard title="Published genes" icon={Dna}><strong className="type-title">{uniqueGenes.size}</strong> unique genes across published analyses</DetailCard>
        <DetailCard title="Available analyses" icon={Microscope}><BadgeList values={item.analysis} /></DetailCard>
      </div>
      {item.diagnosis_id === "base" && <p className="type-body-sm text-muted-foreground">General testing uses the published Base scope, without a named diagnosis.</p>}
    </header>

    <section className="surface-panel min-w-0 space-y-4 p-5" aria-labelledby={`${id}-scope`}>
      <div className="space-y-2">
        <h3 id={`${id}-scope`} className="type-section-title flex items-center gap-2"><Layers className="size-4 text-primary" />Clinical gene scope</h3>
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
        {error && <p role="status" className="type-body-sm text-muted-foreground">HGNC reference information is unavailable. Published gene symbols and list memberships are still shown.</p>}
        {rows.length ? <DataTable key={`${item.offering_id}:${analysis}`} columns={geneColumns} data={rows}
          filename={`${item.offering_id}_${analysis.toLowerCase()}_genes.csv`} />
          : <p className="paper-inset rounded-lg p-4 type-body-sm text-muted-foreground">No public gene list is published for {analysis || "this offering"}.</p>}
        <p className="type-meta text-muted-foreground">HGNC annotations reflect the current reference database. Published genes and gene-list revisions remain fixed to this catalog publication. A dash indicates unavailable metadata.</p>
      </div>
    </section>

    <div className="grid gap-4 md:grid-cols-2">
      <DetailCard title="Reporting" icon={FileText}><BadgeList values={item.report_deliverables} empty="Contact the service for report deliverables." /></DetailCard>
      <DetailCard title="Specimen requirements" icon={Package}><BadgeList values={item.input_material} empty="Contact the service for specimen requirements." /></DetailCard>
      <DetailCard title="Methodology" icon={Microscope}>{item.methodology || familyLabels[item.family] || item.family}</DetailCard>
      <DetailCard title="Analytical limitations" icon={ShieldCheck}>{item.limitations ? <HtmlText html={item.limitations} /> : "Contact the service for analytical limitations."}</DetailCard>
    </div>
    <DetailCard title="Ordering information" icon={FileText}><p className="whitespace-pre-wrap">{item.ordering_information || "Contact the center for eligibility and submission instructions."}</p></DetailCard>
  </article>
}
