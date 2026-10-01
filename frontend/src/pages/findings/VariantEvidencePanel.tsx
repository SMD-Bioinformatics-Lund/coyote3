import {
  DetailDataTable,
  DetailMetricTable,
  EvidenceBadge
} from "@/components/detail/DetailEvidenceCards"
import {
  DetailCard
} from "@/components/detail/FindingDetailLayout"
import {
  clinpgxApiSummary,
  clinpgxEvidenceColumns,
  clinpgxEvidenceRows,
  clinpgxGeneMetrics,
  CosmicKnowledgeBlock,
  hpaExpressionRows,
  KnowledgebaseExplorer,
  KnowledgebaseGrid,
  objectMetrics,
  oncokbActionRows,
  oncokbApiSummary,
  oncokbPublicGeneMetrics,
  VariantKnowledgeBlock
} from "@/components/detail/VariantKnowledgebase"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import { displayValue } from "@/lib/detail-formatters"
import { notifyActionError } from "@/lib/notifications"
import { useMutation } from "@tanstack/react-query"
import { brcaExchangeMetrics } from "./variant-detail-presentation"

type VariantEvidence = {
  cosmic?: unknown
  civic?: unknown[]
  civic_gene?: Record<string, unknown>
  brca_exchange?: unknown
  iarc_tp53?: Record<string, unknown>
  expression?: unknown
  oncokb_action?: unknown
  oncokb_gene?: {
    public_cancer_gene?: boolean
    oncokb_annotated?: boolean
    gene_summary?: string
    background?: string
  }
  clinpgx_gene?: {
    is_vip?: boolean
    has_variant_annotation?: boolean
    has_cpic_dosing_guideline?: boolean
    alternate_symbols?: string[]
  }
}

export function VariantEvidencePanel({ data, geneSymbol, id, varId }: {
  data: VariantEvidence
  geneSymbol?: string
  id?: string
  varId?: string
}) {
  const oncokbPublic = useMutation({
    mutationFn: () => api.get(`/samples/${id}/small-variants/${varId}/oncokb-public`).then(res => res.data),
    onError: (err) => notifyActionError("Unable to load public OncoKB annotation", err, "OncoKB API"),
  })
  const clinpgxPublic = useMutation({
    mutationFn: () => api.get(`/samples/${id}/small-variants/${varId}/clinpgx-public`).then(res => res.data),
    onError: (err) => notifyActionError("Unable to load public ClinPGx gene context", err, "ClinPGx API"),
  })
  return (
    <DetailCard title="Knowledge Bases" tone="success">
      <KnowledgebaseExplorer>
        <CosmicKnowledgeBlock evidence={data.cosmic} />

        <KnowledgebaseGrid>
          <VariantKnowledgeBlock
            source="civic"
            title="CIViC"
            defaultOpen
            searchData={[data.civic, data.civic_gene]}
            badges={data.civic?.length ? <EvidenceBadge tone="success">{data.civic.length} match{data.civic.length === 1 ? "" : "es"}</EvidenceBadge> : null}
          >
          <DetailDataTable
            rows={Array.isArray(data.civic) ? data.civic : []}
            initialRows={10}
            empty="No local CIViC variant evidence is available."
            columns={[
              { key: "variant", header: "Variant", render: (row: any) => row.variant || "-" },
              { key: "types", header: "Types", render: (row: any) => row.variant_types || "-" },
              { key: "score", header: "Actionability", render: (row: any) => displayValue(row.civic_actionability_score) },
              {
                key: "link",
                header: "Record",
                render: (row: any) => row.variant_civic_url ? <a className="link-text" href={row.variant_civic_url} target="_blank" rel="noreferrer">Open CIViC</a> : "-",
              },
            ]}
          />
          {data.civic_gene ? (
            <div className="mt-3">
              <DetailMetricTable
                metrics={objectMetrics(data.civic_gene, [
                  { label: "Gene", keys: ["name"] },
                  { label: "Entrez", keys: ["entrez_id"] },
                  { label: "Last reviewed", keys: ["last_review_date"] },
                  { label: "Record", keys: ["gene_civic_url"] },
                ]).map((metric) => ({
                  ...metric,
                  href: metric.label === "Record" && typeof metric.value === "string" && metric.value.startsWith("http") ? metric.value : undefined,
                }))}
                dense
                initialRows={10}
              />
            </div>
          ) : null}
        </VariantKnowledgeBlock>

        <VariantKnowledgeBlock source="brca-exchange" title="BRCA Exchange" defaultOpen searchData={data.brca_exchange}>
          <DetailMetricTable
            metrics={brcaExchangeMetrics(data.brca_exchange)}
            dense
            initialRows={10}
          />
        </VariantKnowledgeBlock>

        <VariantKnowledgeBlock source="iarc-tp53" title="IARC TP53" defaultOpen searchData={data.iarc_tp53}>
          <DetailMetricTable
            metrics={data.iarc_tp53
              ? objectMetrics(data.iarc_tp53, [
                { label: "cDNA", keys: ["var"] },
                { label: "Somatic observations", keys: ["n_somatic"] },
                { label: "Germline observations", keys: ["n_germline"] },
                { label: "Transactivation class", keys: ["transactivation_class"] },
                { label: "Domain function", keys: ["domain_func"] },
              ])
              : [{
                label: "Status",
                value: String(geneSymbol || "").toUpperCase() === "TP53"
                  ? "No local IARC TP53 record is available for this variant."
                  : "IARC TP53 applies only to TP53 variants.",
              }]}
            dense
            initialRows={10}
          />
        </VariantKnowledgeBlock>

        <VariantKnowledgeBlock source="hpa" title="HPA expression" defaultOpen searchData={data.expression}>
          <DetailDataTable
            rows={hpaExpressionRows(data.expression)}
            initialRows={10}
            empty="No local HPA transcript expression is available."
            columns={[
              { key: "transcript", header: "Transcript", render: (row) => row.transcript },
              { key: "tissues", header: "Tissues", render: (row) => row.tissues },
              { key: "top_tissue", header: "Highest tissue", render: (row) => row.top_tissue },
              { key: "top_expression", header: "Expression", render: (row) => displayValue(row.top_expression) },
            ]}
          />
        </VariantKnowledgeBlock>

        <VariantKnowledgeBlock
          source="oncokb"
          title="OncoKB public cache"
          defaultOpen
          searchData={data.oncokb_gene}
          badges={
            <>
              {data.oncokb_gene?.public_cancer_gene || data.oncokb_gene?.oncokb_annotated != null ? (
                <EvidenceBadge tone="info">Cancer gene</EvidenceBadge>
              ) : null}
              {data.oncokb_gene?.gene_summary || data.oncokb_gene?.background ? (
                <EvidenceBadge tone="success">Curated gene</EvidenceBadge>
              ) : null}
            </>
          }
        >
          <DetailMetricTable metrics={oncokbPublicGeneMetrics(data.oncokb_gene)} dense initialRows={10} />
          {data.oncokb_gene?.gene_summary ? (
            <div className="mt-2 rounded-lg border border-border/70 bg-card/60 p-3">
              <p className="type-meta font-semibold uppercase tracking-wide text-muted-foreground">Gene summary</p>
              <p className="mt-1 text-sm leading-relaxed text-foreground">{data.oncokb_gene.gene_summary}</p>
            </div>
          ) : null}
          {data.oncokb_gene?.background ? (
            <div className="mt-2 rounded-lg border border-border/70 bg-card/60 p-3">
              <p className="type-meta font-semibold uppercase tracking-wide text-muted-foreground">Background</p>
              <p className="mt-1 text-sm leading-relaxed text-foreground">{data.oncokb_gene.background}</p>
            </div>
          ) : null}
        </VariantKnowledgeBlock>

        <VariantKnowledgeBlock
          source="oncokb"
          title="Local actionable evidence"
          defaultOpen
          searchData={data.oncokb_action}
          badges={oncokbActionRows(data.oncokb_action).length ? <EvidenceBadge tone="warning">Historical local</EvidenceBadge> : null}
        >
          <DetailDataTable
            rows={oncokbActionRows(data.oncokb_action)}
            initialRows={10}
            empty="No local OncoKB actionable evidence for this variant."
            columns={[
              { key: "alteration", header: "Alteration", render: (row: any) => row.Alteration || row["Protein Change"] || "-" },
              { key: "level", header: "Level", render: (row: any) => row.Level || "-" },
              { key: "drug", header: "Drug", render: (row: any) => row["Drugs(s)"] || "-" },
              { key: "cancer", header: "Cancer type", render: (row: any) => row["Cancer Type"] || "-" },
            ]}
          />
        </VariantKnowledgeBlock>

        <VariantKnowledgeBlock source="oncokb" title="OncoKB API" defaultOpen searchData={oncokbPublic.data}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="type-meta text-muted-foreground">
              Public API lookup. Therapeutic data is excluded by public OncoKB access.
            </p>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={oncokbPublic.isPending}
              onClick={() => oncokbPublic.mutate()}
            >
              {oncokbPublic.isPending ? "Loading..." : "Fetch public OncoKB"}
            </Button>
          </div>
          {oncokbPublic.data ? (
            <div className="mt-3 space-y-3">
              {oncokbPublic.data.message ? (
                <p className="type-meta text-muted-foreground">{oncokbPublic.data.message}</p>
              ) : null}
              {Object.entries(oncokbPublic.data.responses || {}).map(([intent, response]) => (
                <div key={intent} className="rounded-lg border border-border/70 bg-card/60 p-3">
                  <p className="type-meta font-semibold uppercase tracking-wide text-muted-foreground">
                    {intent} annotation
                  </p>
                  <div className="mt-2">
                    <DetailMetricTable metrics={oncokbApiSummary(oncokbPublic.data, response)} dense initialRows={10} />
                  </div>
                </div>
              ))}
              {Object.entries(oncokbPublic.data.failures || {}).map(([intent, message]) => (
                <p key={intent} className="type-meta text-destructive" role="alert">
                  {intent} annotation could not be retrieved: {String(message)}
                </p>
              ))}
              <p className="type-meta text-muted-foreground">
                Query: {oncokbPublic.data.query?.genomicLocation || "-"} ({oncokbPublic.data.query?.referenceGenome || "-"})
              </p>
              <p className="type-meta text-muted-foreground">
                Coyote3 context: {oncokbPublic.data.analysis_context?.analysis_intents?.length
                  ? oncokbPublic.data.analysis_context.analysis_intents.join(", ")
                  : "not recorded"}
              </p>
            </div>
          ) : null}
          {oncokbPublic.isError ? (
            <p className="mt-3 type-meta text-destructive" role="alert">
              {oncokbPublic.error instanceof Error
                ? oncokbPublic.error.message
                : "The public OncoKB lookup could not be completed."}
            </p>
          ) : null}
        </VariantKnowledgeBlock>

        <VariantKnowledgeBlock
          source="clinpgx"
          title="ClinPGx"
          defaultOpen
          searchData={[data.clinpgx_gene, clinpgxPublic.data]}
          badges={
            <>
              {data.clinpgx_gene?.is_vip ? <EvidenceBadge tone="warning">VIP</EvidenceBadge> : null}
              {data.clinpgx_gene?.has_variant_annotation ? <EvidenceBadge tone="info">Variant annotation</EvidenceBadge> : null}
              {data.clinpgx_gene?.has_cpic_dosing_guideline ? <EvidenceBadge tone="success">CPIC guideline</EvidenceBadge> : null}
            </>
          }
        >
          <DetailMetricTable metrics={clinpgxGeneMetrics(data.clinpgx_gene)} dense initialRows={10} />
          {data.clinpgx_gene?.alternate_symbols?.length ? (
            <p className="mt-2 type-meta text-muted-foreground">
              Alternate symbols: {data.clinpgx_gene.alternate_symbols.join(", ")}
            </p>
          ) : null}
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border/70 bg-card/60 p-3">
            <p className="mt-0.5 type-meta text-muted-foreground">
              Public API lookup for PGx guidelines, labels, variant annotations, drugs, and pathways.
            </p>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={clinpgxPublic.isPending}
              onClick={() => clinpgxPublic.mutate()}
            >
              {clinpgxPublic.isPending ? "Loading..." : "Fetch ClinPGx"}
            </Button>
          </div>

          {clinpgxPublic.data ? (
            <div className="mt-3 space-y-3">
              <DetailMetricTable metrics={clinpgxApiSummary(clinpgxPublic.data)} dense initialRows={10} />
              {clinpgxPublic.data.response?.vip?.summary ? (
                <div className="rounded-lg border border-border/70 bg-card/60 p-3">
                  <p className="type-meta font-semibold uppercase tracking-wide text-muted-foreground">VIP summary</p>
                  <p className="mt-1 text-sm leading-relaxed text-foreground">{clinpgxPublic.data.response.vip.summary}</p>
                </div>
              ) : null}
              <div className="grid gap-3 xl:grid-cols-2">
                <div>
                  <h5 className="mb-1.5 type-meta font-semibold uppercase tracking-wide text-muted-foreground">Guidelines</h5>
                  <DetailDataTable
                    rows={clinpgxEvidenceRows(clinpgxPublic.data, "guidelines")}
                    initialRows={10}
                    columns={clinpgxEvidenceColumns("annotation")}
                    empty="No guideline annotations returned by ClinPGx."
                  />
                </div>
                <div>
                  <h5 className="mb-1.5 type-meta font-semibold uppercase tracking-wide text-muted-foreground">Drug labels</h5>
                  <DetailDataTable
                    rows={clinpgxEvidenceRows(clinpgxPublic.data, "labels")}
                    initialRows={10}
                    columns={clinpgxEvidenceColumns("annotation")}
                    empty="No drug-label annotations returned by ClinPGx."
                  />
                </div>
                <div>
                  <h5 className="mb-1.5 type-meta font-semibold uppercase tracking-wide text-muted-foreground">Top connected drugs</h5>
                  <DetailDataTable
                    rows={clinpgxEvidenceRows(clinpgxPublic.data, "top_chemicals")}
                    initialRows={10}
                    columns={clinpgxEvidenceColumns("object")}
                    empty="No connected drugs returned by ClinPGx."
                  />
                </div>
                <div>
                  <h5 className="mb-1.5 type-meta font-semibold uppercase tracking-wide text-muted-foreground">Pathways</h5>
                  <DetailDataTable
                    rows={clinpgxEvidenceRows(clinpgxPublic.data, "pathways")}
                    initialRows={10}
                    columns={clinpgxEvidenceColumns("object")}
                    empty="No pathways returned by ClinPGx."
                  />
                </div>
              </div>
              <div>
                <h5 className="mb-1.5 type-meta font-semibold uppercase tracking-wide text-muted-foreground">Variant annotation examples</h5>
                <DetailDataTable
                  rows={clinpgxEvidenceRows(clinpgxPublic.data, "variant_annotations")}
                  initialRows={10}
                  columns={clinpgxEvidenceColumns("annotation")}
                  empty="No variant annotations returned by ClinPGx."
                />
              </div>
              <p className="mt-2 type-meta text-muted-foreground">
                Query: {clinpgxPublic.data.query?.clinpgx_id || clinpgxPublic.data.query?.symbol || "-"}
              </p>
            </div>
          ) : null}
          {clinpgxPublic.isError ? (
            <p className="mt-3 type-meta text-destructive" role="alert">
              {clinpgxPublic.error instanceof Error
                ? clinpgxPublic.error.message
                : "The public ClinPGx lookup could not be completed."}
            </p>
          ) : null}
        </VariantKnowledgeBlock>
        </KnowledgebaseGrid>
      </KnowledgebaseExplorer>
    </DetailCard>

  )
}
