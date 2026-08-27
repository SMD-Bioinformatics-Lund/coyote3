import { describe, expect, it } from "vitest"

import {
  cbioportalOncoprintUrl,
  clinGenGeneUrl,
  clinpgxGeneUrl,
  clinvarSearchUrl,
  cosmicSearchUrl,
  dbsnpUrl,
  ensemblGeneSummaryUrl,
  geneCardsUrl,
  gensSampleUrl,
  hgncReportUrl,
  igvLoadUrl,
  litvarSearchUrl,
  ncbiGeneUrl,
  oncokbGeneUrl,
  omimEntryUrl,
  pubmedArticleUrl,
  pubmedSearchUrl,
} from "./external-links"

describe("external knowledgebase links", () => {
  it("encodes identifiers and search terms", () => {
    expect(dbsnpUrl("rs 1").endsWith("/rs%201")).toBe(true)
    expect(ncbiGeneUrl(7157).endsWith("/7157")).toBe(true)
    expect(omimEntryUrl("191170").endsWith("/191170")).toBe(true)
    expect(cosmicSearchUrl("TP53 p.R175H")).toContain("q=TP53%20p.R175H")
    expect(clinvarSearchUrl("NM_000546.6:c.524G>A")).toContain("term=NM_000546.6%3Ac.524G%3EA")
    expect(litvarSearchUrl("TP53 R175H")).toContain("query=TP53%20R175H")
    expect(pubmedArticleUrl(123).endsWith("/123/")).toBe(true)
    expect(pubmedSearchUrl("somatic mutation")).toContain("term=somatic%20mutation")
  })

  it("builds gene-oriented links from arrays and canonical identifiers", () => {
    expect(cbioportalOncoprintUrl(["TP53", "", "KRAS"])).toContain("gene_list=TP53%20KRAS")
    expect(oncokbGeneUrl("HLA B").endsWith("/HLA%20B")).toBe(true)
    expect(clinpgxGeneUrl("CYP2D6", "PA 128").endsWith("/PA%20128")).toBe(true)
    expect(clinpgxGeneUrl("CYP2D6")).toContain("symbol=CYP2D6&view=max")
    expect(hgncReportUrl("HGNC:11998").endsWith("/11998")).toBe(true)
    expect(ensemblGeneSummaryUrl("ENSG 1")).toContain("g=ENSG%201")
    expect(geneCardsUrl("TP53")).toContain("gene=TP53")
    expect(clinGenGeneUrl("TP53").endsWith("/TP53")).toBe(true)
  })

  it("disables deployment-local integrations when no URI is configured", () => {
    expect(igvLoadUrl("bam-id", "17:1-2")).toBeNull()
    expect(gensSampleUrl("sample-1")).toBeNull()
  })
})
