import { runtimeConfig } from "@/lib/runtime-config"

export const EXTERNAL_LINK_BASES = {
  dbsnp: "https://www.ncbi.nlm.nih.gov/snp",
  ncbiGene: "https://www.ncbi.nlm.nih.gov/gene",
  cosmicSearch: "https://cancer.sanger.ac.uk/cosmic/search",
  clinvarSearch: "https://www.ncbi.nlm.nih.gov/clinvar/",
  cbioportalOncoprint: "https://www.cbioportal.org/results/oncoprint",
  oncokbGene: "https://www.oncokb.org/gene",
  litvarDocsum: "https://www.ncbi.nlm.nih.gov/research/litvar2/docsum",
  pubmed: "https://pubmed.ncbi.nlm.nih.gov",
  clinpgxGeneApi: "https://api.clinpgx.org/v1/data/gene",
  mitelmanSearch: "https://mitelmandatabase.isb-cgc.org/mb_search",
  hgncReport: "https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id",
  ensemblGeneSummary: "https://www.ensembl.org/Homo_sapiens/Gene/Summary",
  geneCards: "https://www.genecards.org/cgi-bin/carddisp.pl",
  clinGenGene: "https://search.clinicalgenome.org/kb/genes",
} as const

export function igvLoadUrl(file: unknown, locus: unknown) {
  if (!runtimeConfig.igvUri || !file || !locus) return null
  return `${runtimeConfig.igvUri}/load?file=${encodeURIComponent(String(file))}&locus=${encodeURIComponent(String(locus))}`
}

export function gensSampleUrl(sampleName: unknown) {
  if (!runtimeConfig.gensUri || !sampleName) return null
  return `${runtimeConfig.gensUri}/${encodeURIComponent(String(sampleName))}`
}

export function omimEntryUrl(id: unknown) {
  return `https://www.omim.org/entry/${encodeURIComponent(String(id))}`
}

export function dbsnpUrl(id: unknown) {
  return `${EXTERNAL_LINK_BASES.dbsnp}/${encodeURIComponent(String(id))}`
}

export function ncbiGeneUrl(id: unknown) {
  return `${EXTERNAL_LINK_BASES.ncbiGene}/${encodeURIComponent(String(id))}`
}

export function cosmicSearchUrl(query: unknown) {
  return `${EXTERNAL_LINK_BASES.cosmicSearch}?q=${encodeURIComponent(String(query))}`
}

export function clinvarSearchUrl(term: unknown) {
  return `${EXTERNAL_LINK_BASES.clinvarSearch}?term=${encodeURIComponent(String(term))}`
}

export function cbioportalOncoprintUrl(genes: unknown[] | unknown) {
  const geneList = Array.isArray(genes) ? genes.filter(Boolean).join(" ") : String(genes || "")
  return `${EXTERNAL_LINK_BASES.cbioportalOncoprint}?gene_list=${encodeURIComponent(geneList)}`
}

export function oncokbGeneUrl(gene: unknown) {
  return `${EXTERNAL_LINK_BASES.oncokbGene}/${encodeURIComponent(String(gene || ""))}`
}

export function litvarSearchUrl(query: unknown) {
  return `${EXTERNAL_LINK_BASES.litvarDocsum}?query=${encodeURIComponent(String(query))}`
}

export function pubmedArticleUrl(id: unknown) {
  return `${EXTERNAL_LINK_BASES.pubmed}/${encodeURIComponent(String(id))}/`
}

export function pubmedSearchUrl(term: unknown) {
  return `${EXTERNAL_LINK_BASES.pubmed}/?term=${encodeURIComponent(String(term))}`
}

export function clinpgxGeneUrl(gene: unknown, pharmgkbAccessionId?: unknown) {
  if (pharmgkbAccessionId) {
    return `${EXTERNAL_LINK_BASES.clinpgxGeneApi}/${encodeURIComponent(String(pharmgkbAccessionId))}`
  }
  return `${EXTERNAL_LINK_BASES.clinpgxGeneApi}?symbol=${encodeURIComponent(String(gene || ""))}&view=max`
}

export function hgncReportUrl(hgncId: unknown) {
  return `${EXTERNAL_LINK_BASES.hgncReport}/${encodeURIComponent(String(hgncId || "").replace("HGNC:", ""))}`
}

export function ensemblGeneSummaryUrl(ensemblGeneId: unknown) {
  return `${EXTERNAL_LINK_BASES.ensemblGeneSummary}?g=${encodeURIComponent(String(ensemblGeneId))}`
}

export function geneCardsUrl(symbol: unknown) {
  return `${EXTERNAL_LINK_BASES.geneCards}?gene=${encodeURIComponent(String(symbol))}`
}

export function clinGenGeneUrl(symbol: unknown) {
  return `${EXTERNAL_LINK_BASES.clinGenGene}/${encodeURIComponent(String(symbol))}`
}
