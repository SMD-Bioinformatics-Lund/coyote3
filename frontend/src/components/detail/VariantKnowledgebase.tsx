/* eslint-disable react/only-export-components -- this module intentionally colocates knowledgebase renderers with their pure presentation helpers. */

import { Children, createContext, type ReactNode, useContext, useState } from "react"
import { AlertTriangle, Database, ExternalLink, Search, Target } from "lucide-react"
import {
  DetailDataTable,
  EvidenceBadge,
} from "@/components/detail/DetailEvidenceCards"
import { ExpandableText } from "@/components/detail/ExpandableText"
import { Input } from "@/components/ui/input"
import { AnalysisIntentBadges, CopyNumberBadge, TierBadge } from "@/lib/variant-ui"
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
import { databaseLogo } from "@/lib/database-logos"

export type KnowledgebaseSource =
  | "brca-exchange"
  | "civic"
  | "clinpgx"
  | "cosmic"
  | "hpa"
  | "iarc-tp53"
  | "oncokb"

const knowledgebasePresentation: Record<KnowledgebaseSource, { fallbackLabel: string }> = {
  "brca-exchange": { fallbackLabel: "BRCA Exchange" },
  civic: { fallbackLabel: "CIViC" },
  clinpgx: { fallbackLabel: "ClinPGx" },
  cosmic: { fallbackLabel: "COSMIC" },
  hpa: { fallbackLabel: "Human Protein Atlas" },
  "iarc-tp53": { fallbackLabel: "IARC TP53" },
  oncokb: { fallbackLabel: "OncoKB" },
}

const KnowledgebaseSearchContext = createContext("")

function matchesKnowledgebaseSearch(value: unknown, search: string) {
  const query = search.trim().toLocaleLowerCase()
  return !query || JSON.stringify(value ?? "").toLocaleLowerCase().includes(query)
}

export function KnowledgebaseExplorer({ children }: { children: ReactNode }) {
  const [search, setSearch] = useState("")
  return (
    <KnowledgebaseSearchContext.Provider value={search}>
      <div className="space-y-3">
        <label className="relative block w-full sm:max-w-lg">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search all knowledgebase evidence"
            aria-label="Search all knowledgebase evidence"
            className="pl-8"
          />
        </label>
        {children}
      </div>
    </KnowledgebaseSearchContext.Provider>
  )
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
  searchData,
  defaultOpen = false,
  children,
}: {
  source: KnowledgebaseSource
  title: string
  badges?: ReactNode
  searchData?: unknown
  defaultOpen?: boolean
  children: ReactNode
}) {
  const presentation = knowledgebasePresentation[source]
  const logo = databaseLogo(source)
  const search = useContext(KnowledgebaseSearchContext)

  if (!matchesKnowledgebaseSearch({ source, title, data: searchData }, search)) return null

  return (
    <details
      open={defaultOpen}
      data-knowledgebase={source}
      className="knowledgebase-block group rounded-lg border"
    >
      <summary className="knowledgebase-block-header flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2">
        <span className="flex min-w-0 flex-wrap items-center gap-2">
          <span className={`knowledgebase-logo-frame flex h-9 ${logo ? "w-20" : "w-7"} shrink-0 items-center justify-center`}>
            {logo ? (
              <img
                src={appPath(logo.src)}
                alt={logo.alt}
                className="max-h-8 max-w-full object-contain"
              />
            ) : (
              <Database className="size-4" aria-label={presentation.fallbackLabel} />
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

export function KnowledgebaseGrid({ children }: { children: ReactNode }) {
  return (
    <div className="columns-1 gap-3 xl:columns-2">
      {Children.toArray(children).map((child, index) => (
        <div key={index} className="mb-3 inline-block w-full break-inside-avoid align-top last:mb-0">
          {child}
        </div>
      ))}
    </div>
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

const cosmicMatchPresentation: Record<string, { label: string; description: string }> = {
  small_variant: {
    label: "Exact variant",
    description: "Matched to the reported genomic allele or its stored COSMIC identifier.",
  },
  copy_number: {
    label: "Interval and gene",
    description: "Matched COSMIC copy-number records overlap the reported interval and affected genes.",
  },
  fusion: {
    label: "Gene pair",
    description: "Matched COSMIC fusion records contain the reported gene pair in either orientation.",
  },
  translocation: {
    label: "Breakpoint overlap",
    description: "Matched COSMIC structural records overlap one or both reported breakpoints.",
  },
}

function filterKnowledgebaseRows(rows: any[], search: string) {
  const query = search.trim().toLocaleLowerCase()
  if (!query) return rows
  return rows.filter((row) => JSON.stringify(row).toLocaleLowerCase().includes(query))
}

function evidenceValues(value: unknown) {
  const rawValues = Array.isArray(value) ? value : value == null ? [] : [value]
  return rawValues
    .flatMap((item) => String(item).split(/\s*[,;|]\s*/))
    .map((item) => item.trim())
    .filter((item) => item && item !== "-")
}

function EvidenceValues({
  value,
  tone = "neutral",
}: {
  value: unknown
  tone?: "neutral" | "success" | "warning" | "danger" | "info"
}) {
  const values = evidenceValues(value)
  if (!values.length) return <span className="text-muted-foreground">-</span>

  return (
    <div className="flex max-w-full flex-wrap gap-1">
      {values.map((item) => <EvidenceBadge key={item} tone={tone}>{item}</EvidenceBadge>)}
    </div>
  )
}

export function CosmicKnowledgeBlock({ evidence }: { evidence: any }) {
  const search = useContext(KnowledgebaseSearchContext)
  const normalizedSearch = search.trim().toLocaleLowerCase()
  const sourceNameMatches = Boolean(normalizedSearch) && "cosmic".includes(normalizedSearch)
  const rowSearch = sourceNameMatches ? "" : search
  const records = Array.isArray(evidence?.records) ? evidence.records : []
  const geneCensus = Array.isArray(evidence?.gene_census) ? evidence.gene_census : []
  const classifications = Array.isArray(evidence?.classifications) ? evidence.classifications : []
  const hallmarks = Array.isArray(evidence?.hallmarks) ? evidence.hallmarks : []
  const resistance = Array.isArray(evidence?.resistance) ? evidence.resistance : []
  const actionability = Array.isArray(evidence?.actionability) ? evidence.actionability : []
  const structuralVariants = Array.isArray(evidence?.structural_variants) ? evidence.structural_variants : []
  const visibleRecords = filterKnowledgebaseRows(records, rowSearch)
  const visibleClassifications = filterKnowledgebaseRows(classifications, rowSearch)
  const visibleGeneCensus = filterKnowledgebaseRows(geneCensus, rowSearch)
  const visibleHallmarks = filterKnowledgebaseRows(hallmarks, rowSearch)
  const visibleActionability = filterKnowledgebaseRows(actionability, rowSearch)
  const visibleResistance = filterKnowledgebaseRows(resistance, rowSearch)
  const visibleStructuralVariants = filterKnowledgebaseRows(structuralVariants, rowSearch)
  const visibleResultCount = [
    visibleRecords,
    visibleClassifications,
    visibleGeneCensus,
    visibleHallmarks,
    visibleActionability,
    visibleResistance,
    visibleStructuralVariants,
  ].reduce((total, rows) => total + rows.length, 0)
  const matchPresentation = cosmicMatchPresentation[evidence?.kind] || {
    label: "Relevant evidence",
    description: "Matched COSMIC evidence for this finding.",
  }
  const unavailable = Object.entries(evidence?.availability || {})
    .filter(([, available]) => available === false)
    .map(([product]) => ({
      product,
      label: ({
        actionability: "Actionability",
        breakpoints: "Breakpoints",
        cancer_gene_census: "Cancer Gene Census",
        classifications: "Tumour Classifications",
        census_gene_mutations: "Census Genes Mutations",
        copy_number: "Copy Number Analysis",
        fusions: "Fusions",
        cgc_hallmarks: "Hallmarks of Cancer",
        mutation_census: "Cancer Mutation Census",
        resistance_mutations: "Resistance Mutations",
        structural_variants: "Structural Variants",
        targeted_variants: "Targeted Screens Mutants",
      } as Record<string, string>)[product] || product,
    }))

  if (normalizedSearch && !sourceNameMatches && visibleResultCount === 0) return null

  return (
    <VariantKnowledgeBlock
      source="cosmic"
      title="COSMIC"
      defaultOpen
      searchData={evidence}
      badges={evidence?.match_count ? <EvidenceBadge tone="info">{evidence.match_count} observations</EvidenceBadge> : null}
    >
      <div className="space-y-3">
        {rowSearch ? (
          <span className="type-meta text-muted-foreground">
            {visibleResultCount} matching {visibleResultCount === 1 ? "row" : "rows"}
          </span>
        ) : null}
        {records.length ? (
          <div className="flex items-start gap-2 rounded-md border border-pass/35 bg-pass/10 px-3 py-2">
            <Target className="mt-0.5 size-4 shrink-0 text-pass" aria-hidden="true" />
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="type-body-sm font-semibold text-foreground">Relevant match</span>
                <EvidenceBadge tone="success">{matchPresentation.label}</EvidenceBadge>
              </div>
              <p className="mt-0.5 type-meta text-muted-foreground">{matchPresentation.description}</p>
            </div>
          </div>
        ) : null}
        {unavailable.length ? (
          <div className="flex items-start gap-2 rounded-md border border-warning/40 bg-warning/10 px-3 py-2 type-body-sm text-foreground">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true" />
            <span>
              Not configured: {unavailable.map(({ label }) => label).join(", ")}.
            </span>
          </div>
        ) : null}
        <KnowledgebaseGrid>
          <div className="min-w-0">
            <h5 className="mb-1 type-section-title">Matched records</h5>
            <DetailDataTable
              rows={visibleRecords}
              initialRows={10}
              empty={rowSearch ? "No COSMIC records match this search." : "No matching COSMIC records are available for this finding."}
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
            {
              key: "finding",
              header: "Finding",
              render: (row: any) => (
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="font-semibold text-foreground">{cosmicFinding(row)}</span>
                  {evidence?.kind === "copy_number" && row.type ? (
                    <CopyNumberBadge value={row.type} />
                  ) : null}
                </div>
              ),
            },
            {
              key: "source",
              header: "Product",
              render: (row: any) => <EvidenceBadge>{row.source_product || "COSMIC"}</EvidenceBadge>,
            },
            {
              key: "evidence",
              header: "Evidence",
              render: (row: any) => {
                if (row.observations) {
                  return (
                    <EvidenceBadge tone="success">
                      {Number(row.observations).toLocaleString()} observations
                    </EvidenceBadge>
                  )
                }
                if (row.cosmic_sample_mutated != null) {
                  const mutated = Number(row.cosmic_sample_mutated).toLocaleString()
                  const tested = row.cosmic_sample_tested == null
                    ? null
                    : Number(row.cosmic_sample_tested).toLocaleString()
                  const sampleCount = tested ? `${mutated} / ${tested} samples` : `${mutated} samples`
                  return (
                    <div className="flex flex-wrap items-center gap-1.5">
                      {row.mutation_significance_tier ? (
                        <EvidenceBadge tone="warning">{row.mutation_significance_tier}</EvidenceBadge>
                      ) : null}
                      <span className="font-medium text-foreground">{sampleCount}</span>
                    </div>
                  )
                }
                const summary = row.mutation_significance_tier
                  || row.mutation_somatic_status
                  || row.primary_histology
                  || row.so_term
                  || row.mutation_type
                  || row.tier
                  || "-"
                return <span className="font-medium text-foreground">{summary}</span>
              },
            },
              ]}
            />
          </div>

          {classifications.length ? (
          <div className="min-w-0">
            <h5 className="mb-1 type-section-title">Tumour classifications</h5>
            <DetailDataTable
              rows={visibleClassifications}
              initialRows={10}
              empty="No tumour classifications match this search."
              columns={[
                { key: "id", header: "COSMIC phenotype", render: (row: any) => row.cosmic_phenotype_id || "-" },
                { key: "site", header: "Primary site", render: (row: any) => row.primary_site || "-" },
                { key: "histology", header: "Histology", render: (row: any) => row.primary_histology || "-" },
                { key: "subtype", header: "Subtype", render: (row: any) => row.histology_subtype_1 || row.histology_subtype_2 || "-" },
              ]}
            />
          </div>
          ) : null}

          {geneCensus.length ? (
          <div className="min-w-0">
            <h5 className="mb-1 type-section-title">Cancer Gene Census</h5>
            <DetailDataTable
              rows={visibleGeneCensus}
              initialRows={10}
              empty="No Cancer Gene Census records match this search."
              columns={[
                { key: "gene", header: "Gene", render: (row: any) => row.gene_symbol || "-" },
                { key: "tier", header: "Tier", render: (row: any) => <TierBadge tier={row.tier} /> },
                { key: "role", header: "Role", render: (row: any) => row.role_in_cancer || "-" },
                { key: "origin", header: "Origin", render: (row: any) => <AnalysisIntentBadges somatic={row.somatic} germline={row.germline} /> },
                { key: "types", header: "Mutation types", render: (row: any) => row.mutation_types || "-" },
              ]}
            />
          </div>
          ) : null}

          {hallmarks.length ? (
          <div className="min-w-0">
            <h5 className="mb-1 type-section-title">Cancer Gene Census hallmarks</h5>
            <DetailDataTable
              rows={visibleHallmarks}
              initialRows={10}
              empty="No cancer hallmark records match this search."
              columns={[
                { key: "gene", header: "Gene", render: (row: any) => row.gene_symbol || "-" },
                { key: "hallmark", header: "Hallmark", render: (row: any) => row.hallmark || row.impact || "-" },
                { key: "description", header: "Description", render: (row: any) => <ExpandableText text={row.description || "-"} maxLength={120} /> },
              ]}
            />
          </div>
          ) : null}
        </KnowledgebaseGrid>

        {actionability.length ? (
          <div>
            <h5 className="mb-1 type-section-title">Actionability</h5>
            <DetailDataTable
              rows={visibleActionability}
              initialRows={10}
              empty="No actionability records match this search."
              columns={[
                {
                  key: "selection",
                  header: "Mutation selection",
                  render: (row: any) => (
                    <ExpandableText
                      text={row.mutation_remark || row.mutation_selectivity || "-"}
                      maxLength={72}
                      className="max-w-md text-foreground"
                    />
                  ),
                },
                { key: "disease", header: "Disease", render: (row: any) => <EvidenceValues value={row.disease} /> },
                { key: "drug", header: "Drug", render: (row: any) => <EvidenceValues value={row.drug_combination} /> },
                {
                  key: "evidence",
                  header: "Evidence",
                  render: (row: any) => (
                    <EvidenceValues
                      value={row.actionability_rank_description || row.development_status || row.actionability_rank}
                    />
                  ),
                },
              ]}
            />
          </div>
        ) : null}

        {resistance.length ? (
          <div>
            <h5 className="mb-1 type-section-title">Resistance Mutations</h5>
            <DetailDataTable
              rows={visibleResistance}
              initialRows={10}
              empty="No resistance records match this search."
              columns={[
                { key: "finding", header: "Finding", render: (row: any) => row.hgvsp || row.mutation_aa || row.hgvsc || row.mutation_cds || "-" },
                { key: "drug", header: "Drug", render: (row: any) => row.drug_name || "-" },
                { key: "response", header: "Response", render: (row: any) => row.drug_response || "-" },
              ]}
            />
          </div>
        ) : null}

        {structuralVariants.length ? (
          <div>
            <h5 className="mb-1 type-section-title">Structural variant context</h5>
            <DetailDataTable
              rows={visibleStructuralVariants}
              initialRows={10}
              empty="No structural variant records match this search."
              columns={[
                { key: "id", header: "COSMIC record", render: (row: any) => row.cosmic_structural_id || "-" },
                { key: "type", header: "Type", render: (row: any) => <EvidenceBadge tone="info">{row.mutation_type || "Structural"}</EvidenceBadge> },
                { key: "description", header: "Description", render: (row: any) => <ExpandableText text={row.description || "-"} maxLength={120} /> },
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

export function VariantIdentifierLinks({ variant }: { variant: any }) {
  const cosmicIds = identifierValues(variant?.cosmic_ids)
  const dbsnpIds = identifierValues(variant?.dbsnp_ids ?? variant?.dbsnp_id)
  const pubmedIds = identifierValues(variant?.pubmed_ids)

  return (
    <div>
      <h4 className="mb-1.5 type-label font-semibold uppercase text-muted-foreground">Stored identifiers</h4>
      <div className="overflow-hidden rounded-lg border border-border/70 bg-background/45">
        <IdentifierRow label="COSMIC" values={cosmicIds} href={cosmicSearchUrl} />
        <IdentifierRow label="dbSNP" values={dbsnpIds} href={dbsnpUrl} />
        <IdentifierRow label="PubMed" values={pubmedIds} href={pubmedArticleUrl} />
      </div>
    </div>
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
