import { Link } from "react-router-dom"
import { ExternalLink, Info } from "lucide-react"
import { cn } from "@/lib/utils"
import { isOncoKbGene, type OncoKbGeneRecord } from "@/lib/oncokb-ui"
import { oncokbGeneUrl } from "@/lib/external-links"

export type KnowledgebaseGeneMarkers = {
  oncokb?: boolean
  cosmic_cgc?: boolean
  civic?: boolean
  clinpgx?: boolean
  clinpgx_accession?: string | null
}

const markerStyles = {
  oncokb: "border-tier3/35 bg-tier3/10 text-tier3",
  cosmic_cgc: "border-loss/35 bg-loss/10 text-loss",
  civic: "border-info/35 bg-info/10 text-info",
  clinpgx: "border-pass/35 bg-pass/10 text-pass",
}

export function KnowledgebaseGeneTags({
  markers,
  compact = false,
}: {
  markers?: KnowledgebaseGeneMarkers | null
  compact?: boolean
}) {
  const tags = [
    ["oncokb", "OncoKB", "OncoKB public cancer gene"],
    ["cosmic_cgc", "CGC", "COSMIC Cancer Gene Census gene"],
    ["civic", "CIViC", "CIViC curated gene"],
    ["clinpgx", "PGx", "ClinPGx / PharmGKB gene"],
  ] as const
  const visible = tags.filter(([key]) => markers?.[key])
  if (!visible.length) return null
  return (
    <span className="inline-flex min-w-0 flex-wrap items-center gap-1" aria-label="Knowledgebase sources">
      {visible.map(([key, label, title]) => (
        <span
          key={key}
          className={cn(
            "inline-flex items-center rounded-full border font-semibold leading-none",
            compact ? "h-4 px-1 type-label" : "h-5 px-1.5 type-label",
            markerStyles[key],
          )}
          title={title}
        >
          {label}
        </span>
      ))}
    </span>
  )
}

export function OncoKbGeneBadge({
  gene,
  record,
  className,
}: {
  gene: string
  record?: OncoKbGeneRecord | null
  className?: string
}) {
  const summary =
    record?.description ||
    record?.geneSummary ||
    record?.gene_summary ||
    record?.summary ||
    `${gene} is present in the OncoKB public gene cache.`
  return (
    <a
      href={oncokbGeneUrl(gene)}
      target="_blank"
      rel="noreferrer"
      className={cn(
        "inline-flex h-5 items-center gap-1 rounded-full border border-tier3/35 bg-tier3/10 px-1.5 type-label font-semibold uppercase leading-none text-tier3 shadow-sm transition-colors hover:bg-tier3/18",
        className,
      )}
      title={summary}
      aria-label={`${gene} is an OncoKB gene`}
    >
      OncoKB
      <ExternalLink className="h-2.5 w-2.5" />
    </a>
  )
}

export function GeneWithOncoKbBadge({
  gene,
  displayGene,
  resolvedGene,
  hgncId,
  matchSource,
  oncokbGenes,
  record,
  markers,
  showOncoKbBadge = true,
  geneTo,
  className,
}: {
  gene?: string
  displayGene?: string
  resolvedGene?: string
  hgncId?: string | null
  matchSource?: string
  oncokbGenes?: string[] | Record<string, OncoKbGeneRecord>
  record?: OncoKbGeneRecord | null
  markers?: KnowledgebaseGeneMarkers | null
  showOncoKbBadge?: boolean
  geneTo?: string
  className?: string
}) {
  const shownGene = displayGene || gene
  const currentGene = resolvedGene || gene
  if (!shownGene) return <span className={className}>-</span>
  const showBadge = showOncoKbBadge && (record || isOncoKbGene(currentGene, oncokbGenes))
  const geneHrefId = hgncId ? String(hgncId).replace("HGNC:", "") : currentGene
  const hasSymbolChange = Boolean(
    currentGene && shownGene && currentGene.toUpperCase() !== shownGene.toUpperCase(),
  )
  const symbolTitle =
    matchSource === "previous_symbol"
      ? `${shownGene} is a previous HGNC symbol. Current approved symbol: ${currentGene}.`
      : matchSource === "alias_symbol"
        ? `${shownGene} is an HGNC alias. Current approved symbol: ${currentGene}.`
        : `Current HGNC approved symbol: ${currentGene}.`
  return (
    <span className={cn("inline-flex min-w-0 items-center gap-1.5", className)}>
      <Link
        to={geneTo || `/public/gene/${encodeURIComponent(String(geneHrefId || shownGene))}/info`}
        className="link-text truncate font-medium"
        title={hasSymbolChange ? symbolTitle : String(shownGene)}
      >
        {shownGene}
      </Link>
      {hasSymbolChange && (
        <span
          className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-primary/25 bg-primary/10 text-primary"
          title={symbolTitle}
          aria-label={symbolTitle}
        >
          <Info className="h-3 w-3" />
        </span>
      )}
      {showBadge && <OncoKbGeneBadge gene={currentGene || shownGene} record={record} />}
      <KnowledgebaseGeneTags markers={markers} compact />
    </span>
  )
}
