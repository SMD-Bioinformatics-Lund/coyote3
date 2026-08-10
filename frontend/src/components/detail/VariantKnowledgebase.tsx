/* eslint-disable react/only-export-components -- this module intentionally colocates knowledgebase renderers with their pure presentation helpers. */

import type { ReactNode } from "react"
import { ExpandableText } from "@/components/detail/ExpandableText"
import { displayValue, isPresent } from "@/lib/detail-formatters"
import {
  cbioportalOncoprintUrl,
  clinvarSearchUrl,
  cosmicSearchUrl,
  dbsnpUrl,
  igvLoadUrl,
  litvarSearchUrl,
  oncokbGeneUrl,
  pubmedArticleUrl,
} from "@/lib/external-links"

export function compactObjectSummary(value: any) {
  if (!value) return "-"
  if (typeof value === "string") return value
  if (Array.isArray(value)) return `${value.length} record(s)`
  if (typeof value === "object") {
    const preferred = ["highest_level", "oncogenic", "mutationEffect", "clinicalSignificance", "drug", "disease", "summary", "description", "name"]
    for (const key of preferred) {
      if (isPresent(value[key])) return displayValue(value[key])
    }
    return `${Object.keys(value).length} field(s)`
  }
  return displayValue(value)
}

export function oncokbApiSummary(payload: any) {
  const response = payload?.response || {}
  const query = payload?.query || response?.query || {}
  const mutationEffect = response?.mutationEffect || {}
  return [
    { label: "Status", value: payload?.status || "-" },
    { label: "HGVSg", value: query?.hgvsg || query?.hgvs || "-", monospace: true },
    { label: "Gene", value: response?.query?.hugoSymbol || query?.gene?.hugoSymbol || query?.hugoSymbol || "-" },
    { label: "Alteration", value: response?.query?.alteration || query?.alteration || "-" },
    { label: "Data version", value: response?.dataVersion || "-" },
    { label: "Gene exists", value: response?.geneExist == null ? "-" : String(Boolean(response.geneExist)) },
    { label: "Variant exists", value: response?.variantExist == null ? (response?.alleleExist == null ? "-" : String(Boolean(response.alleleExist))) : String(Boolean(response.variantExist)) },
    { label: "Oncogenic", value: response?.oncogenic || "-" },
    { label: "Mutation effect", value: mutationEffect?.knownEffect || mutationEffect?.description || "-" },
    { label: "Diagnostic level", value: response?.highestDiagnosticImplicationLevel || "-" },
    { label: "Prognostic level", value: response?.highestPrognosticImplicationLevel || "-" },
    { label: "Gene summary", value: response?.geneSummary || "-" },
    { label: "Variant summary", value: response?.variantSummary || "-" },
  ]
}

export function oncokbPublicGeneMetrics(record: any) {
  if (!record) return []
  const cancerGene = record.public_cancer_gene || record
  const geneSummary = record.public_gene_summary || record
  return [
    { label: "Public cancer gene", value: record.public_cancer_gene || record.oncokb_annotated != null ? "Yes" : "-" },
    { label: "Gene type", value: cancerGene.gene_type || geneSummary.gene_type },
    { label: "Entrez", value: cancerGene.entrez_gene_id || geneSummary.entrez_gene_id, monospace: true },
    { label: "Setting", value: geneSummary.setting },
    { label: "Sensitive level", value: geneSummary.highest_sensitive_level || "-" },
    { label: "Resistance level", value: geneSummary.highest_resistance_level || "-" },
    { label: "GRCh38 RefSeq", value: geneSummary.grch38_refseq || cancerGene.grch38_refseq, monospace: true },
  ]
}

export function oncokbActionRows(value: any) {
  if (!value) return []
  return Array.isArray(value) ? value : [value]
}

export function clinpgxGeneMetrics(record: any) {
  if (!record) return []
  return [
    { label: "ClinPGx ID", value: record.pharmgkb_accession_id, monospace: true },
    { label: "HGNC", value: record.hgnc_id, monospace: true },
    { label: "VIP", value: record.is_vip == null ? "-" : String(Boolean(record.is_vip)) },
    { label: "Variant annotation", value: record.has_variant_annotation == null ? "-" : String(Boolean(record.has_variant_annotation)) },
    { label: "CPIC dosing guideline", value: record.has_cpic_dosing_guideline == null ? "-" : String(Boolean(record.has_cpic_dosing_guideline)) },
  ]
}

export function clinpgxApiSummary(payload: any) {
  const response = payload?.response || {}
  const gene = response?.gene || response || {}
  const counts = response?.counts || {}
  const flags = response?.flags || {}
  return [
    { label: "Status", value: payload?.status || "-" },
    { label: "ClinPGx ID", value: response?.clinpgx_id || gene?.id || payload?.query?.clinpgx_id || "-", monospace: true },
    { label: "Symbol", value: response?.symbol || gene?.symbol || payload?.query?.symbol || "-" },
    { label: "Name", value: response?.name || gene?.name || payload?.local_record?.name || "-" },
    { label: "VIP tier", value: flags?.vip_tier || response?.vip?.tier || "-" },
    { label: "CPIC gene", value: flags?.cpic_gene == null ? "-" : String(Boolean(flags.cpic_gene)) },
    { label: "Guidelines", value: counts?.guideline_annotations },
    { label: "Labels", value: counts?.label_annotations },
    { label: "Variant annotations", value: counts?.variant_annotations },
    { label: "Connected drugs", value: counts?.connected_chemicals },
    { label: "Pathways", value: counts?.pathways },
  ]
}

export function VariantKnowledgeBlock({ title, badges, defaultOpen = false, children }: { title: string; badges?: ReactNode; defaultOpen?: boolean; children: ReactNode }) {
  return (
    <details open={defaultOpen} className="group rounded-lg border border-border bg-background/70">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2">
        <span className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="text-xs font-black uppercase tracking-wide text-muted-foreground">{title}</span>
          {badges}
        </span>
        <span className="rounded-md bg-muted px-2 py-0.5 text-[10px] font-bold uppercase text-muted-foreground group-open:hidden">Expand</span>
        <span className="hidden rounded-md bg-muted px-2 py-0.5 text-[10px] font-bold uppercase text-muted-foreground group-open:inline">Collapse</span>
      </summary>
      <div className="border-t border-border px-3 py-3">{children}</div>
    </details>
  )
}

export function clinpgxEvidenceRows(payload: any, key: string) {
  const response = payload?.response || {}
  return Array.isArray(response?.[key]) ? response[key] : []
}

export function clinpgxEvidenceColumns(kind: "annotation" | "object") {
  if (kind === "object") {
    return [
      { key: "name", header: "Name", render: (row: any) => <span className="font-semibold">{row.name || "-"}</span> },
      { key: "type", header: "Type", render: (row: any) => row.type || "-" },
      { key: "connections", header: "Connections", render: (row: any) => Array.isArray(row.connection_types) && row.connection_types.length ? row.connection_types.join(", ") : "-" },
    ]
  }
  return [
    { key: "name", header: "Annotation", render: (row: any) => <span className="font-semibold">{row.name || row.id || "-"}</span> },
    { key: "type", header: "Type", render: (row: any) => row.type || "-" },
    {
      key: "summary",
      header: "Summary",
      render: (row: any) => <ExpandableText text={row.sentence || row.description || row.significance || "-"} maxLength={96} className="max-w-xl text-xs leading-5 text-muted-foreground" />,
    },
  ]
}

export function externalVariantLinks(variant: any, csq: any, data: any) {
  const gene = csq?.SYMBOL
  const hgvsp = csq?.HGVSp
  const dbsnp = variant?.dbsnp_id
  const cosmic = Array.isArray(variant?.cosmic_ids) ? variant.cosmic_ids[0] : undefined
  const pubmed = Array.isArray(variant?.pubmed_ids) ? variant.pubmed_ids[0] : undefined
  const clinvar = variant?.INFO?.CLNACC
  const position = variant?.CHROM && variant?.POS ? `${variant.CHROM}:${variant.POS}` : ""
  const igvUrl = data?.bam_id && position ? igvLoadUrl(data.bam_id, position) : null

  return [
    igvUrl ? { label: "Open region in IGV", value: position, href: igvUrl } : null,
    dbsnp ? { label: `dbSNP ${dbsnp}`, value: dbsnp, href: dbsnpUrl(dbsnp) } : null,
    cosmic ? { label: `COSMIC ${cosmic}`, value: cosmic, href: cosmicSearchUrl(cosmic) } : null,
    clinvar ? { label: `ClinVar ${clinvar}`, value: clinvar, href: clinvarSearchUrl(clinvar) } : null,
    gene ? { label: `cBioPortal ${gene}`, value: gene, href: cbioportalOncoprintUrl(gene) } : null,
    gene ? { label: `OncoKB ${gene}`, value: gene, href: oncokbGeneUrl(gene) } : null,
    gene && hgvsp ? { label: "LitVar", value: `${gene} ${hgvsp}`, href: litvarSearchUrl(`${gene} ${hgvsp}`) } : null,
    pubmed ? { label: `PubMed ${pubmed}`, value: pubmed, href: pubmedArticleUrl(pubmed) } : null,
  ].filter(Boolean) as any[]
}
