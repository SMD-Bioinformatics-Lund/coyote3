import { useEffect } from "react"
import { useLocation, useNavigate, useParams } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { VariantActionButtons } from "@/components/detail/VariantActionButtons"
import { ClassificationsCard } from "@/components/detail/FindingDetailCards"
import { CommentsPanel } from "@/components/comments/CommentsPanel"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { StatusBadges } from "@/lib/variant-ui"
import { FusionCallerBadges, FusionEffectBadge, FusionEvidenceBadges } from "@/lib/fusion-ui"
import { fusionCallers, fusionGenes, selectedFusionCall } from "@/lib/variant-helpers"
import {
  DetailDataTable,
  DetailMetricTable,
  EvidenceBadge,
  ExternalLinksCard,
} from "@/components/detail/DetailEvidenceCards"
import { displayValue } from "@/lib/detail-formatters"
import {
  DetailCard,
  DetailField,
  FindingDetailShell,
  FindingError,
  DetailHero,
  DetailHeroSubtitle,
  FindingIdentityCard,
  FindingLoading,
  FindingMainGrid,
} from "@/components/detail/FindingDetailLayout"
import { sampleDetailTabPath, sampleFindingPath, sampleUrlKey } from "@/lib/sample-routing"
import { cbioportalOncoprintUrl, EXTERNAL_LINK_BASES, pubmedSearchUrl } from "@/lib/external-links"

function fusionName(fusion: any) {
  const genes = fusionGenes(fusion)
  if (genes.length >= 2) return `${genes[0]}--${genes[1]}`
  return fusion?.fusion_name || fusion?.name || "Unknown Fusion"
}

function fusionBreakpoint(call: any) {
  const left = call?.breakpoint1 || call?.breakpoints?.[0]
  const right = call?.breakpoint2 || call?.breakpoints?.[1]
  return [left, right].filter(Boolean).join(" | ") || "-"
}

export function FusionDetail() {
  const { id, varId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['fusion', id, varId],
    queryFn: () => api.get(`/samples/${id}/fusions/${varId}`).then(res => res.data)
  })
  const callsLength = Array.isArray(data?.fusion?.calls) ? data.fusion.calls.length : 0
  const pickCall = useMutation({
    mutationFn: (index: number) => api.patch(`/samples/${id}/fusions/${varId}/selection/${index + 1}/${callsLength}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fusion", id, varId] })
      queryClient.invalidateQueries({ queryKey: ["sample-comment-suggestion", id] })
      notifySuccess("Fusion call selected", "The selected fusion call was updated.", "fusion")
      refetch()
    },
    onError: (err) => notifyActionError("Unable to select fusion call", err, "fusion"),
  })
  const routeSample = data?.sample
  useEffect(() => {
    if (routeSample?.name && id && varId && id !== routeSample.name) {
      navigate(sampleFindingPath(routeSample, id, "fusion", varId), {
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
        title="Error loading fusion"
        message={error instanceof Error ? error.message : "Unknown error"}
        backTo={`/samples/${id}`}
      />
    )
  }

  const { fusion, sample, latest_classification } = data
  const genes = fusionGenes(fusion)
  const selectedCall = selectedFusionCall(fusion)
  const calls = Array.isArray(fusion?.calls) ? fusion.calls : []
  const sampleRouteKey = sampleUrlKey(sample, id)
  const sampleHref = sampleDetailTabPath(sample, id, "fusions")
  const previousSampleHref = typeof location.state === "object" && location.state && "from" in location.state
    ? String((location.state as { from?: string }).from || sampleHref)
    : sampleHref

  return (
    <FindingDetailShell>
      <DetailHero
        backTo={previousSampleHref}
        title={fusionName(fusion)}
        subtitle={
          <DetailHeroSubtitle sampleHref={sampleHref} sampleName={sample?.name || id}>
            <span>
              Fusion{selectedCall ? ` · ${fusionBreakpoint(selectedCall)}` : ""}
            </span>
          </DetailHeroSubtitle>
        }
        chips={
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Called by</span>
            <FusionCallerBadges callers={fusionCallers(fusion)} />
          </div>
        }
        actions={
          <VariantActionButtons
            sampleId={sampleRouteKey}
            resourceType="fusion"
            variant={fusion}
            onUpdate={() => refetch()}
          />
        }
        statLabel="Calls"
        statValue={calls.length.toLocaleString()}
      />

      <FindingMainGrid
        main={
          <>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <FindingIdentityCard title="Fusion Identity">
                <DetailField label="Gene 1">{genes[0] || fusion?.gene1 || "-"}</DetailField>
                <DetailField label="Gene 2">{genes[1] || fusion?.gene2 || "-"}</DetailField>
                <DetailField label="Breakpoints">{fusionBreakpoint(selectedCall)}</DetailField>
                <DetailField label="Effect"><FusionEffectBadge effect={selectedCall?.effect || fusion?.frame} /></DetailField>
                <DetailField label="Caller"><FusionCallerBadges callers={selectedCall?.caller || fusionCallers(fusion)} /></DetailField>
                <DetailField label="Evidence"><FusionEvidenceBadges description={selectedCall?.desc || fusion?.desc} metadata={data.fusion_annotation_metadata} /></DetailField>
                <DetailField label="Status">
                  <div className="flex flex-wrap gap-1">
                    <StatusBadges finding={fusion} />
                    {selectedCall?.selected && <EvidenceBadge tone="success">Selected</EvidenceBadge>}
                  </div>
                </DetailField>
              </FindingIdentityCard>

              <div className="h-full lg:col-span-2">
                <CommentsPanel
                  sampleId={sampleRouteKey}
                  title="Add Comment Or Annotation"
                  resourceType="fusion"
                  resource={fusion}
                  comments={[]}
                  showList={false}
                  assayGroup={data.assay_group}
                  subpanel={data.subpanel}
                  queryKeys={[["fusion", id, varId]]}
                  enableSuggestion={false}
                  livePreview={false}
                  fillHeight
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <CommentsPanel
                sampleId={sampleRouteKey}
                title="Sample-Specific Fusion Comments"
                resourceType="fusion"
                resource={fusion}
                comments={fusion?.comments || []}
                showComposer={false}
                queryKeys={[["fusion", id, varId]]}
              />
              <CommentsPanel
                sampleId={sampleRouteKey}
                title="Global Fusion Annotations"
                resourceType="fusion"
                resource={fusion}
                comments={data.annotations || data.annotations_interesting || []}
                showComposer={false}
                allowHide={false}
                queryKeys={[["fusion", id, varId]]}
              />
            </div>

            <DetailCard title="Read Support" tone="success">
              <DetailMetricTable
                metrics={[
                  { label: "Spanning pairs", value: selectedCall?.spanpairs || fusion?.supporting_reads?.span, monospace: true },
                  { label: "Spanning reads", value: selectedCall?.spanreads || fusion?.supporting_reads?.split, monospace: true },
                  { label: "Longest anchor", value: selectedCall?.longestanchor, monospace: true },
                ]}
                dense
              />
            </DetailCard>

            <DetailCard title="Fusion Calls From Callers">
              <DetailDataTable
                rows={calls}
                empty="No per-caller fusion calls available."
                columns={[
                  { key: "selected", header: "", render: (row: any, index) => row.selected ? <EvidenceBadge tone="success">Selected</EvidenceBadge> : <button className="rounded-md border border-border bg-background px-2 py-1 text-[10px] font-bold text-primary hover:bg-primary/10 disabled:opacity-50" disabled={pickCall.isPending} onClick={() => pickCall.mutate(index)}>Pick</button> },
                  { key: "gene1", header: "Gene 1", render: () => genes[0] || fusion?.gene1 || "-" },
                  { key: "gene2", header: "Gene 2", render: () => genes[1] || fusion?.gene2 || "-" },
                  { key: "breakpoints", header: "Breakpoints", render: (row: any) => <span className="">{fusionBreakpoint(row)}</span> },
                  { key: "effect", header: "Effect", render: (row: any) => <FusionEffectBadge effect={row.effect} /> },
                  { key: "spanpairs", header: "Span pairs", render: (row: any) => displayValue(row.spanpairs) },
                  { key: "spanreads", header: "Span reads", render: (row: any) => displayValue(row.spanreads) },
                  { key: "anchor", header: "Anchor", render: (row: any) => displayValue(row.longestanchor) },
                  { key: "caller", header: "Caller", render: (row: any) => <FusionCallerBadges callers={row.caller} /> },
                  { key: "desc", header: "Description", render: (row: any) => <FusionEvidenceBadges description={row.desc} metadata={data.fusion_annotation_metadata} /> },
                ]}
              />
            </DetailCard>
          </>
        }
        aside={
          <>
            <ClassificationsCard
              latest={latest_classification}
              other={data.other_classifications || []}
              sampleId={id}
              resourceType="fusion"
              resourceId={String(fusion?._id || "")}
              onUpdate={() => refetch()}
            />

            <ExternalLinksCard
              links={[
                genes[0] ? { label: `cBioPortal ${genes[0]}`, value: genes[0], href: cbioportalOncoprintUrl(genes[0]) } : null,
                genes[1] ? { label: `cBioPortal ${genes[1]}`, value: genes[1], href: cbioportalOncoprintUrl(genes[1]) } : null,
                genes.length >= 2 ? { label: "PubMed fusion", value: genes.join("::"), href: pubmedSearchUrl(`${genes[0]}::${genes[1]}`) } : null,
                genes.length >= 2 ? { label: "Atlas of Genetics and Cytogenetics", value: genes.join(" "), href: pubmedSearchUrl(`${genes[0]} ${genes[1]} atlasgeneticsoncology.org`) } : null,
                { label: "Mitelman Database", value: "Mitelman", href: EXTERNAL_LINK_BASES.mitelmanSearch },
              ].filter(Boolean) as any[]}
            />
          </>
        }
      />
    </FindingDetailShell>
  )
}
