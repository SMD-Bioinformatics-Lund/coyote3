import { useEffect, useState } from "react"
import { Link, useLocation, useNavigate, useParams } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { ExpandableText } from "@/components/detail/ExpandableText"
import { VariantActionButtons } from "@/components/detail/VariantActionButtons"
import { ClassificationsCard } from "@/components/detail/FindingDetailCards"
import { CommentsPanel } from "@/components/comments/CommentsPanel"
import { CallerBadges, ConsequenceBadges, FilterFlagBadges, ImpactBadge, PredictionBadge, TierBadge } from "@/lib/variant-ui"
import {
  DetailDataTable,
  DetailMetricTable,
  EvidenceBadge,
  ExternalLinksCard,
} from "@/components/detail/DetailEvidenceCards"
import { displayValue, percentValue } from "@/lib/detail-formatters"
import { GeneWithOncoKbBadge } from "@/components/knowledgebase/OncoKbGeneBadge"
import {
  DetailCard,
  DetailField,
  FindingDetailShell,
  FindingError,
  FindingCallerMeta,
  FindingDetailHero,
  FindingIdentityCard,
  FindingLoading,
  FindingMainGrid,
} from "@/components/detail/FindingDetailLayout"
import { Button } from "@/components/ui/button"
import { TranscriptConsequencesTable } from "@/components/detail/TranscriptConsequencesTable"
import { HotspotIndicator } from "@/components/detail/HotspotIndicator"
import {
  clinpgxApiSummary,
  clinpgxEvidenceColumns,
  clinpgxEvidenceRows,
  clinpgxGeneMetrics,
  externalVariantLinks,
  hpaExpressionRows,
  objectMetrics,
  oncokbActionRows,
  oncokbApiSummary,
  oncokbPublicGeneMetrics,
  VariantKnowledgeBlock,
} from "@/components/detail/VariantKnowledgebase"
import { notifyActionError } from "@/lib/notifications"
import { sampleDetailPath, sampleDetailTabPath, sampleFindingPath, sampleUrlKey } from "@/lib/sample-routing"

function variantLocation(variant: any) {
  if (!variant) return "-"
  const ref = Array.isArray(variant.REF) ? variant.REF.join(",") : variant.REF
  const alt = Array.isArray(variant.ALT) ? variant.ALT.join(",") : variant.ALT
  return `${variant.CHROM}:${variant.POS} ${displayValue(ref)}>${displayValue(alt)}`
}

function clinicalSig(csq: any, variant: any) {
  return csq?.CLIN_SIG || variant?.INFO?.CLNSIG || variant?.INFO?.CLIN_SIG
}

function ponRows(value: any) {
  if (!value || typeof value !== "object") return []
  return Object.entries(value)
    .flatMap(([caller, callerValue]: [string, any]) => {
      if (!callerValue || typeof callerValue !== "object") return []
      return Object.entries(callerValue).map(([metric, metricValue]) => ({
        caller,
        metric,
        value: metricValue,
      }))
    })
}

function brcaExchangeMetrics(record: any) {
  if (!record) {
    return [{ label: "Status", value: "No local BRCA Exchange evidence is available." }]
  }

  const grch38 = record.chr38 && record.pos38
    ? `${record.chr38}:${record.pos38} ${record.ref38 || ""}>${record.alt38 || ""}`.trim()
    : "-"
  return [
    ...objectMetrics(record, [
      { label: "Clinical significance", keys: ["enigma_clinsig"] },
      { label: "References", keys: ["enigma_clinsig_refs"] },
      { label: "Comment", keys: ["enigma_clinsig_comment"] },
    ]),
    { label: "GRCh38", value: grch38, monospace: grch38 !== "-" },
  ]
}

export function VariantDetail() {
  const { id, varId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const [commentDraft, setCommentDraft] = useState("")
  const variantQueryKey = ['variant', id, varId]

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: variantQueryKey,
    queryFn: () => api.get(`/samples/${id}/small-variants/${varId}`).then(res => res.data)
  })
  const { data: filterFlagMetadata } = useQuery({
    queryKey: ["filter-flag-metadata"],
    queryFn: () => api.get("/public/filter-flags/metadata").then(res => res.data),
    staleTime: 10 * 60 * 1000,
  })
  const oncokbPublic = useMutation({
    mutationFn: () => api.get(`/samples/${id}/small-variants/${varId}/oncokb-public`).then(res => res.data),
    onError: (err) => notifyActionError("Unable to load public OncoKB annotation", err, "OncoKB API"),
  })
  const clinpgxPublic = useMutation({
    mutationFn: () => api.get(`/samples/${id}/small-variants/${varId}/clinpgx-public`).then(res => res.data),
    onError: (err) => notifyActionError("Unable to load public ClinPGx gene context", err, "ClinPGx API"),
  })
  const transcriptSelection = useMutation({
    mutationFn: (featureId: string) =>
      api.patch(`/samples/${id}/small-variants/${varId}/selected-transcript`, { feature_id: featureId }).then(res => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: variantQueryKey })
      queryClient.invalidateQueries({ queryKey: ["sample-comment-suggestion", id] })
      refetch()
    },
    onError: (err) => notifyActionError("Unable to select transcript", err, "Transcript selection"),
  })
  const routeSample = data?.sample
  useEffect(() => {
    if (routeSample?.name && id && varId && id !== routeSample.name) {
      navigate(sampleFindingPath(routeSample, id, "variant", varId), {
        replace: true,
        state: location.state,
      })
    }
  }, [id, location.state, navigate, routeSample, routeSample?.name, varId])

  if (isLoading) {
    return <FindingLoading />
  }

  if (error || !data) {
    return (
      <FindingError
        title="Error loading variant"
        message={error instanceof Error ? error.message : "Unknown error"}
        backTo={`/samples/${id}`}
      />
    )
  }

  const { variant, sample, latest_classification } = data
  const sampleRouteKey = sampleUrlKey(sample, id)
  const sampleHref = sampleDetailTabPath(sample, id, "snvs")
  const previousSampleHref = typeof location.state === "object" && location.state && "from" in location.state
    ? String((location.state as { from?: string }).from || sampleHref)
    : sampleHref
  const csq = variant?.INFO?.selected_CSQ || {}
  const displayGene = csq.display_symbol || csq.SYMBOL
  const resolvedGene = csq.SYMBOL
  const alternateTranscripts = Array.isArray(data?.transcripts) ? data.transcripts : []
  const selectedFeature = String(csq?.Feature || "").trim()
  const transcripts = [
    ...(csq && Object.keys(csq).length ? [csq] : []),
    ...alternateTranscripts.filter((row: any) => String(row?.Feature || "").trim() !== selectedFeature),
  ]
  const callers = variant?.INFO?.variant_callers || variant?.callers || []

  const titleVariantId = csq.HGVSp && csq.HGVSp !== "-" ? csq.HGVSp : (csq.HGVSc || variant?.ALT?.[0] || "")

  return (
    <FindingDetailShell>
      <FindingDetailHero
        backTo={previousSampleHref}
        genes={[String(displayGene || resolvedGene || "")]}
        identity={titleVariantId}
        sampleHref={sampleHref}
        sampleName={sample?.name || id}
        callers={
          <FindingCallerMeta>
            <CallerBadges value={callers} />
          </FindingCallerMeta>
        }
        actions={
          <VariantActionButtons
            sampleId={sampleRouteKey}
            resourceType="small_variant"
            variant={variant}
            onUpdate={() => refetch()}
          />
        }
        statLabel="Max VAF"
        statValue={`${variant?.GT ? Math.max(...variant.GT.map((g: any) => g.AF * 100)).toFixed(1) : 0}%`}
      />

      <FindingMainGrid
        main={
          <>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <FindingIdentityCard title="Variant Identity">
                <DetailField label="Gene">
                  <GeneWithOncoKbBadge
                    gene={resolvedGene}
                    displayGene={displayGene}
                    resolvedGene={resolvedGene}
                    hgncId={csq.HGNC_ID}
                    record={data.oncokb_gene}
                    showOncoKbBadge={false}
                  />
                </DetailField>
                <DetailField label="Canonical transcript" valueClassName="text-primary/80">{csq.Feature}</DetailField>
                <DetailField label="Consequence">
                  <ConsequenceBadges value={csq.Consequence} translations={data.vep_conseq_translations} />
                </DetailField>
                <DetailField label="Impact"><ImpactBadge value={csq.IMPACT} /></DetailField>
                <DetailField label="Variant class">{data.vep_var_class_translations?.[variant?.variant_class]?.display_name || variant?.variant_class || csq.VARIANT_CLASS || "-"}</DetailField>
                <DetailField label="Hotspot"><HotspotIndicator variant={variant} showLabel /></DetailField>
                <DetailField label="Position">{variantLocation(variant)}</DetailField>
                <DetailField label="Filter flags"><FilterFlagBadges value={variant?.FILTER} metadata={filterFlagMetadata} /></DetailField>
                <DetailField label="cDNA"><ExpandableText text={csq.HGVSc || "-"} maxLength={24} className="" /></DetailField>
                <DetailField label="Protein"><ExpandableText text={csq.HGVSp || "-"} maxLength={24} className="" /></DetailField>
                <DetailField label="Exon / Intron">{csq.EXON || csq.INTRON || "-"}</DetailField>
                <DetailField label="Indel size">{variant?.INFO?.SVLEN || variant?.indel_size || "-"}</DetailField>
              </FindingIdentityCard>

              <div className="h-full lg:col-span-2">
                <CommentsPanel
                  sampleId={sampleRouteKey}
                  title="Add Comment Or Annotation"
                  resourceType="small_variant"
                  resource={variant}
                  comments={[]}
                  showList={false}
                  assayGroup={data.assay_group}
                  subpanel={data.subpanel}
                  queryKeys={[["variant", id, varId]]}
                  enableSuggestion={false}
                  livePreview={false}
                  draftText={commentDraft}
                  onDraftChange={setCommentDraft}
                  fillHeight
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <CommentsPanel
                sampleId={sampleRouteKey}
                title="Sample-Specific Variant Comments"
                resourceType="small_variant"
                resource={variant}
                comments={variant?.comments || []}
                showComposer={false}
                queryKeys={[["variant", id, varId]]}
                onUseAsDraft={setCommentDraft}
              />
              <CommentsPanel
                sampleId={sampleRouteKey}
                title="Global Variant Annotations"
                resourceType="small_variant"
                resource={variant}
                comments={data.annotations || variant?.global_annotations || []}
                showComposer={false}
                allowHide={false}
                queryKeys={[["variant", id, varId]]}
                onUseAsDraft={setCommentDraft}
              />
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <DetailCard title="Sample Genotype" tone="success">
                <div className="overflow-x-auto">
                  <table className="type-table-cell w-full text-left">
                    <thead className="type-table-header bg-muted/50 text-muted-foreground">
                      <tr>
                        <th className="px-3 py-1">Type</th>
                        <th className="px-3 py-1">VAF</th>
                        <th className="px-3 py-1">Alt Depth</th>
                        <th className="px-3 py-1">Total Depth</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/30">
                      {variant?.GT?.map((gt: any, i: number) => (
                        <tr key={i}>
                          <td className="px-3 py-1 capitalize font-semibold">{gt.type}</td>
                          <td className="type-allele-frequency px-3 py-1">{(gt.AF * 100).toFixed(1)}%</td>
                          <td className="px-3 py-1 ">{gt.VD}</td>
                          <td className="px-3 py-1 ">{gt.DP}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </DetailCard>

              <DetailCard title="Prediction And Clinical Signals">
                <div className="space-y-2">
                  <DetailMetricTable
                    metrics={[
                      { label: "CADD", value: csq.CADD_PHRED, monospace: true },
                      { label: "ClinVar", value: clinicalSig(csq, variant) },
                      { label: "Callers", value: callers },
                      { label: "Selected by", value: variant?.INFO?.selected_CSQ_criteria },
                    ]}
                    dense
                  />
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <div className="rounded-lg border border-border bg-background/50 p-2">
                      <span className="detail-field-label">SIFT</span>
                      <PredictionBadge value={csq.SIFT} />
                    </div>
                    <div className="rounded-lg border border-border bg-background/50 p-2">
                      <span className="detail-field-label">PolyPhen</span>
                      <PredictionBadge value={csq.PolyPhen} />
                    </div>
                  </div>
                </div>
              </DetailCard>
            </div>

            <DetailCard title="Panel Of Normals Evidence" tone="info">
              <DetailDataTable
                rows={ponRows(data.pon) || []}
                empty="No panel-of-normals evidence available."
                columns={[
                  { key: "caller", header: "Tool", render: (row: any) => row.caller || "-" },
                  { key: "metric", header: "Metric", render: (row: any) => row.metric || "-" },
                  { key: "value", header: "Value", render: (row: any) => displayValue(row.value) },
                ]}
              />
            </DetailCard>

            <DetailCard title="Knowledge Bases" tone="success">
              <div className="space-y-2">
                <VariantKnowledgeBlock
                  title="CIViC"
                  defaultOpen
                  badges={data.civic?.length ? <EvidenceBadge tone="success">{data.civic.length} match{data.civic.length === 1 ? "" : "es"}</EvidenceBadge> : null}
                >
                  <DetailDataTable
                    rows={Array.isArray(data.civic) ? data.civic : []}
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
                      />
                    </div>
                  ) : null}
                </VariantKnowledgeBlock>

                <VariantKnowledgeBlock title="BRCA Exchange" defaultOpen>
                  <DetailMetricTable
                    metrics={brcaExchangeMetrics(data.brca_exchange)}
                    dense
                  />
                </VariantKnowledgeBlock>

                <VariantKnowledgeBlock title="IARC TP53" defaultOpen>
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
                        value: String(csq.SYMBOL || "").toUpperCase() === "TP53"
                          ? "No local IARC TP53 record is available for this variant."
                          : "IARC TP53 applies only to TP53 variants.",
                      }]}
                    dense
                  />
                </VariantKnowledgeBlock>

                <VariantKnowledgeBlock title="HPA expression" defaultOpen>
                  <DetailDataTable
                    rows={hpaExpressionRows(data.expression)}
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
                  title="OncoKB public cache"
                  defaultOpen
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
                  <DetailMetricTable metrics={oncokbPublicGeneMetrics(data.oncokb_gene)} dense />
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
                  title="Local actionable evidence"
                  defaultOpen
                  badges={oncokbActionRows(data.oncokb_action).length ? <EvidenceBadge tone="warning">Historical local</EvidenceBadge> : null}
                >
                  <DetailDataTable
                    rows={oncokbActionRows(data.oncokb_action)}
                    empty="No local OncoKB actionable evidence for this variant."
                    columns={[
                      { key: "alteration", header: "Alteration", render: (row: any) => row.Alteration || row["Protein Change"] || "-" },
                      { key: "level", header: "Level", render: (row: any) => row.Level || "-" },
                      { key: "drug", header: "Drug", render: (row: any) => row["Drugs(s)"] || "-" },
                      { key: "cancer", header: "Cancer type", render: (row: any) => row["Cancer Type"] || "-" },
                    ]}
                  />
                </VariantKnowledgeBlock>

                <VariantKnowledgeBlock title="OncoKB API" defaultOpen>
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
                            <DetailMetricTable metrics={oncokbApiSummary(oncokbPublic.data, response)} dense />
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
                  title="ClinPGx"
                  defaultOpen
                  badges={
                    <>
                      {data.clinpgx_gene?.is_vip ? <EvidenceBadge tone="warning">VIP</EvidenceBadge> : null}
                      {data.clinpgx_gene?.has_variant_annotation ? <EvidenceBadge tone="info">Variant annotation</EvidenceBadge> : null}
                      {data.clinpgx_gene?.has_cpic_dosing_guideline ? <EvidenceBadge tone="success">CPIC guideline</EvidenceBadge> : null}
                    </>
                  }
                >
                  <DetailMetricTable metrics={clinpgxGeneMetrics(data.clinpgx_gene)} dense />
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
                      <DetailMetricTable metrics={clinpgxApiSummary(clinpgxPublic.data)} dense />
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
                            columns={clinpgxEvidenceColumns("annotation")}
                            empty="No guideline annotations returned by ClinPGx."
                          />
                        </div>
                        <div>
                          <h5 className="mb-1.5 type-meta font-semibold uppercase tracking-wide text-muted-foreground">Drug labels</h5>
                          <DetailDataTable
                            rows={clinpgxEvidenceRows(clinpgxPublic.data, "labels")}
                            columns={clinpgxEvidenceColumns("annotation")}
                            empty="No drug-label annotations returned by ClinPGx."
                          />
                        </div>
                        <div>
                          <h5 className="mb-1.5 type-meta font-semibold uppercase tracking-wide text-muted-foreground">Top connected drugs</h5>
                          <DetailDataTable
                            rows={clinpgxEvidenceRows(clinpgxPublic.data, "top_chemicals")}
                            columns={clinpgxEvidenceColumns("object")}
                            empty="No connected drugs returned by ClinPGx."
                          />
                        </div>
                        <div>
                          <h5 className="mb-1.5 type-meta font-semibold uppercase tracking-wide text-muted-foreground">Pathways</h5>
                          <DetailDataTable
                            rows={clinpgxEvidenceRows(clinpgxPublic.data, "pathways")}
                            columns={clinpgxEvidenceColumns("object")}
                            empty="No pathways returned by ClinPGx."
                          />
                        </div>
                      </div>
                      <div>
                        <h5 className="mb-1.5 type-meta font-semibold uppercase tracking-wide text-muted-foreground">Variant annotation examples</h5>
                        <DetailDataTable
                          rows={clinpgxEvidenceRows(clinpgxPublic.data, "variant_annotations")}
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
              </div>
            </DetailCard>

            <DetailCard title="Transcript Consequences">
              <TranscriptConsequencesTable
                rows={transcripts}
                selectedFeature={selectedFeature}
                consequenceTranslations={data.vep_conseq_translations}
                selecting={transcriptSelection.isPending}
                onSelectTranscript={(featureId) => transcriptSelection.mutate(featureId)}
              />
            </DetailCard>
          </>
        }
        aside={
          <>
            <ClassificationsCard
              latest={latest_classification}
              other={data.other_classifications || variant?.additional_classifications || []}
              sampleId={sampleRouteKey}
              resourceType="small_variant"
              resourceId={String(variant?._id || "")}
              onUpdate={() => refetch()}
            />

            <ExternalLinksCard links={externalVariantLinks(variant, csq, data)} />

            <DetailCard title="Population Frequencies" tone="info">
              <DetailMetricTable
                metrics={[
                  { label: "gnomAD", value: percentValue(variant?.gnomad_frequency, 4) },
                  { label: "gnomAD max", value: percentValue(variant?.gnomad_max, 4) },
                  { label: "ExAC", value: percentValue(variant?.exac_frequency, 4) },
                  { label: "1000G", value: percentValue(variant?.thousandG_frequency, 4) },
                ]}
                dense
              />
            </DetailCard>

            <DetailCard title="Seen In Other Samples" tone="info">
              <DetailDataTable
                rows={data.in_other_samples || data.in_other || []}
                empty="No matching variants found in other samples."
                columns={[
                  {
                    key: "sample",
                    header: "Sample",
                    render: (row: any) => {
                      const sampleName = row.sample_name || row.sample || row.SAMPLE || row.name
                      return sampleName ? (
                        <Link to={sampleDetailPath(row, sampleName)} className="link-text">
                          {sampleName}
                        </Link>
                      ) : "-"
                    },
                  },
                  { key: "assay_group", header: "Assay group", render: (row: any) => row.assay_group || "-" },
                  { key: "vaf", header: "VAF", render: (row: any) => <span className="type-allele-frequency">{percentValue(row.vaf, 1)}</span> },
                  { key: "tier", header: "Tier", render: (row: any) => <TierBadge tier={row.classification?.class ?? row.class ?? row.tier} /> },
                ]}
              />
            </DetailCard>
          </>
        }
      />
    </FindingDetailShell>
  )
}
