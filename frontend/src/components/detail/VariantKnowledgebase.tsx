/* eslint-disable react/only-export-components -- this module intentionally colocates knowledgebase renderers with their pure presentation helpers. */

import type { ReactNode } from "react"
import { Database, ExternalLink } from "lucide-react"
import {
  DetailDataTable,
  EvidenceBadge,
} from "@/components/detail/DetailEvidenceCards"
import { DetailCard } from "@/components/detail/FindingDetailLayout"
import { ExpandableText } from "@/components/detail/ExpandableText"
import { isPresent } from "@/lib/detail-formatters"
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
import { appPath } from "@/lib/runtime-paths"

export type KnowledgebaseSource =
  | "brca-exchange"
  | "civic"
  | "clinpgx"
  | "cosmic"
  | "hpa"
  | "iarc-tp53"
  | "oncokb"

const knowledgebasePresentation: Record<
  KnowledgebaseSource,
  { logo?: string; logoAlt: string; logoWidth: string }
> = {
  "brca-exchange": {
    logo: "/BRCA-Exchange.png",
    logoAlt: "BRCA Exchange logo",
    logoWidth: "w-7",
  },
  civic: { logo: "/civic.png", logoAlt: "CIViC logo", logoWidth: "w-16" },
  clinpgx: { logo: "/clinPGxpng.png", logoAlt: "ClinPGx logo", logoWidth: "w-16" },
  cosmic: { logo: "/COSMIC.png", logoAlt: "COSMIC logo", logoWidth: "w-16" },
  hpa: { logoAlt: "Human Protein Atlas", logoWidth: "w-7" },
  "iarc-tp53": { logoAlt: "IARC TP53", logoWidth: "w-7" },
  oncokb: { logo: "/OncoKB.png", logoAlt: "OncoKB logo", logoWidth: "w-16" },
}

export function objectMetrics(
  value: any,
  fields: Array<{ label: string; keys: string[] }>,
) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return []
  return fields.map(({ label, keys }) => ({
    label,
    value: keys.map((key) => value[key]).find(isPresent) ?? "-",
  }))
}

export function hpaExpressionRows(expression: any) {
  if (!expression || typeof expression !== "object" || Array.isArray(expression)) return []

  return Object.entries(expression)
    .filter(([, values]) => values && typeof values === "object" && !Array.isArray(values))
    .map(([transcript, values]) => {
      const tissues = Object.entries(values as Record<string, unknown>)
        .filter(([, value]) => typeof value === "number" && Number.isFinite(value))
        .sort(([, left], [, right]) => Number(right) - Number(left))
      const [topTissue, topValue] = tissues[0] || []
      return {
        transcript,
        tissues: tissues.length,
        top_tissue: topTissue || "-",
        top_expression: typeof topValue === "number" ? topValue : "-",
      }
    })
}

export function oncokbApiSummary(payload: any, response: any) {
  const query = payload?.query || {}
  const mutationEffect = response?.mutationEffect || {}
  return [
    { label: "Reference genome", value: query?.referenceGenome || "-" },
    { label: "Genomic location", value: query?.genomicLocation || "-", monospace: true },
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

export function VariantKnowledgeBlock({
  source,
  title,
  badges,
  defaultOpen = false,
  children,
}: {
  source: KnowledgebaseSource
  title: string
  badges?: ReactNode
  defaultOpen?: boolean
  children: ReactNode
}) {
  const presentation = knowledgebasePresentation[source]

  return (
    <details
      open={defaultOpen}
      data-knowledgebase={source}
      className="knowledgebase-block group rounded-lg border"
    >
      <summary className="knowledgebase-block-header flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2">
        <span className="flex min-w-0 flex-wrap items-center gap-2">
          <span className={`knowledgebase-logo-frame flex h-8 ${presentation.logoWidth} shrink-0 items-center justify-center rounded-md`}>
            {presentation.logo ? (
              <img
                src={appPath(presentation.logo)}
                alt={presentation.logoAlt}
                className="max-h-7 max-w-full object-contain"
              />
            ) : (
              <Database className="size-4" aria-label={presentation.logoAlt} />
            )}
          </span>
          <span className="type-card-title text-foreground">{title}</span>
          {badges}
        </span>
        <span className="rounded-md bg-muted px-2 py-0.5 type-label font-semibold uppercase text-muted-foreground group-open:hidden">Expand</span>
        <span className="hidden rounded-md bg-muted px-2 py-0.5 type-label font-semibold uppercase text-muted-foreground group-open:inline">Collapse</span>
      </summary>
      <div className="border-t border-border px-3 py-3">{children}</div>
    </details>
  )
}

function cosmicRecordId(row: any) {
  return row?.id || row?.cosmic_fusion_id || row?.cosmic_structural_id
    || (Array.isArray(row?.cosmic_ids) ? row.cosmic_ids[0] : undefined)
}

function cosmicFinding(row: any) {
  if (row?.gene || row?.gene_symbol) {
    return [row.gene || row.gene_symbol, row.hgvsp || row.hgvsc || row.type]
      .filter(Boolean)
      .join(" · ")
  }
  if (row?.five_prime_gene_symbol || row?.three_prime_gene_symbol) {
    return [row.five_prime_gene_symbol, row.three_prime_gene_symbol].filter(Boolean).join("::")
  }
  if (row?.chrom_from || row?.chrom_to) {
    return `${row.chrom_from || "?"}:${row.location_from_min || "?"} · ${row.chrom_to || "?"}:${row.location_to_min || "?"}`
  }
  return row?.hgvsg || row?.type || "-"
}

export function CosmicKnowledgeBlock({ evidence }: { evidence: any }) {
  const records = Array.isArray(evidence?.records) ? evidence.records : []
  const hallmarks = Array.isArray(evidence?.hallmarks) ? evidence.hallmarks : []
  const actionability = Array.isArray(evidence?.actionability) ? evidence.actionability : []

  return (
    <VariantKnowledgeBlock
      source="cosmic"
      title="COSMIC"
      defaultOpen
      badges={evidence?.match_count ? <EvidenceBadge tone="info">{evidence.match_count} observations</EvidenceBadge> : null}
    >
      <div className="space-y-3">
        <DetailDataTable
          rows={records}
          empty="No matching COSMIC records are available for this finding."
          columns={[
            {
              key: "id",
              header: "COSMIC record",
              render: (row: any) => {
                const identifier = cosmicRecordId(row)
                return identifier ? (
                  <a className="link-text" href={cosmicSearchUrl(String(identifier))} target="_blank" rel="noreferrer">
                    {identifier}
                  </a>
                ) : "-"
              },
            },
            { key: "finding", header: "Finding", render: cosmicFinding },
            {
              key: "evidence",
              header: "Evidence",
              render: (row: any) => row.observations
                ? `${Number(row.observations).toLocaleString()} observations`
                : row.primary_histology || row.so_term || row.mutation_type || row.tier || "-",
            },
          ]}
        />

        {hallmarks.length ? (
          <div>
            <h5 className="mb-1 type-section-title">Cancer Gene Census hallmarks</h5>
            <DetailDataTable
              rows={hallmarks}
              columns={[
                { key: "gene", header: "Gene", render: (row: any) => row.gene_symbol || "-" },
                { key: "hallmark", header: "Hallmark", render: (row: any) => row.hallmark || row.impact || "-" },
                { key: "description", header: "Description", render: (row: any) => <ExpandableText text={row.description || "-"} maxLength={120} /> },
              ]}
            />
          </div>
        ) : null}

        {actionability.length ? (
          <div>
            <h5 className="mb-1 type-section-title">Actionability</h5>
            <DetailDataTable
              rows={actionability}
              columns={[
                { key: "disease", header: "Disease", render: (row: any) => row.disease || "-" },
                { key: "drug", header: "Drug", render: (row: any) => row.drug_name || row.drug || "-" },
                { key: "evidence", header: "Evidence", render: (row: any) => row.evidence_type || row.rank || "-" },
              ]}
            />
          </div>
        ) : null}
      </div>
    </VariantKnowledgeBlock>
  )
}

function identifierValues(value: unknown): string[] {
  const values = Array.isArray(value) ? value : value ? [value] : []
  return listUnique(values.map(String).map((item) => item.trim()).filter(Boolean))
}

function listUnique(values: string[]) {
  return [...new Set(values)]
}

function IdentifierRow({
  label,
  values,
  href,
}: {
  label: string
  values: string[]
  href: (value: string) => string
}) {
  return (
    <div className="border-b border-border/60 px-3 py-2 last:border-b-0">
      <div className="detail-field-label mb-1">{label}</div>
      {values.length ? (
        <div className="flex flex-wrap gap-1.5">
          {values.map((value) => (
            <a
              key={value}
              className="inline-flex min-w-0 items-center gap-1 rounded-md border border-border bg-background px-2 py-1 type-badge text-primary hover:bg-primary/10"
              href={href(value)}
              target="_blank"
              rel="noreferrer"
            >
              <span className="break-all">{value}</span>
              <ExternalLink className="size-3 shrink-0" />
            </a>
          ))}
        </div>
      ) : (
        <span className="type-body-sm text-muted-foreground">Not available</span>
      )}
    </div>
  )
}

export function VariantIdentifiersCard({ variant }: { variant: any }) {
  const cosmicIds = identifierValues(variant?.cosmic_ids)
  const dbsnpIds = identifierValues(variant?.dbsnp_ids ?? variant?.dbsnp_id)
  const pubmedIds = identifierValues(variant?.pubmed_ids)

  return (
    <DetailCard title="Variant Identifiers" tone="info">
      <div className="overflow-hidden rounded-lg border border-border/70 bg-background/45">
        <IdentifierRow label="COSMIC" values={cosmicIds} href={cosmicSearchUrl} />
        <IdentifierRow label="dbSNP" values={dbsnpIds} href={dbsnpUrl} />
        <IdentifierRow label="PubMed" values={pubmedIds} href={pubmedArticleUrl} />
      </div>
    </DetailCard>
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
  const clinvar = variant?.INFO?.CLNACC
  const position = variant?.CHROM && variant?.POS ? `${variant.CHROM}:${variant.POS}` : ""
  const igvUrl = data?.bam_id && position ? igvLoadUrl(data.bam_id, position) : null

  return [
    igvUrl ? { label: "Open region in IGV", value: position, href: igvUrl } : null,
    clinvar ? { label: `ClinVar ${clinvar}`, value: clinvar, href: clinvarSearchUrl(clinvar) } : null,
    gene ? { label: `cBioPortal ${gene}`, value: gene, href: cbioportalOncoprintUrl(gene) } : null,
    gene ? { label: `OncoKB ${gene}`, value: gene, href: oncokbGeneUrl(gene) } : null,
    gene && hgvsp ? { label: "LitVar", value: `${gene} ${hgvsp}`, href: litvarSearchUrl(`${gene} ${hgvsp}`) } : null,
  ].filter(Boolean) as any[]
}
