import { FindingCommentComposer, FindingCommentLists } from "@/components/comments/FindingComments"
import {
  DetailDataTable,
  DetailMetricTable,
  EvidenceBadge,
  ExternalLinksCard,
} from "@/components/detail/DetailEvidenceCards"
import { ExpandableText } from "@/components/detail/ExpandableText"
import { ClassificationsCard } from "@/components/detail/FindingDetailCards"
import {
  DetailCard,
  DetailField,
  FindingCallerMeta,
  FindingDetailHero,
  FindingDetailShell,
  FindingError,
  FindingIdentityCard,
  FindingLoading,
  FindingMainGrid,
} from "@/components/detail/FindingDetailLayout"
import { HotspotIndicator } from "@/components/detail/HotspotIndicator"
import { TranscriptConsequencesTable } from "@/components/detail/TranscriptConsequencesTable"
import { VariantActionButtons } from "@/components/detail/VariantActionButtons"
import {
  externalVariantLinks,
  VariantIdentifierLinks
} from "@/components/detail/VariantKnowledgebase"
import { GeneWithOncoKbBadge } from "@/components/knowledgebase/OncoKbGeneBadge"
import { VepVersionBadge } from "@/components/ui/vep-version-badge"
import { api } from "@/lib/api"
import { displayValue, percentValue } from "@/lib/detail-formatters"
import { notifyActionError } from "@/lib/notifications"
import { sampleDetailPath, sampleDetailTabPath, sampleFindingPath, sampleUrlKey } from "@/lib/sample-routing"
import { CallerBadges, ConsequenceBadges, FilterFlagBadges, ImpactBadge, PredictionBadge, TierBadge } from "@/lib/variant-ui"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { Link, useLocation, useNavigate, useParams } from "react-router-dom"
import { clinicalSig, ponRows, variantLocation } from "./variant-detail-presentation"
import { VariantEvidencePanel } from "./VariantEvidencePanel"

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
                <DetailField label="Filter flags"><FilterFlagBadges value={variant?.FILTER} metadata={filterFlagMetadata} analysis="snv" callers={callers} /></DetailField>
                <DetailField label="cDNA"><ExpandableText text={csq.HGVSc || "-"} maxLength={24} className="" /></DetailField>
                <DetailField label="Protein"><ExpandableText text={csq.HGVSp || "-"} maxLength={24} className="" /></DetailField>
                <DetailField label="Exon / Intron">{csq.EXON || csq.INTRON || "-"}</DetailField>
                <DetailField label="Indel size">{variant?.INFO?.SVLEN || variant?.indel_size || "-"}</DetailField>
              </FindingIdentityCard>

              <FindingCommentComposer
                sampleId={sampleRouteKey}
                resourceType="small_variant"
                resource={variant}
                assayGroup={data.assay_group}
                subpanel={data.subpanel}
                queryKeys={[["variant", id, varId]]}
                draftText={commentDraft}
                onDraftChange={setCommentDraft}
              />
            </div>

            <FindingCommentLists
              sampleId={sampleRouteKey}
              resourceType="small_variant"
              resource={variant}
              queryKeys={[["variant", id, varId]]}
              findingLabel="Variant"
              sampleComments={variant?.comments || []}
              globalComments={data.annotations || variant?.global_annotations || []}
              onUseAsDraft={setCommentDraft}
            />

            <DetailCard title="Panel Of Normals Evidence" tone="info">
              <DetailDataTable
                rows={ponRows(data.pon) || []}
                empty="No panel-of-normals evidence available."
                columns={[
                  { key: "caller", header: "Tool", render: (row: any) => row.caller || "-" },
                  { key: "detected", header: "Num (freq)", render: (row) => row.detected },
                  { key: "frequencies", header: "Latest 20 frequencies", render: (row) => row.frequencies },
                ]}
              />
            </DetailCard>

            <VariantEvidencePanel data={data} geneSymbol={csq.SYMBOL} id={id} varId={varId} />

            <DetailCard title="Transcript Consequences">
              <div className="mb-2"><VepVersionBadge version={sample?.database_versions?.vep} /></div>
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

            <DetailCard title="Sample Genotype" tone="success">
              <div className="space-y-2">
                {variant?.GT?.map((gt: any, i: number) => (
                  <div
                    key={i}
                    className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-3 rounded-lg border border-border/70 bg-background/55 px-3 py-2"
                  >
                    <div className="min-w-0">
                      <span className="detail-field-label">Genotype</span>
                      <EvidenceBadge tone="info">{gt.type || "Unknown"}</EvidenceBadge>
                    </div>
                    <div className="text-right">
                      <span className="detail-field-label">VAF</span>
                      <span className="type-allele-frequency block">{percentValue(gt.AF, 1)}</span>
                    </div>
                    <div className="text-right">
                      <span className="detail-field-label">Alt / depth</span>
                      <span className="type-body-sm font-semibold text-foreground">{displayValue(gt.VD)} / {displayValue(gt.DP)}</span>
                    </div>
                  </div>
                ))}
                {!variant?.GT?.length ? <p className="type-body-sm text-muted-foreground">No genotype data available.</p> : null}
              </div>
            </DetailCard>

            <DetailCard title="Prediction and Clinical Signals">
              <div className="space-y-2.5">
                <div className="grid grid-cols-2 gap-2">
                  <div className="min-w-0 rounded-lg border border-border/70 bg-background/55 p-2.5">
                    <span className="detail-field-label">CADD</span>
                    <span className="type-body font-semibold text-foreground">{displayValue(csq.CADD_PHRED)}</span>
                  </div>
                  <div className="min-w-0 rounded-lg border border-border/70 bg-background/55 p-2.5">
                    <span className="detail-field-label">ClinVar</span>
                    <ExpandableText
                      text={displayValue(clinicalSig(csq, variant))}
                      maxLength={18}
                      className="type-body-sm font-semibold text-foreground"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="min-w-0 overflow-hidden rounded-lg border border-border bg-background/50 p-2.5">
                    <span className="detail-field-label">SIFT</span>
                    <PredictionBadge value={csq.SIFT} />
                  </div>
                  <div className="min-w-0 overflow-hidden rounded-lg border border-border bg-background/50 p-2.5">
                    <span className="detail-field-label">PolyPhen</span>
                    <PredictionBadge value={csq.PolyPhen} />
                  </div>
                </div>
                <div className="min-w-0 rounded-lg border border-border/70 bg-background/55 p-2.5">
                  <span className="detail-field-label">Called by</span>
                  <div className="min-w-0 overflow-hidden"><CallerBadges value={callers} /></div>
                </div>
                <div className="min-w-0 rounded-lg border border-border/70 bg-background/55 p-2.5">
                  <span className="detail-field-label">Transcript selected by</span>
                  <ExpandableText
                    text={displayValue(variant?.INFO?.selected_CSQ_criteria)}
                    maxLength={32}
                    className="type-body-sm text-foreground"
                  />
                </div>
              </div>
            </DetailCard>

            <ExternalLinksCard
              title="External Evidence and Identifiers"
              links={externalVariantLinks(variant, csq, data)}
            >
              <VariantIdentifierLinks variant={variant} />
            </ExternalLinksCard>

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
