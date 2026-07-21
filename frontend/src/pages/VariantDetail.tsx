import { useEffect, useState } from "react"
import { Link, useLocation, useNavigate, useParams } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { ExpandableText } from "@/components/detail/ExpandableText"
import { VariantActionButtons } from "@/components/detail/VariantActionButtons"
import { ClassificationsCard } from "@/components/detail/FindingDetailCards"
import { CommentsPanel } from "@/components/comments/CommentsPanel"
import { CallerBadges, ConsequenceBadges, FilterFlagBadges, ImpactBadge, PredictionBadge } from "@/lib/variant-ui"
import {
  DetailDataTable,
  DetailMetricTable,
  EvidenceBadge,
  ExternalLinksCard,
} from "@/components/detail/DetailEvidenceCards"
import { displayValue, isPresent, percentValue } from "@/lib/detail-formatters"
import { GeneWithOncoKbBadge } from "@/components/knowledgebase/OncoKbGeneBadge"
import {
  DetailCard,
  DetailField,
  DetailFieldGrid,
  FindingDetailShell,
  FindingError,
  FindingHero,
  FindingLoading,
  FindingMainGrid,
} from "@/components/detail/FindingDetailLayout"
import { Button } from "@/components/ui/button"
import { notifyActionError } from "@/lib/notifications"
import { sampleDetailTabPath, sampleFindingPath, sampleUrlKey } from "@/lib/sample-routing"
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

function variantLocation(variant: any) {
  if (!variant) return "-"
  const ref = Array.isArray(variant.REF) ? variant.REF.join(",") : variant.REF
  const alt = Array.isArray(variant.ALT) ? variant.ALT.join(",") : variant.ALT
  return `${variant.CHROM}:${variant.POS} ${displayValue(ref)}>${displayValue(alt)}`
}

function clinicalSig(csq: any, variant: any) {
  return csq?.CLIN_SIG || variant?.INFO?.CLNSIG || variant?.INFO?.CLIN_SIG
}

function compactObjectSummary(value: any) {
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

function oncokbApiSummary(payload: any) {
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

function oncokbPublicGeneMetrics(record: any) {
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

function oncokbActionRows(value: any) {
  if (!value) return []
  return Array.isArray(value) ? value : [value]
}

function clinpgxGeneMetrics(record: any) {
  if (!record) return []
  return [
    { label: "ClinPGx ID", value: record.pharmgkb_accession_id, monospace: true },
    { label: "HGNC", value: record.hgnc_id, monospace: true },
    { label: "VIP", value: record.is_vip == null ? "-" : String(Boolean(record.is_vip)) },
    {
      label: "Variant annotation",
      value: record.has_variant_annotation == null ? "-" : String(Boolean(record.has_variant_annotation)),
    },
    {
      label: "CPIC dosing guideline",
      value: record.has_cpic_dosing_guideline == null ? "-" : String(Boolean(record.has_cpic_dosing_guideline)),
    },
  ]
}

function clinpgxApiSummary(payload: any) {
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

function KnowledgeBlock({ title, badges, defaultOpen = false, children }: { title: string; badges?: any; defaultOpen?: boolean; children: any }) {
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
      <div className="border-t border-border px-3 py-3">
        {children}
      </div>
    </details>
  )
}

function clinpgxEvidenceRows(payload: any, key: string) {
  const response = payload?.response || {}
  return Array.isArray(response?.[key]) ? response[key] : []
}

function clinpgxEvidenceColumns(kind: "annotation" | "object") {
  if (kind === "object") {
    return [
      { key: "name", header: "Name", render: (row: any) => <span className="font-semibold">{row.name || "-"}</span> },
      { key: "type", header: "Type", render: (row: any) => row.type || "-" },
      {
        key: "connections",
        header: "Connections",
        render: (row: any) => (Array.isArray(row.connection_types) && row.connection_types.length ? row.connection_types.join(", ") : "-"),
      },
    ]
  }
  return [
    { key: "name", header: "Annotation", render: (row: any) => <span className="font-semibold">{row.name || row.id || "-"}</span> },
    { key: "type", header: "Type", render: (row: any) => row.type || "-" },
    {
      key: "summary",
      header: "Summary",
      render: (row: any) => (
        <ExpandableText
          text={row.sentence || row.description || row.significance || "-"}
          maxLength={96}
          className="max-w-xl text-xs leading-5 text-muted-foreground"
        />
      ),
    },
  ]
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

function externalLinks(variant: any, csq: any, data: any) {
  const gene = csq?.SYMBOL
  const hgvsp = csq?.HGVSp
  const dbsnp = variant?.dbsnp_id
  const cosmic = Array.isArray(variant?.cosmic_ids) ? variant.cosmic_ids[0] : undefined
  const pubmed = Array.isArray(variant?.pubmed_ids) ? variant.pubmed_ids[0] : undefined
  const clinvar = variant?.INFO?.CLNACC
  const position = variant?.CHROM && variant?.POS ? `${variant.CHROM}:${variant.POS}` : ""

  return [
    data?.bam_id && position ? { label: "Open region in IGV", value: position, href: igvLoadUrl(data.bam_id, position) } : null,
    dbsnp ? { label: `dbSNP ${dbsnp}`, value: dbsnp, href: dbsnpUrl(dbsnp) } : null,
    cosmic ? { label: `COSMIC ${cosmic}`, value: cosmic, href: cosmicSearchUrl(cosmic) } : null,
    clinvar ? { label: `ClinVar ${clinvar}`, value: clinvar, href: clinvarSearchUrl(clinvar) } : null,
    gene ? { label: `cBioPortal ${gene}`, value: gene, href: cbioportalOncoprintUrl(gene) } : null,
    gene ? { label: `OncoKB ${gene}`, value: gene, href: oncokbGeneUrl(gene) } : null,
    gene && hgvsp ? { label: "LitVar", value: `${gene} ${hgvsp}`, href: litvarSearchUrl(`${gene} ${hgvsp}`) } : null,
    pubmed ? { label: `PubMed ${pubmed}`, value: pubmed, href: pubmedArticleUrl(pubmed) } : null,
  ].filter(Boolean) as any[]
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
  const displayGene = csq.VEP_SYMBOL || csq.display_symbol || csq.SYMBOL
  const resolvedGene = csq.SYMBOL
  const alternateTranscripts = Array.isArray(variant?.INFO?.CSQ) ? variant.INFO.CSQ : []
  const selectedFeature = String(csq?.Feature || "").trim()
  const transcripts = [
    ...(csq && Object.keys(csq).length ? [csq] : []),
    ...alternateTranscripts.filter((row: any) => String(row?.Feature || "").trim() !== selectedFeature),
  ]
  const callers = variant?.INFO?.variant_callers || variant?.callers || []

  const titleVariantId = csq.HGVSp && csq.HGVSp !== "-" ? csq.HGVSp : (csq.HGVSc || variant?.ALT?.[0] || "")

  return (
    <FindingDetailShell>
      <FindingHero
        backTo={previousSampleHref}
        title={
          <span className="inline-flex items-center gap-2">
            <GeneWithOncoKbBadge
              gene={resolvedGene}
              displayGene={displayGene}
              resolvedGene={resolvedGene}
              hgncId={csq.HGNC_ID}
              matchSource={csq.HGNC_MATCH_SOURCE}
              record={data.oncokb_gene}
              showOncoKbBadge={false}
            />
          </span>
        }
        subtitle={
          <div className="space-y-2">
            <span className="block text-xl font-bold text-muted-foreground">
              <ExpandableText text={titleVariantId} maxLength={30} className="inline-flex" />
            </span>
            <Link to={sampleHref} className="inline-flex w-max rounded-full border border-border bg-muted px-2.5 py-1 text-xs font-bold text-muted-foreground transition-colors hover:bg-primary/10 hover:text-primary">
              Sample {sample?.name || id}
            </Link>
          </div>
        }
        chips={
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] font-black uppercase tracking-wide text-muted-foreground">Called by</span>
            <CallerBadges value={callers} />
          </div>
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
              <DetailCard title="Variant Identity">
                <DetailFieldGrid>
                  <DetailField label="Gene">
                    <GeneWithOncoKbBadge
                      gene={resolvedGene}
                      displayGene={displayGene}
                      resolvedGene={resolvedGene}
                      hgncId={csq.HGNC_ID}
                      matchSource={csq.HGNC_MATCH_SOURCE}
                      record={data.oncokb_gene}
                      showOncoKbBadge={false}
                    />
                  </DetailField>
                  <DetailField label="Canonical transcript" valueClassName="font-mono text-primary/80">{csq.Feature}</DetailField>
                  <DetailField label="Consequence">
                    <ConsequenceBadges value={csq.Consequence} translations={data.vep_conseq_translations} />
                  </DetailField>
                  <DetailField label="Impact"><ImpactBadge value={csq.IMPACT} /></DetailField>
                  <DetailField label="Variant class">{data.vep_var_class_translations?.[variant?.variant_class]?.display_name || variant?.variant_class || csq.VARIANT_CLASS || "-"}</DetailField>
                  <DetailField label="Position" valueClassName="font-mono">{variantLocation(variant)}</DetailField>
                  <DetailField label="Filter flags"><FilterFlagBadges value={variant?.FILTER} metadata={filterFlagMetadata} /></DetailField>
                  <DetailField label="cDNA"><ExpandableText text={csq.HGVSc || "-"} maxLength={24} className="font-mono" /></DetailField>
                  <DetailField label="Protein"><ExpandableText text={csq.HGVSp || "-"} maxLength={24} className="font-mono" /></DetailField>
                  <DetailField label="Exon / Intron">{csq.EXON || csq.INTRON || "-"}</DetailField>
                  <DetailField label="Indel size">{variant?.INFO?.SVLEN || variant?.indel_size || "-"}</DetailField>
                </DetailFieldGrid>
              </DetailCard>

            <div className="lg:col-span-2">
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
                  <table className="w-full text-left text-sm">
                    <thead className="bg-muted/50 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      <tr>
                        <th className="px-3 py-2">Type</th>
                        <th className="px-3 py-2">VAF</th>
                        <th className="px-3 py-2">Alt Depth</th>
                        <th className="px-3 py-2">Total Depth</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/30">
                      {variant?.GT?.map((gt: any, i: number) => (
                        <tr key={i}>
                          <td className="px-3 py-2 capitalize font-semibold">{gt.type}</td>
                          <td className="px-3 py-2 font-mono">{(gt.AF * 100).toFixed(1)}%</td>
                          <td className="px-3 py-2 font-mono">{gt.VD}</td>
                          <td className="px-3 py-2 font-mono">{gt.DP}</td>
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

            <DetailCard title="Transcript Consequences">
              <DetailDataTable
                rows={transcripts}
                empty="No alternate transcript annotations available."
                columns={[
                  { key: "gene", header: "Gene", render: (row: any) => (
                    <span className="inline-flex items-center gap-1.5">
                      <span>{row.SYMBOL || "-"}</span>
                      {row.Feature === csq.Feature ? <EvidenceBadge tone="success">Selected</EvidenceBadge> : null}
                    </span>
                  ) },
                  { key: "feature", header: "Transcript", render: (row: any) => <span className="font-mono">{row.Feature || "-"}</span> },
                  { key: "hgvsc", header: "cDNA", render: (row: any) => <ExpandableText text={row.HGVSc || "-"} maxLength={28} className="font-mono" /> },
                  { key: "hgvsp", header: "Protein", render: (row: any) => <ExpandableText text={row.HGVSp || "-"} maxLength={28} className="font-mono" /> },
                  { key: "consequence", header: "Consequence", render: (row: any) => <ConsequenceBadges value={row.Consequence} translations={data.vep_conseq_translations} /> },
                  { key: "exon", header: "Exon/Intron", render: (row: any) => row.EXON || row.INTRON || "-" },
                  { key: "impact", header: "Impact", render: (row: any) => <ImpactBadge value={row.IMPACT} /> },
                  {
                    key: "actions",
                    header: "Actions",
                    render: (row: any) => (
                      row.Feature === csq.Feature ? (
                        <EvidenceBadge tone="success">Primary</EvidenceBadge>
                      ) : (
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 px-2 text-xs"
                          disabled={!row.Feature || transcriptSelection.isPending}
                          onClick={() => transcriptSelection.mutate(String(row.Feature))}
                        >
                          Use transcript
                        </Button>
                      )
                    ),
                  },
                ]}
              />
            </DetailCard>

            <DetailCard title="Knowledge Bases" tone="success">
              <div className="space-y-2">
                <KnowledgeBlock title="Clinical knowledgebase summary" defaultOpen>
                  <DetailMetricTable
                    metrics={[
                      { label: "CIViC variant", value: compactObjectSummary(data.civic) },
                      { label: "CIViC gene", value: compactObjectSummary(data.civic_gene) },
                      { label: "BRCA Exchange", value: compactObjectSummary(data.brca_exchange) },
                      { label: "IARC TP53", value: compactObjectSummary(data.iarc_tp53) },
                    ]}
                    dense
                  />
                </KnowledgeBlock>

                <KnowledgeBlock
                  title="OncoKB public cache"
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
                      <p className="text-[11px] font-black uppercase tracking-wide text-muted-foreground">Gene summary</p>
                      <p className="mt-1 text-sm leading-relaxed text-foreground">{data.oncokb_gene.gene_summary}</p>
                    </div>
                  ) : null}
                  {data.oncokb_gene?.background ? (
                    <div className="mt-2 rounded-lg border border-border/70 bg-card/60 p-3">
                      <p className="text-[11px] font-black uppercase tracking-wide text-muted-foreground">Background</p>
                      <p className="mt-1 text-sm leading-relaxed text-foreground">{data.oncokb_gene.background}</p>
                    </div>
                  ) : null}
                </KnowledgeBlock>

                <KnowledgeBlock
                  title="Local actionable evidence"
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
                </KnowledgeBlock>

                <KnowledgeBlock title="OncoKB API">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-[11px] text-muted-foreground">
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
                    <div className="mt-3">
                      <DetailMetricTable metrics={oncokbApiSummary(oncokbPublic.data)} dense />
                      <p className="mt-2 text-[11px] text-muted-foreground">
                        Query: {oncokbPublic.data.query?.hgvsg || `${oncokbPublic.data.query?.gene?.hugoSymbol || ""} ${oncokbPublic.data.query?.alteration || ""}`.trim() || "-"} ({oncokbPublic.data.query?.referenceGenome || "-"})
                      </p>
                    </div>
                  ) : null}
                </KnowledgeBlock>

                <KnowledgeBlock
                  title="ClinPGx"
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
                    <p className="mt-2 text-[11px] text-muted-foreground">
                      Alternate symbols: {data.clinpgx_gene.alternate_symbols.join(", ")}
                    </p>
                  ) : null}
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border/70 bg-card/60 p-3">
                    <p className="mt-0.5 text-[11px] text-muted-foreground">
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
                          <p className="text-[11px] font-black uppercase tracking-wide text-muted-foreground">VIP summary</p>
                          <p className="mt-1 text-sm leading-relaxed text-foreground">{clinpgxPublic.data.response.vip.summary}</p>
                        </div>
                      ) : null}
                      <div className="grid gap-3 xl:grid-cols-2">
                        <div>
                          <h5 className="mb-1.5 text-[11px] font-black uppercase tracking-wide text-muted-foreground">Guidelines</h5>
                          <DetailDataTable
                            rows={clinpgxEvidenceRows(clinpgxPublic.data, "guidelines")}
                            columns={clinpgxEvidenceColumns("annotation")}
                            empty="No guideline annotations returned by ClinPGx."
                          />
                        </div>
                        <div>
                          <h5 className="mb-1.5 text-[11px] font-black uppercase tracking-wide text-muted-foreground">Drug labels</h5>
                          <DetailDataTable
                            rows={clinpgxEvidenceRows(clinpgxPublic.data, "labels")}
                            columns={clinpgxEvidenceColumns("annotation")}
                            empty="No drug-label annotations returned by ClinPGx."
                          />
                        </div>
                        <div>
                          <h5 className="mb-1.5 text-[11px] font-black uppercase tracking-wide text-muted-foreground">Top connected drugs</h5>
                          <DetailDataTable
                            rows={clinpgxEvidenceRows(clinpgxPublic.data, "top_chemicals")}
                            columns={clinpgxEvidenceColumns("object")}
                            empty="No connected drugs returned by ClinPGx."
                          />
                        </div>
                        <div>
                          <h5 className="mb-1.5 text-[11px] font-black uppercase tracking-wide text-muted-foreground">Pathways</h5>
                          <DetailDataTable
                            rows={clinpgxEvidenceRows(clinpgxPublic.data, "pathways")}
                            columns={clinpgxEvidenceColumns("object")}
                            empty="No pathways returned by ClinPGx."
                          />
                        </div>
                      </div>
                      <div>
                        <h5 className="mb-1.5 text-[11px] font-black uppercase tracking-wide text-muted-foreground">Variant annotation examples</h5>
                        <DetailDataTable
                          rows={clinpgxEvidenceRows(clinpgxPublic.data, "variant_annotations")}
                          columns={clinpgxEvidenceColumns("annotation")}
                          empty="No variant annotations returned by ClinPGx."
                        />
                      </div>
                      <p className="mt-2 text-[11px] text-muted-foreground">
                        Query: {clinpgxPublic.data.query?.clinpgx_id || clinpgxPublic.data.query?.symbol || "-"}
                      </p>
                    </div>
                  ) : null}
                </KnowledgeBlock>
              </div>
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

            <ExternalLinksCard links={externalLinks(variant, csq, data)} />

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
                  { key: "sample", header: "Sample", render: (row: any) => row.sample_name || row.sample || row.SAMPLE || row.name || "-" },
                  { key: "assay", header: "Assay", render: (row: any) => row.assay || row.assay_group || "-" },
                  { key: "tier", header: "Tier", render: (row: any) => row.classification?.class || row.class || row.tier || "-" },
                ]}
              />
            </DetailCard>
          </>
        }
      />
    </FindingDetailShell>
  )
}
