import { expect, it } from "vitest"
import { catalogGeneTranscript, type GeneTranscriptMetadata } from "./gene-transcript"

const metadata: GeneTranscriptMetadata = {
  refseq_mane_plus_clinical: ["NM_000002.1", "NM_000001.2"],
  ensembl_mane_plus_clinical: ["ENST000001.1"],
  refseq_mane_select: "NM_000003.1",
  ensembl_mane_select: "ENST000003.1",
  refseq_accession: ["NR_000001.1", "NM_000004.1"],
}

it.each([
  [metadata, "NM_000001.2", "RS MC+"],
  [{ ...metadata, refseq_mane_plus_clinical: [] }, "ENST000001.1", "ENS MC+"],
  [{ ...metadata, refseq_mane_plus_clinical: [], ensembl_mane_plus_clinical: [] }, "NM_000003.1", "RS MANE"],
  [{ refseq_mane_select: "  ", ensembl_mane_select: "ENST000003.1", refseq_accession: ["NM_000004.1"] }, "ENST000003.1", "ENS MANE"],
  [{ refseq_accession: ["NR_000001.1", "NM_000004.1"] }, "NM_000004.1", "PC"],
  [{ addtional_transcript_info: { "XM_000005.1": {}, "NR_000001.1": {} } }, "XM_000005.1", "PC"],
] satisfies [GeneTranscriptMetadata, string, string][])("selects one transcript in the declared priority: %s", (gene, id, badge) => {
  expect(catalogGeneTranscript(gene)).toMatchObject({ id, badge })
})

it("does not infer a coding transcript from a gene identifier or a noncoding accession", () => {
  expect(catalogGeneTranscript({ refseq_accession: ["NR_000001.1", "XR_000002.1"],
    addtional_transcript_info: { ENSG000001: {}, ENST000001: {} } })).toBeUndefined()
  expect(catalogGeneTranscript({})).toBeUndefined()
})

it("uses a deterministic accession within a priority without changing reference arrays", () => {
  const reversed = { ...metadata, refseq_mane_plus_clinical: [...metadata.refseq_mane_plus_clinical!].reverse() }
  expect(catalogGeneTranscript(reversed)).toEqual(catalogGeneTranscript(metadata))
  expect(metadata.refseq_mane_plus_clinical).toEqual(["NM_000002.1", "NM_000001.2"])
})
