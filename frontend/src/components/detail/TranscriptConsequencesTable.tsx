import { Button } from "@/components/ui/button"
import { Link } from "react-router-dom"
import { DetailDataTable, EvidenceBadge } from "@/components/detail/DetailEvidenceCards"
import { ExpandableText } from "@/components/detail/ExpandableText"
import { ConsequenceBadges, ImpactBadge, InfoTooltipBadge } from "@/lib/variant-ui"

type TranscriptRow = Record<string, unknown>

type ConsequenceTranslations = Record<
  string,
  {
    label?: string
    display_name?: string
    description?: string
    definition?: string
    tooltip?: string
    impact?: string
    IMPACT?: string
  }
>

type TranscriptTagMeta = {
  label: string
  short: string
  description: string
  severity: string
}

const TRANSCRIPT_TAGS: Record<string, TranscriptTagMeta> = {
  ncbi_mane_plus_clinical: {
    label: "NCBI MANE Plus Clinical",
    short: "NCBI MANE+",
    description: "HGNC marks this RefSeq transcript as MANE Plus Clinical for clinically relevant reporting contexts.",
    severity: "success",
  },
  ensembl_mane_plus_clinical: {
    label: "Ensembl MANE Plus Clinical",
    short: "ENS MANE+",
    description: "HGNC and VEP identify this Ensembl transcript as MANE Plus Clinical.",
    severity: "success",
  },
  ncbi_mane_select: {
    label: "NCBI MANE Select",
    short: "NCBI MANE",
    description: "HGNC maps this transcript to the RefSeq MANE Select transcript for the gene.",
    severity: "info",
  },
  ensembl_mane_select: {
    label: "Ensembl MANE Select",
    short: "ENS MANE",
    description: "HGNC maps this transcript to the Ensembl MANE Select transcript for the gene.",
    severity: "info",
  },
  vep_canonical: {
    label: "VEP canonical transcript",
    short: "VEP canonical",
    description: "VEP marks this transcript as canonical for the gene.",
    severity: "neutral",
  },
}

function TranscriptTagBadges({ row }: { row: TranscriptRow }) {
  const tags = Array.isArray(row.transcript_tags) ? row.transcript_tags.map(String).filter(Boolean) : []
  if (!tags.length) return null

  return (
    <span className="mt-1 flex flex-wrap items-center gap-1">
      {tags.map((tag) => {
        const meta = TRANSCRIPT_TAGS[tag] || {
          label: tag.replaceAll("_", " "),
          short: tag.replaceAll("_", " "),
          description: "Transcript provenance marker carried from VEP or reference-gene metadata.",
          severity: "neutral",
        }
        return (
          <InfoTooltipBadge key={tag} label={meta.label} description={meta.description} severity={meta.severity}>
            {meta.short}
          </InfoTooltipBadge>
        )
      })}
    </span>
  )
}

function CanonicalTranscriptBadge({ row }: { row: TranscriptRow }) {
  const source = row.canonical_source
  const isCanonical = Boolean(row.is_canonical || source || row.CANONICAL === "YES")
  if (!isCanonical) return <span className="text-muted-foreground">-</span>

  const isVepCanonical = source === "vep_canonical"
  const label = isVepCanonical ? "VEP canonical" : "Canonical"
  return (
    <InfoTooltipBadge
      label={label}
      description={isVepCanonical ? "The transcript is marked canonical by VEP for this gene." : "The transcript is marked canonical in the stored annotation."}
      severity="neutral"
    >
      {label}
    </InfoTooltipBadge>
  )
}

export function TranscriptConsequencesTable({
  rows,
  selectedFeature,
  consequenceTranslations,
  onSelectTranscript,
  selecting,
}: {
  rows: TranscriptRow[]
  selectedFeature: string
  consequenceTranslations?: ConsequenceTranslations
  onSelectTranscript: (featureId: string) => void
  selecting: boolean
}) {
  return (
    <DetailDataTable
      rows={rows}
      empty="No alternate transcript annotations available."
      columns={[
        {
          key: "gene",
          header: "Gene",
          render: (row) => (
            <span className="inline-flex items-center gap-1.5">
              {row.SYMBOL ? (
                <Link
                  to={`/public/gene/${encodeURIComponent(String(row.SYMBOL))}/info`}
                  className="link-text font-semibold"
                >
                  {String(row.SYMBOL)}
                </Link>
              ) : (
                <span>-</span>
              )}
              {row.Feature === selectedFeature ? <EvidenceBadge tone="success">Selected</EvidenceBadge> : null}
            </span>
          ),
        },
        {
          key: "feature",
          header: "Transcript",
          render: (row) => (
            <span className="block min-w-44">
              <span className="font-mono">{String(row.Feature || "-")}</span>
              <TranscriptTagBadges row={row} />
            </span>
          ),
        },
        { key: "canonical", header: "Canonical", render: (row) => <CanonicalTranscriptBadge row={row} /> },
        { key: "hgvsc", header: "cDNA", render: (row) => <ExpandableText text={String(row.HGVSc || "-")} maxLength={28} className="font-mono" /> },
        { key: "hgvsp", header: "Protein", render: (row) => <ExpandableText text={String(row.HGVSp || "-")} maxLength={28} className="font-mono" /> },
        {
          key: "consequence",
          header: "Consequence",
          className: "min-w-80",
          render: (row) => <ConsequenceBadges value={row.Consequence} translations={consequenceTranslations} compact={false} wide />,
        },
        { key: "exon", header: "Exon/Intron", render: (row) => String(row.EXON || row.INTRON || "-") },
        { key: "impact", header: "Impact", render: (row) => <ImpactBadge value={row.IMPACT} /> },
        {
          key: "actions",
          header: "Actions",
          render: (row) => (
            row.Feature === selectedFeature ? (
              <EvidenceBadge tone="success">Primary</EvidenceBadge>
            ) : (
              <Button
                size="sm"
                variant="outline"
                className="h-7 px-2 text-xs"
                disabled={!row.Feature || selecting}
                onClick={() => onSelectTranscript(String(row.Feature))}
              >
                Use transcript
              </Button>
            )
          ),
        },
      ]}
    />
  )
}
