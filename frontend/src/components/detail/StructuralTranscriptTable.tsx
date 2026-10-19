import { DetailDataTable, EvidenceBadge } from "@/components/detail/DetailEvidenceCards"
import { ConsequenceBadges } from "@/lib/variant-ui"

type Partner = { gene: string; transcript: string; mane_flags: string[] }
export type StructuralTranscriptRow = {
  annotation_key: string
  partners: Partner[]
  annotation: { HGVSp?: string; HGVSc?: string; Annotation?: string[] }
}

const maneLabels: Record<string, string> = {
  ncbi_mane_select: "NCBI MANE Select",
  ensembl_mane_select: "Ensembl MANE Select",
  ncbi_mane_plus_clinical: "NCBI MANE Plus Clinical",
  ensembl_mane_plus_clinical: "Ensembl MANE Plus Clinical",
}

function TranscriptPartner({ partner }: { partner?: Partner }) {
  return <div className="space-y-1">
    <span>{partner?.transcript || "—"}</span>
    <div className="flex flex-wrap gap-1">
      {partner?.mane_flags.map(flag => <EvidenceBadge key={flag} tone="success">
        {maneLabels[flag] || flag}
      </EvidenceBadge>)}
    </div>
  </div>
}

export function StructuralTranscriptTable({ rows, selectedKey, canSelect, pending, onSelect, translations }: {
  rows: StructuralTranscriptRow[]
  selectedKey?: string
  canSelect: boolean
  pending: boolean
  onSelect: (key: string) => void
  translations: Record<string, { display_name?: string; description?: string }>
}) {
  return <DetailDataTable rows={rows} empty="No transcript combinations available." columns={[
    { key: "selection", header: "Selection", render: row => row.annotation_key === selectedKey
      ? <EvidenceBadge tone="success">Selected</EvidenceBadge>
      : canSelect ? <button type="button" disabled={pending}
        aria-label={`Select ${row.partners.map(p => p.transcript).join(" / ")}`}
        className="rounded-md border border-border px-2 py-1 type-meta text-primary hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
        onClick={() => onSelect(row.annotation_key)}>Select</button> : null },
    { key: "gene1", header: "Gene 1", render: row => row.partners[0]?.gene || "—" },
    { key: "transcript1", header: "Transcript 1", render: row => <TranscriptPartner partner={row.partners[0]} /> },
    { key: "gene2", header: "Gene 2", render: row => row.partners[1]?.gene || "—" },
    { key: "transcript2", header: "Transcript 2", render: row => <TranscriptPartner partner={row.partners[1]} /> },
    { key: "protein", header: "Protein", render: row => row.annotation.HGVSp || "—" },
    { key: "cdna", header: "cDNA", render: row => row.annotation.HGVSc || "—" },
    { key: "consequence", header: "SnpEff consequence", render: row => <ConsequenceBadges value={row.annotation.Annotation} translations={translations} wide /> },
  ]} />
}
