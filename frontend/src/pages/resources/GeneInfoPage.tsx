import { DataTable } from "@/components/data-table/DataTable"
import {
  GeneKnowledgebaseSummary,
  type GeneKnowledgebasePayload,
} from "@/components/knowledgebase/GeneKnowledgebaseSummary"
import { PageShell } from "@/components/layout/PageShell"
import { api } from "@/lib/api"
import { clinGenGeneUrl, ensemblGeneSummaryUrl, geneCardsUrl, hgncReportUrl, ncbiGeneUrl, omimEntryUrl } from "@/lib/external-links"
import { useQuery } from "@tanstack/react-query"
import { ColumnDef } from "@tanstack/react-table"
import { CalendarDays, Database, Dna, ExternalLink, Fingerprint, Link2, MapPinned, Tags } from "lucide-react"
import { useParams } from "react-router-dom"
import { ChipList, ErrorBox, InfoTile, Loading, SectionTitle } from "./resource-presentation"
import { asList, display, formatCoordinate, formatDate } from "./resource-values"

export function GeneInfoPage() {
  const { geneId = "" } = useParams()
  const { data, isLoading, error } = useQuery({
    queryKey: ["gene-info", geneId],
    queryFn: () => api.get(`/knowledgebases/gene/${geneId}`).then((res) => res.data),
    enabled: Boolean(geneId),
  })

  const gene = data?.gene || data?.payload || data || {}
  const symbol = gene.hgnc_symbol || gene.symbol || geneId
  const hgncId = gene.hgnc_id || gene._id
  const aliases = gene.aliases || gene.alias_symbol || []
  const previousSymbols = gene.previous_symbols || gene.prev_symbol || []
  const previousNames = gene.prev_name || []
  const refseq = asList(gene.refseq_accession)
  const mane = [gene.refseq_mane_select, gene.ensembl_mane_select].filter(Boolean)
  const manePlusClinical = asList(gene.refseq_mane_plus_clinical)
  const cosmicIds = asList(gene.cosmic)
  const omimIds = asList(gene.omim_id)
  const transcriptInfo = gene.addtional_transcript_info || gene.additional_transcript_info || {}
  const links = [
    hgncId && { label: "HGNC", href: hgncReportUrl(hgncId) },
    gene.ensembl_gene_id && { label: "Ensembl", href: ensemblGeneSummaryUrl(gene.ensembl_gene_id) },
    gene.entrez_id && { label: "NCBI", href: ncbiGeneUrl(gene.entrez_id) },
    symbol && { label: "GeneCards", href: geneCardsUrl(symbol) },
    symbol && { label: "ClinGen", href: clinGenGeneUrl(symbol) },
  ].filter(Boolean) as { label: string; href: string }[]
  const transcriptRows = Object.entries(transcriptInfo || {}).map(([transcript, value]: [string, any]) => ({
    transcript,
    start: value?.start,
    end: value?.end,
    length: value?.length,
    start_site: value?.start_site,
  }))
  const transcriptColumns: ColumnDef<any, any>[] = [
    { id: "transcript", header: "Transcript", accessorKey: "transcript", cell: ({ row }) => <span className="text-xs font-bold">{row.original.transcript}</span> },
    { id: "start", header: "Start", accessorFn: (row) => formatCoordinate(row.start) },
    { id: "end", header: "End", accessorFn: (row) => formatCoordinate(row.end) },
    { id: "length", header: "Length", accessorFn: (row) => formatCoordinate(row.length) },
    { id: "start_site", header: "Start site", accessorFn: (row) => formatCoordinate(row.start_site) },
  ]

  return (
    <PageShell
      eyebrow="Gene"
      title={symbol}
      description={gene.gene_name || gene.gene_description || "Curated HGNC gene metadata and external reference identifiers."}
    >
      {isLoading ? <Loading /> : error ? <ErrorBox error={error} /> : (
        <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_25rem]">
          <section className="surface-panel p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-primary">{display(hgncId)}</p>
                <h2 className="mt-1 text-2xl font-semibold">{symbol}</h2>
                <p className="mt-1 max-w-4xl text-sm font-semibold text-muted-foreground">{display(gene.gene_name)}</p>
              </div>
              <span className="rounded-full border border-pass/30 bg-pass/10 px-3 py-1 text-xs font-semibold uppercase text-pass">
                {display(gene.status)}
              </span>
            </div>
            {gene.gene_description && (
              <p className="mt-4 rounded-lg border border-border bg-muted/35 p-3 text-sm leading-relaxed text-foreground">
                {gene.gene_description}
              </p>
            )}

            <dl className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
              <InfoTile label="HGNC ID" value={hgncId} mono />
              <InfoTile label="Entrez ID" value={gene.entrez_id} mono />
              <InfoTile label="Ensembl gene" value={gene.ensembl_gene_id} mono />
              <InfoTile label="Locus type" value={gene.locus} />
            </dl>
          </section>

          <aside className="space-y-3">
            <section className="surface-panel p-4">
              <SectionTitle icon={ExternalLink}>External Links</SectionTitle>
              <div className="mt-3 flex flex-wrap gap-2">
                {links.length ? links.map((link) => (
                  <a key={link.label} href={link.href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted">
                    {link.label}
                    <ExternalLink className="h-4 w-4" />
                  </a>
                )) : <p className="text-sm text-muted-foreground">No external identifiers available.</p>}
              </div>
            </section>

            <section className="surface-panel p-4">
              <SectionTitle icon={Tags}>Aliases</SectionTitle>
              <div className="space-y-3">
                <div>
                  <p className="mb-1 type-label font-semibold uppercase tracking-wide text-muted-foreground">Alias symbols</p>
                  <ChipList values={aliases} />
                </div>
                <div>
                  <p className="mb-1 type-label font-semibold uppercase tracking-wide text-muted-foreground">Previous symbols</p>
                  <ChipList values={previousSymbols} />
                </div>
                <div>
                  <p className="mb-1 type-label font-semibold uppercase tracking-wide text-muted-foreground">Previous names</p>
                  <ChipList values={previousNames} />
                </div>
              </div>
            </section>
          </aside>

          <div className="xl:col-span-2">
            <GeneKnowledgebaseSummary payload={data as GeneKnowledgebasePayload} />
          </div>

          <section className="surface-panel p-4">
            <SectionTitle icon={MapPinned}>Genomic Location</SectionTitle>
            <dl className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
              <InfoTile label="Chromosome" value={gene.chromosome} />
              <InfoTile label="Start" value={formatCoordinate(gene.start)} mono />
              <InfoTile label="End" value={formatCoordinate(gene.end)} mono />
              <InfoTile label="GC content" value={gene.gene_gc_content ? `${Number(gene.gene_gc_content).toFixed(2)}%` : "-"} />
              <InfoTile label="Sortable locus" value={gene.locus_sortable} mono />
              <InfoTile label="Other chromosome" value={gene.other_chromosome} />
            </dl>
          </section>

          <section className="surface-panel p-4">
            <SectionTitle icon={Dna}>Transcripts</SectionTitle>
            <div className="space-y-3">
              <div>
                <p className="mb-1 type-label font-semibold uppercase tracking-wide text-muted-foreground">MANE select</p>
                <ChipList values={mane} empty="No MANE select transcript recorded" />
              </div>
              <div>
                <p className="mb-1 type-label font-semibold uppercase tracking-wide text-muted-foreground">MANE plus clinical</p>
                <ChipList values={manePlusClinical} empty="No MANE plus clinical transcript recorded" />
              </div>
              <div>
                <p className="mb-1 type-label font-semibold uppercase tracking-wide text-muted-foreground">RefSeq accessions</p>
                <ChipList values={refseq} empty="No RefSeq accessions recorded" />
              </div>
            </div>
          </section>

          <section className="surface-panel p-4">
            <SectionTitle icon={Database}>Clinical And Database References</SectionTitle>
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <p className="mb-1 type-label font-semibold uppercase tracking-wide text-muted-foreground">OMIM</p>
                <div className="flex flex-wrap gap-1.5">
                  {omimIds.length ? omimIds.map((id) => (
                    <a key={id} href={omimEntryUrl(id)} target="_blank" rel="noreferrer" className="rounded-md border border-border bg-muted px-2 py-1 text-xs font-semibold hover:bg-primary hover:text-primary-foreground">
                      {id}
                    </a>
                  )) : <span className="text-sm text-muted-foreground">No OMIM identifiers recorded</span>}
                </div>
              </div>
              <div>
                <p className="mb-1 type-label font-semibold uppercase tracking-wide text-muted-foreground">COSMIC</p>
                <ChipList values={cosmicIds} empty="No COSMIC identifiers recorded" />
              </div>
              <div>
                <p className="mb-1 type-label font-semibold uppercase tracking-wide text-muted-foreground">Gene type</p>
                <ChipList values={gene.gene_type} empty="No gene type recorded" />
              </div>
              <div>
                <p className="mb-1 type-label font-semibold uppercase tracking-wide text-muted-foreground">Special references</p>
                <ChipList values={[gene.imgt, gene.lncrnadb, gene.lncipedia].filter(Boolean)} empty="No special references recorded" />
              </div>
            </div>
          </section>

          <section className="surface-panel p-4">
            <SectionTitle icon={CalendarDays}>Record Dates</SectionTitle>
            <dl className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
              <InfoTile label="Approved/reserved" value={formatDate(gene.date_approved_reserved)} />
              <InfoTile label="Symbol changed" value={formatDate(gene.date_symbol_changed)} />
              <InfoTile label="Name changed" value={formatDate(gene.date_name_changed)} />
              <InfoTile label="Modified" value={formatDate(gene.date_modified)} />
            </dl>
          </section>

          {transcriptRows.length > 0 && (
            <section className="surface-panel p-3 xl:col-span-2">
              <div className="mb-2 px-1">
                <SectionTitle icon={Fingerprint}>Additional Transcript Coordinates</SectionTitle>
              </div>
              <DataTable columns={transcriptColumns} data={transcriptRows} filename={`${symbol}_transcripts.csv`} />
            </section>
          )}

          {gene.pseudogene_org?.length > 0 && (
            <section className="surface-panel p-4 xl:col-span-2">
              <SectionTitle icon={Link2}>Pseudogene Orthologs</SectionTitle>
              <ChipList values={gene.pseudogene_org} />
            </section>
          )}
        </div>
      )}
    </PageShell>
  )
}
