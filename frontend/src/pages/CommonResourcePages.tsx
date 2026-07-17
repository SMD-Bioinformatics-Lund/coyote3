import { useMemo } from "react"
import { Link, useParams, useSearchParams } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Activity, ArrowLeft, CalendarDays, Database, Dna, ExternalLink, Fingerprint, Link2, MapPinned, Tags, Trash2 } from "lucide-react"
import { ColumnDef } from "@tanstack/react-table"
import { api } from "@/lib/api"
import { DataTable } from "@/components/data-table/DataTable"
import { CollapsibleJson } from "@/components/detail/JsonInspector"
import { PageShell } from "@/components/layout/PageShell"
import { notifyActionError, notifySuccess } from "@/lib/notifications"

function columnsFor(rows: any[], preferred: string[] = []): ColumnDef<any, any>[] {
  const keys = [...preferred, ...rows.flatMap((row) => Object.keys(row || {}))]
  const seen = new Set<string>()
  return keys
    .filter((key) => {
      if (seen.has(key) || key.startsWith("_rev")) return false
      seen.add(key)
      return rows.some((row) => row?.[key] !== undefined)
    })
    .slice(0, 12)
    .map((key) => ({
      id: key,
      header: key.replaceAll("_", " "),
      accessorFn: (row: any) => {
        const value = row?.[key]
        if (Array.isArray(value)) return value.join(", ")
        if (value && typeof value === "object") return JSON.stringify(value)
        return value ?? ""
      },
      cell: ({ row }) => {
        const value = row.original?.[key]
        const label = Array.isArray(value) ? value.join(", ") : value && typeof value === "object" ? JSON.stringify(value) : String(value ?? "-")
        return <span className="block max-w-[24rem] truncate text-xs" title={label}>{label}</span>
      },
    }))
}

function Loading() {
  return <div className="flex justify-center p-10"><Activity className="animate-spin text-muted-foreground" /></div>
}

function ErrorBox({ error }: { error: unknown }) {
  return (
    <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
      {error instanceof Error ? error.message : "Unable to load data"}
    </div>
  )
}

function asList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((item) => String(item || "").trim()).filter(Boolean)
  if (value === undefined || value === null || value === "") return []
  return String(value).split(/[;,]/).map((item) => item.trim()).filter(Boolean)
}

function display(value: unknown) {
  if (value === undefined || value === null || value === "") return "-"
  if (Array.isArray(value)) return value.length ? value.join(", ") : "-"
  return String(value)
}

function formatDate(value: unknown) {
  if (!value) return "-"
  const date = new Date(String(value))
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleDateString()
}

function formatCoordinate(value: unknown) {
  if (typeof value === "number") return value.toLocaleString()
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed.toLocaleString() : display(value)
}

function InfoTile({ label, value, mono = false }: { label: string; value: unknown; mono?: boolean }) {
  return (
    <div className="rounded-lg border border-border bg-background/70 p-3">
      <dt className="text-[10px] font-black uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className={`mt-1 break-words text-sm font-semibold ${mono ? "font-mono" : ""}`}>{display(value)}</dd>
    </div>
  )
}

function ChipList({ values, empty = "None recorded" }: { values: unknown; empty?: string }) {
  const items = asList(values)
  if (!items.length) return <span className="text-sm text-muted-foreground">{empty}</span>
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span key={item} className="rounded-md border border-border bg-muted px-2 py-1 text-xs font-semibold">
          {item}
        </span>
      ))}
    </div>
  )
}

function SectionTitle({ icon: Icon, children }: { icon: any; children: string }) {
  return (
    <h2 className="mb-3 flex items-center gap-2 text-sm font-black uppercase tracking-wide text-muted-foreground">
      <Icon className="h-4 w-4 text-primary" />
      {children}
    </h2>
  )
}

function stripHtml(value: unknown) {
  return String(value || "").replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim()
}

function HtmlText({ value, className = "" }: { value: unknown; className?: string }) {
  const html = String(value || "").trim()
  if (!html) return null
  return (
    <div
      className={`prose prose-sm max-w-none text-sm leading-relaxed text-muted-foreground dark:prose-invert prose-a:text-primary ${className}`}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}

function BadgeList({
  values,
  empty = "Not specified",
  tone = "default",
}: {
  values: unknown
  empty?: string
  tone?: "default" | "sample" | "analysis" | "material"
}) {
  const items = asList(values)
  const toneClass = {
    default: "border-border bg-muted text-foreground",
    sample: "border-primary/25 bg-primary/10 text-primary",
    analysis: "border-tier2/30 bg-tier2/10 text-tier2",
    material: "border-pass/30 bg-pass/10 text-pass",
  }[tone]
  if (!items.length) return <span className="text-sm text-muted-foreground">{empty}</span>
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span key={item} className={`rounded-full border px-2.5 py-1 text-xs font-black ${toneClass}`}>
          {item}
        </span>
      ))}
    </div>
  )
}

export function GeneInfoPage() {
  const { geneId = "" } = useParams()
  const { data, isLoading, error } = useQuery({
    queryKey: ["gene-info", geneId],
    queryFn: () => api.get(`/common/gene/${geneId}/info`).then((res) => res.data),
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
    hgncId && { label: "HGNC", href: `https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/${String(hgncId).replace("HGNC:", "")}` },
    gene.ensembl_gene_id && { label: "Ensembl", href: `https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=${gene.ensembl_gene_id}` },
    gene.entrez_id && { label: "NCBI", href: `https://www.ncbi.nlm.nih.gov/gene/${gene.entrez_id}` },
    symbol && { label: "GeneCards", href: `https://www.genecards.org/cgi-bin/carddisp.pl?gene=${encodeURIComponent(String(symbol))}` },
    symbol && { label: "ClinGen", href: `https://search.clinicalgenome.org/kb/genes/${encodeURIComponent(String(symbol))}` },
  ].filter(Boolean) as { label: string; href: string }[]
  const transcriptRows = Object.entries(transcriptInfo || {}).map(([transcript, value]: [string, any]) => ({
    transcript,
    start: value?.start,
    end: value?.end,
    length: value?.length,
    start_site: value?.start_site,
  }))
  const transcriptColumns: ColumnDef<any, any>[] = [
    { id: "transcript", header: "Transcript", accessorKey: "transcript", cell: ({ row }) => <span className="font-mono text-xs font-bold">{row.original.transcript}</span> },
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
                <p className="text-xs font-black uppercase tracking-wide text-primary">{display(hgncId)}</p>
                <h2 className="mt-1 text-2xl font-black">{symbol}</h2>
                <p className="mt-1 max-w-4xl text-sm font-semibold text-muted-foreground">{display(gene.gene_name)}</p>
              </div>
              <span className="rounded-full border border-pass/30 bg-pass/10 px-3 py-1 text-xs font-black uppercase text-pass">
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
                  <p className="mb-1 text-[10px] font-black uppercase tracking-wide text-muted-foreground">Alias symbols</p>
                  <ChipList values={aliases} />
                </div>
                <div>
                  <p className="mb-1 text-[10px] font-black uppercase tracking-wide text-muted-foreground">Previous symbols</p>
                  <ChipList values={previousSymbols} />
                </div>
                <div>
                  <p className="mb-1 text-[10px] font-black uppercase tracking-wide text-muted-foreground">Previous names</p>
                  <ChipList values={previousNames} />
                </div>
              </div>
            </section>
          </aside>

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
                <p className="mb-1 text-[10px] font-black uppercase tracking-wide text-muted-foreground">MANE select</p>
                <ChipList values={mane} empty="No MANE select transcript recorded" />
              </div>
              <div>
                <p className="mb-1 text-[10px] font-black uppercase tracking-wide text-muted-foreground">MANE plus clinical</p>
                <ChipList values={manePlusClinical} empty="No MANE plus clinical transcript recorded" />
              </div>
              <div>
                <p className="mb-1 text-[10px] font-black uppercase tracking-wide text-muted-foreground">RefSeq accessions</p>
                <ChipList values={refseq} empty="No RefSeq accessions recorded" />
              </div>
            </div>
          </section>

          <section className="surface-panel p-4">
            <SectionTitle icon={Database}>Clinical And Database References</SectionTitle>
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <p className="mb-1 text-[10px] font-black uppercase tracking-wide text-muted-foreground">OMIM</p>
                <div className="flex flex-wrap gap-1.5">
                  {omimIds.length ? omimIds.map((id) => (
                    <a key={id} href={`https://www.omim.org/entry/${id}`} target="_blank" rel="noreferrer" className="rounded-md border border-border bg-muted px-2 py-1 text-xs font-semibold hover:bg-primary hover:text-primary-foreground">
                      {id}
                    </a>
                  )) : <span className="text-sm text-muted-foreground">No OMIM identifiers recorded</span>}
                </div>
              </div>
              <div>
                <p className="mb-1 text-[10px] font-black uppercase tracking-wide text-muted-foreground">COSMIC</p>
                <ChipList values={cosmicIds} empty="No COSMIC identifiers recorded" />
              </div>
              <div>
                <p className="mb-1 text-[10px] font-black uppercase tracking-wide text-muted-foreground">Gene type</p>
                <ChipList values={gene.gene_type} empty="No gene type recorded" />
              </div>
              <div>
                <p className="mb-1 text-[10px] font-black uppercase tracking-wide text-muted-foreground">Special references</p>
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

export function PublicGenelistPage() {
  const { genelistId = "" } = useParams()
  const [params] = useSearchParams()
  const assay = params.get("assay") || undefined
  const { data, isLoading, error } = useQuery({
    queryKey: ["public-genelist", genelistId, assay],
    queryFn: () => api.get(`/public/genelists/${genelistId}/view_context${assay ? `?assay=${encodeURIComponent(assay)}` : ""}`).then((res) => res.data),
    enabled: Boolean(genelistId),
  })
  const genes = useMemo(() => data?.genes || data?.gene_objects || data?.rows || [], [data])
  const rows = useMemo(() => Array.isArray(genes) ? genes.map((gene: any) => typeof gene === "string" ? { gene } : gene) : [], [genes])
  const columns = useMemo(() => columnsFor(rows, ["hgnc_symbol", "symbol", "gene"]), [rows])

  return (
    <PageShell eyebrow="Public" title={data?.genelist?.name || data?.title || genelistId} description="Public gene list view migrated from the historical catalog.">
      {isLoading ? <Loading /> : error ? <ErrorBox error={error} /> : (
        <div className="space-y-3">
          <section className="surface-panel border-t-4 border-t-genelist p-3">
            <DataTable columns={columns} data={rows} filename={`${genelistId}_genes.csv`} />
          </section>
          <CollapsibleJson title="Genelist Payload" value={data || {}} />
        </div>
      )}
    </PageShell>
  )
}

export function PublicAspGenesPage() {
  const { aspId = "" } = useParams()
  const { data, isLoading, error } = useQuery({
    queryKey: ["public-asp-genes", aspId],
    queryFn: () => api.get(`/public/asp/${aspId}/genes`).then((res) => res.data),
    enabled: Boolean(aspId),
  })
  const genes = useMemo(() => data?.gene_details || data?.genes || data?.gene_objects || [], [data])
  const rows = useMemo(() => Array.isArray(genes) ? genes.map((gene: any) => typeof gene === "string" ? { gene } : gene) : [], [genes])
  const columns = useMemo(() => columnsFor(rows, ["hgnc_symbol", "symbol", "gene", "hgnc_id", "ensembl_gene_id"]), [rows])
  const catalog = data?.catalog || {}
  const asp = data?.asp || {}
  const stats = data?.stats || {}
  const geneLists = Array.isArray(catalog.gene_lists) ? catalog.gene_lists.filter((item: any) => item?.key || item?.label) : []
  const title = catalog.title || catalog.label || asp.display_name || asp.assay_name || aspId
  const description = catalog.description || asp.description || "Assay-panel gene table."
  const subpanel = catalog.subpanel_id && catalog.subpanel_id !== "base" ? catalog.subpanel_id : null

  return (
    <PageShell eyebrow="Public" title={title} description={stripHtml(description) || "Assay-panel gene table."}>
      {isLoading ? <Loading /> : error ? <ErrorBox error={error} /> : (
        <div className="space-y-3">
          <section className="surface-panel p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="mb-2 flex flex-wrap gap-1.5">
                  <span className="rounded-full border border-primary/25 bg-primary/10 px-2.5 py-1 text-xs font-black uppercase text-primary">
                    {catalog.modality_label || catalog.modality || asp.asp_category || "Assay"}
                  </span>
                  {catalog.family && (
                    <span className="rounded-full border border-border bg-muted px-2.5 py-1 text-xs font-black uppercase text-muted-foreground">
                      {catalog.family}
                    </span>
                  )}
                  {catalog.assay_group && (
                    <span className="rounded-full border border-border bg-muted px-2.5 py-1 text-xs font-black uppercase text-muted-foreground">
                      {catalog.assay_group}
                    </span>
                  )}
                  {subpanel && (
                    <span className="rounded-full border border-tier3/30 bg-tier3/10 px-2.5 py-1 text-xs font-black uppercase text-tier3">
                      {subpanel}
                    </span>
                  )}
                </div>
                <h2 className="text-xl font-black">{title}</h2>
                <HtmlText value={description} className="mt-1" />
              </div>
              <Link to="/catalog" className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted">
                Catalog
                <ExternalLink className="h-4 w-4" />
              </Link>
            </div>

            <div className="mt-4 grid gap-3 lg:grid-cols-4">
              <div className="rounded-lg border border-border bg-background/70 p-3">
                <p className="mb-2 text-[10px] font-black uppercase tracking-wide text-muted-foreground">Input material</p>
                <BadgeList values={catalog.input_material} tone="material" />
              </div>
              <div className="rounded-lg border border-border bg-background/70 p-3">
                <p className="mb-2 text-[10px] font-black uppercase tracking-wide text-muted-foreground">Sample types</p>
                <BadgeList values={catalog.sample_modes} tone="sample" />
              </div>
              <InfoTile label="Turnaround time" value={catalog.tat} />
              <InfoTile label="Covered genes" value={stats.covered_total ?? rows.length} />
              <div className="rounded-lg border border-border bg-background/70 p-3">
                <p className="mb-2 text-[10px] font-black uppercase tracking-wide text-muted-foreground">Analysis</p>
                <BadgeList values={catalog.analysis} tone="analysis" />
              </div>
              <div className="rounded-lg border border-border bg-background/70 p-3">
                <p className="mb-2 text-[10px] font-black uppercase tracking-wide text-muted-foreground">Report sections</p>
                <BadgeList values={catalog.report_sections} />
              </div>
              <InfoTile label="Germline genes" value={stats.germline_total ?? data?.germline_gene_symbols?.length ?? 0} />
              <InfoTile label="Platform / read mode" value={[asp.platform, asp.read_mode].filter(Boolean).join(" / ") || "-"} />
            </div>

            {(catalog.clinical_indications?.length > 0 || catalog.limitations || catalog.public_notes) && (
              <div className="mt-4 grid gap-3 lg:grid-cols-3">
                {catalog.clinical_indications?.length > 0 && (
                  <div className="rounded-lg border border-border bg-background/70 p-3">
                    <p className="mb-2 text-[10px] font-black uppercase tracking-wide text-muted-foreground">Clinical indications</p>
                    <BadgeList values={catalog.clinical_indications} />
                  </div>
                )}
                {catalog.limitations && (
                  <div className="rounded-lg border border-border bg-background/70 p-3">
                    <p className="mb-2 text-[10px] font-black uppercase tracking-wide text-muted-foreground">Limitations</p>
                    <HtmlText value={catalog.limitations} />
                  </div>
                )}
                {catalog.public_notes && (
                  <div className="rounded-lg border border-border bg-background/70 p-3">
                    <p className="mb-2 text-[10px] font-black uppercase tracking-wide text-muted-foreground">Notes</p>
                    <HtmlText value={catalog.public_notes} />
                  </div>
                )}
              </div>
            )}
          </section>

          {geneLists.length > 0 && (
            <section className="surface-panel p-4">
              <SectionTitle icon={Tags}>Catalog Gene Lists</SectionTitle>
              <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
                {geneLists.map((list: any) => (
                  <div key={list.key || list.label} className="rounded-lg border border-border bg-background/70 p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h3 className="text-sm font-black">{list.label || list.key}</h3>
                        {list.key && <p className="font-mono text-[11px] font-semibold text-muted-foreground">{list.key}</p>}
                      </div>
                      {list.tat && (
                        <span className="rounded-full border border-border bg-muted px-2 py-1 text-[10px] font-black uppercase text-muted-foreground">
                          {list.tat}
                        </span>
                      )}
                    </div>
                    <HtmlText value={list.description} className="mt-2" />
                    <div className="mt-3 space-y-2">
                      <BadgeList values={list.analysis} empty="Analysis follows assay default" tone="analysis" />
                      <BadgeList values={list.sample_modes} empty="Sample types follow assay default" tone="sample" />
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="surface-panel p-3">
            <DataTable columns={columns} data={rows} filename={`${aspId}_genes.csv`} />
          </section>
        </div>
      )}
    </PageShell>
  )
}

export function CoverageBlacklistPage() {
  const { group = "" } = useParams()
  const queryClient = useQueryClient()
  const { data, isLoading, error } = useQuery({
    queryKey: ["coverage-blacklisted", group],
    queryFn: () => api.get(`/coverage/blacklisted/${group}`).then((res) => res.data),
    enabled: Boolean(group),
  })
  const removeEntry = useMutation({
    mutationFn: (id: string) => api.delete(`/coverage/blacklist/entries/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["coverage-blacklisted", group] })
      notifySuccess("Blacklist entry removed", "The coverage blacklist entry was deleted.", "Coverage")
    },
    onError: (error) => {
      notifyActionError("Unable to remove blacklist entry", error, "Coverage")
    },
  })

  const rows = useMemo(() => {
    const blacklisted = data?.blacklisted || {}
    return Object.entries(blacklisted).flatMap(([gene, info]: [string, any]) => {
      const regions = info?.regions || info?.entries || []
      if (Array.isArray(regions) && regions.length) {
        return regions.map((entry: any) => ({ gene, ...entry, id: entry._id || entry.id || entry.coord || gene }))
      }
      return [{ gene, ...(typeof info === "object" ? info : {}), id: info?._id || info?.id || gene }]
    })
  }, [data])

  const columns: ColumnDef<any, any>[] = [
    ...columnsFor(rows, ["gene", "region", "coord", "smp_grp", "_id"]).slice(0, 8),
    {
      id: "actions",
      header: "Actions",
      cell: ({ row }) => {
        const id = String(row.original._id || row.original.id || row.original.gene)
        return (
          <button
            onClick={() => removeEntry.mutate(id)}
            disabled={removeEntry.isPending}
            className="inline-flex items-center gap-2 rounded-lg border border-destructive/30 px-2 py-1 text-xs font-bold text-destructive hover:bg-destructive/10 disabled:opacity-50"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Remove
          </button>
        )
      },
    },
  ]

  return (
    <PageShell
      eyebrow="Coverage"
      title={`Blacklisted Regions: ${group}`}
      description="Coverage blacklist overview and removal workflow migrated from the historical coverage page."
      actions={<Link to="/samples" className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-semibold hover:bg-muted"><ArrowLeft className="h-4 w-4" /> Samples</Link>}
    >
      {isLoading ? <Loading /> : error ? <ErrorBox error={error} /> : (
        <div className="space-y-3">
          <section className="surface-panel border-t-4 border-t-cnvlist p-3">
            <DataTable columns={columns} data={rows} filename={`coverage_blacklist_${group}.csv`} />
          </section>
          <CollapsibleJson title="Coverage Blacklist Payload" value={data || {}} />
        </div>
      )}
    </PageShell>
  )
}
