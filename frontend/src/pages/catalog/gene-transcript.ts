/** HGNC reference fields used only to choose the catalog's displayed transcript. */
export type GeneTranscriptMetadata = {
  refseq_mane_plus_clinical?: string[]
  ensembl_mane_plus_clinical?: string[]
  refseq_mane_select?: string
  ensembl_mane_select?: string
  refseq_accession?: string[]
  addtional_transcript_info?: Record<string, unknown>
}

type Transcript = {
  id: string
  badge: string
  description: string
  className: string
}

function firstTranscript(values: string[]): string | undefined {
  return values.map(value => value.trim()).filter(Boolean)
    .sort((a, b) => a.localeCompare(b, "en", { numeric: true }))[0]
}

/** Select one display accession; this does not change finding transcript selection. */
export function catalogGeneTranscript(gene: GeneTranscriptMetadata): Transcript | undefined {
  const priorities = [
    [gene.refseq_mane_plus_clinical || [], "RS MC+", "RefSeq MANE Plus Clinical", "badge-transcript-refseq"],
    [gene.ensembl_mane_plus_clinical || [], "ENS MC+", "Ensembl MANE Plus Clinical", "badge-transcript-ensembl"],
    [[gene.refseq_mane_select || ""], "RS MANE", "RefSeq MANE Select", "badge-transcript-refseq"],
    [[gene.ensembl_mane_select || ""], "ENS MANE", "Ensembl MANE Select", "badge-transcript-ensembl"],
  ] as const
  for (const [values, badge, description, className] of priorities) {
    const id = firstTranscript([...values])
    if (id) return { id, badge, description, className }
  }
  // Gene-level biotype cannot establish the biotype of an arbitrary ENST accession.
  // NM_/XM_ RefSeq accessions identify coding transcripts, unlike NR_/XR_ or ENSG IDs.
  const id = firstTranscript([
    ...(gene.refseq_accession || []),
    ...Object.keys(gene.addtional_transcript_info || {}),
  ].filter(value => /^(NM|XM)_/.test(value)))
  return id ? { id, badge: "PC", description: "Protein-coding RefSeq transcript (no MANE designation)",
    className: "badge-transcript-protein-coding" } : undefined
}
