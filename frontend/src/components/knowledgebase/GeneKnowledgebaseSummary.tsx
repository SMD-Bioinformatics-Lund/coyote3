import { Activity, Database, Dna, Sparkles } from "lucide-react"

import { TableBadge } from "@/components/ui/table-badge"
import { AnalysisIntentBadges, TierBadge } from "@/lib/variant-ui"

type CosmicGeneCensusRecord = {
  cosmic_gene_id?: string
  role_in_cancer?: string
  tier?: string | number
  somatic?: string | boolean | null
  germline?: string | boolean | null
  tumour_types_somatic?: string | string[] | null
  tumour_types_germline?: string | string[] | null
  mutation_types?: string | string[] | null
}

type CosmicGeneEvidence = {
  availability?: Record<string, boolean>
  gene_census?: CosmicGeneCensusRecord[]
  hallmarks?: Array<Record<string, unknown>>
}

export type GeneKnowledgebasePayload = {
  gene?: Record<string, unknown> | null
  available_sources?: string[]
  sources?: Record<string, unknown>
}

const sourceLabels: Record<string, string> = {
  brca_exchange: "BRCA Exchange",
  civic_gene: "CIViC",
  clinpgx_public: "ClinPGx",
  cosmic: "COSMIC",
  iarc_tp53: "IARC TP53",
  oncokb_actionable_local: "OncoKB Actionable",
  oncokb_local: "OncoKB",
  oncokb_public: "OncoKB Public",
}

const sourceFactFields: Record<string, Array<[string, string]>> = {
  civic_gene: [["Entrez", "entrez_id"], ["Reviewed", "last_review_date"]],
  clinpgx_public: [["ClinPGx", "pharmgkb_accession_id"], ["VIP", "is_vip"], ["Variant annotations", "has_variant_annotation"], ["CPIC dosing", "has_cpic_dosing_guideline"]],
  oncokb_actionable_local: [["Level", "Level"], ["Cancer type", "Cancer Type"], ["Alteration", "Alteration"]],
  oncokb_local: [["Entrez", "entrezGeneId"], ["Type", "type"]],
  oncokb_public: [["Type", "gene_type"], ["OncoKB annotated", "oncokb_annotated"], ["Data version", "data_version"], ["Occurrences", "occurrence_count"]],
}

function sourceFacts(source: string, value: unknown) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return []
  const record = value as Record<string, unknown>
  return (sourceFactFields[source] || [])
    .map(([label, key]) => ({ label, value: record[key] }))
    .filter(({ value }) => value !== undefined && value !== null && value !== "")
}

function displayFact(value: unknown) {
  if (typeof value === "boolean") return value ? "Yes" : "No"
  if (Array.isArray(value)) return value.map(String).join(", ")
  return String(value)
}

export function GeneKnowledgebaseSummary({ payload }: { payload?: GeneKnowledgebasePayload }) {
  const sources = payload?.sources || {}
  const cosmic = (
    sources.cosmic && typeof sources.cosmic === "object" ? sources.cosmic : {}
  ) as CosmicGeneEvidence
  const census = Array.isArray(cosmic.gene_census) ? cosmic.gene_census : []
  const hallmarks = Array.isArray(cosmic.hallmarks) ? cosmic.hallmarks : []
  const availableSources = (payload?.available_sources || []).filter((source: string) => {
    const sourceValue = sources[source]
    if (source === "brca_exchange" || source === "iarc_tp53") {
      return Boolean(
        sourceValue
        && typeof sourceValue === "object"
        && "applies_to_gene" in sourceValue
        && sourceValue.applies_to_gene,
      )
    }
    if (source === "cosmic") return Object.values(cosmic.availability || {}).some(Boolean)
    return true
  })

  if (!availableSources.length && !census.length && !hallmarks.length) return null

  const hallmarkLabels = Array.from(new Set(hallmarks.flatMap((record) => {
    const value = record.hallmark || record.impact
    return Array.isArray(value) ? value.map(String) : value ? [String(value)] : []
  })))
  const mutationTypes = Array.from(new Set(census.flatMap((record) => {
    const value = record.mutation_types
    if (Array.isArray(value)) return value.map(String)
    return value ? String(value).split(",").map((item) => item.trim()).filter(Boolean) : []
  })))

  return (
    <section className="surface-panel p-4" aria-labelledby="gene-knowledgebase-heading">
      <div className="surface-panel-heading flex items-center gap-2">
        <Database className="size-4 text-primary" />
        <div>
          <h2 id="gene-knowledgebase-heading" className="type-card-title">Knowledgebase context</h2>
          <p className="type-caption text-muted-foreground">
            Gene-level reference evidence. Finding-specific evidence remains on each finding page.
          </p>
        </div>
      </div>
      <div className="grid gap-3 lg:grid-cols-[12rem_minmax(0,1fr)]">
        <div className="content-item flex items-center gap-3 p-3">
          <div className="flex size-20 shrink-0 items-center justify-center rounded-full border-8 border-primary/20 text-center">
            <div>
              <p className="text-xl font-semibold text-primary">{availableSources.length}</p>
              <p className="type-label uppercase text-muted-foreground">sources</p>
            </div>
          </div>
          <div className="min-w-0">
            <p className="type-label uppercase text-muted-foreground">Evidence coverage</p>
            <p className="type-body-sm mt-1 text-foreground">
              {census.length} census and {hallmarks.length} hallmark records
            </p>
          </div>
        </div>
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {availableSources.map((source: string) => (
            <div key={source} className="content-item min-w-0 p-2.5">
              <div className="flex items-center gap-2">
                <Database className="size-4 shrink-0 text-primary" />
                <span className="type-body-sm min-w-0 truncate text-foreground">
                  {sourceLabels[source] || source}
                </span>
              </div>
              {sourceFacts(source, sources[source]).length > 0 && (
                <dl className="mt-2 flex flex-wrap gap-1">
                  {sourceFacts(source, sources[source]).map((fact) => (
                    <div key={fact.label} className="rounded-md bg-muted px-1.5 py-1 type-label text-muted-foreground">
                      <dt className="inline">{fact.label}: </dt>
                      <dd className="inline text-foreground">{displayFact(fact.value)}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </div>
          ))}
        </div>
      </div>
      {(census.length > 0 || hallmarks.length > 0) && (
        <div className="mt-3 columns-1 gap-3 lg:columns-2">
          <div className="mb-3 inline-block w-full break-inside-avoid content-item p-3 align-top">
            <div className="mb-3 flex items-center gap-2">
              <Dna className="size-4 text-primary" />
              <p className="type-section-title">Cancer Gene Census</p>
            </div>
            <div className="space-y-2">
              {census.map((record, index) => (
                <div key={record.cosmic_gene_id || index} className="rounded-md border border-border bg-background/60 p-2.5">
                  <div className="flex flex-wrap items-center gap-1.5">
                    {record.role_in_cancer ? <span className="type-body-sm text-foreground">{record.role_in_cancer}</span> : null}
                    {record.tier ? <TierBadge tier={record.tier} /> : null}
                    <AnalysisIntentBadges somatic={record.somatic} germline={record.germline} showEmpty={false} />
                  </div>
                </div>
              ))}
              {mutationTypes.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {mutationTypes.map((mutationType) => (
                    <TableBadge key={mutationType} className="badge-neutral">{mutationType}</TableBadge>
                  ))}
                </div>
              )}
              {!census.length && <p className="type-body-sm text-muted-foreground">No Cancer Gene Census record.</p>}
            </div>
          </div>
          <div className="mb-3 inline-block w-full break-inside-avoid content-item p-3 align-top">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Sparkles className="size-4 text-primary" />
                <p className="type-section-title">Cancer hallmarks</p>
              </div>
              <span className="flex size-9 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
                {hallmarks.length}
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {hallmarkLabels.map((label) => (
                <TableBadge key={label} className="badge-neutral">{label}</TableBadge>
              ))}
              {!hallmarkLabels.length && <span className="type-body-sm text-muted-foreground">No hallmark records.</span>}
            </div>
          </div>
          <div className="mb-3 inline-block w-full break-inside-avoid content-item p-3 align-top">
            <div className="flex items-center gap-2">
              <Activity className="size-4 text-primary" />
              <div>
                <p className="type-section-title">Interpretation scope</p>
                <p className="type-caption text-muted-foreground">
                  Gene-level context; variant actionability remains finding-specific.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
