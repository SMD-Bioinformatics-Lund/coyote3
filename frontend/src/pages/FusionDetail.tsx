import { useEffect } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { VariantActionButtons } from "@/components/detail/VariantActionButtons"
import { ClassificationsCard } from "@/components/detail/FindingDetailCards"
import { CommentsPanel } from "@/components/comments/CommentsPanel"
import { notifyActionError, notifySuccess } from "@/lib/notifications"
import { CallerBadges } from "@/lib/variant-ui"
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
  DetailFieldGrid,
  FindingDetailShell,
  FindingError,
  FindingHero,
  FindingLoading,
  FindingMainGrid,
} from "@/components/detail/FindingDetailLayout"
import { sampleDetailPath, sampleFindingPath, sampleUrlKey } from "@/lib/sample-routing"

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

function fusionDescription(value: unknown) {
  if (!value) return "-"
  return String(value).replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim()
}

export function FusionDetail() {
  const { id, varId } = useParams()
  const navigate = useNavigate()
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
      notifySuccess("Fusion call selected", "The selected fusion call was updated.", "fusion")
      refetch()
    },
    onError: (err) => notifyActionError("Unable to select fusion call", err, "fusion"),
  })
  const routeSample = data?.sample
  useEffect(() => {
    if (routeSample?.name && id && varId && id !== routeSample.name) {
      navigate(sampleFindingPath(routeSample, id, "fusion", varId), { replace: true })
    }
  }, [id, navigate, routeSample, routeSample?.name, varId])

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
  const sampleHref = sampleDetailPath(sample, id)

  return (
    <FindingDetailShell>
      <FindingHero
        backTo={sampleHref}
        title={fusionName(fusion)}
        chips={
          <>
            <span className="soft-chip">Fusion</span>
            <CallerBadges value={fusionCallers(fusion)} />
            <Link to={sampleHref} className="soft-chip hover:bg-primary/15 hover:text-primary">
              Sample {sample?.name || id}
            </Link>
          </>
        }
        actions={
          <VariantActionButtons
            sampleId={sampleRouteKey}
            resourceType="fusion"
            variant={fusion}
            onUpdate={() => refetch()}
          />
        }
      />

      <FindingMainGrid
        main={
          <>
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
            />

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

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <DetailCard title="Selected Fusion Call">
                <DetailFieldGrid>
                  <DetailField label="Gene 1">{genes[0] || fusion?.gene1 || "-"}</DetailField>
                  <DetailField label="Gene 2">{genes[1] || fusion?.gene2 || "-"}</DetailField>
                  <DetailField label="Breakpoints" valueClassName="font-mono">{fusionBreakpoint(selectedCall)}</DetailField>
                  <DetailField label="Effect" valueClassName="uppercase">{selectedCall?.effect || fusion?.frame || "-"}</DetailField>
                  <DetailField label="Caller">{selectedCall?.caller || fusionCallers(fusion)}</DetailField>
                  <DetailField label="Status">
                    <div className="flex flex-wrap gap-1">
                      {fusion?.fp && <EvidenceBadge tone="danger">False positive</EvidenceBadge>}
                      {selectedCall?.selected && <EvidenceBadge tone="success">Selected</EvidenceBadge>}
                    </div>
                  </DetailField>
                </DetailFieldGrid>
              </DetailCard>

              <DetailCard title="Read Support" tone="success">
                <DetailMetricTable
                  metrics={[
                    { label: "Spanning pairs", value: selectedCall?.spanpairs || fusion?.supporting_reads?.span, monospace: true },
                    { label: "Spanning reads", value: selectedCall?.spanreads || fusion?.supporting_reads?.split, monospace: true },
                    { label: "Longest anchor", value: selectedCall?.longestanchor, monospace: true },
                    { label: "Description", value: fusionDescription(selectedCall?.desc || fusion?.desc) },
                  ]}
                  dense
                />
              </DetailCard>
            </div>

            <DetailCard title="Fusion Calls From Callers">
              <DetailDataTable
                rows={calls}
                empty="No per-caller fusion calls available."
                columns={[
                  { key: "selected", header: "", render: (row: any, index) => row.selected ? <EvidenceBadge tone="success">Selected</EvidenceBadge> : <button className="rounded-md border border-border bg-background px-2 py-1 text-[10px] font-bold text-primary hover:bg-primary/10 disabled:opacity-50" disabled={pickCall.isPending} onClick={() => pickCall.mutate(index)}>Pick</button> },
                  { key: "gene1", header: "Gene 1", render: () => genes[0] || fusion?.gene1 || "-" },
                  { key: "gene2", header: "Gene 2", render: () => genes[1] || fusion?.gene2 || "-" },
                  { key: "breakpoints", header: "Breakpoints", render: (row: any) => <span className="font-mono">{fusionBreakpoint(row)}</span> },
                  { key: "effect", header: "Effect", render: (row: any) => row.effect || "-" },
                  { key: "spanpairs", header: "Span pairs", render: (row: any) => displayValue(row.spanpairs) },
                  { key: "spanreads", header: "Span reads", render: (row: any) => displayValue(row.spanreads) },
                  { key: "anchor", header: "Anchor", render: (row: any) => displayValue(row.longestanchor) },
                  { key: "caller", header: "Caller", render: (row: any) => row.caller || "-" },
                  { key: "desc", header: "Description", render: (row: any) => <span className="block max-w-md whitespace-normal">{fusionDescription(row.desc)}</span> },
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
                genes[0] ? { label: `cBioPortal ${genes[0]}`, value: genes[0], href: `https://www.cbioportal.org/results/oncoprint?gene_list=${encodeURIComponent(genes[0])}` } : null,
                genes[1] ? { label: `cBioPortal ${genes[1]}`, value: genes[1], href: `https://www.cbioportal.org/results/oncoprint?gene_list=${encodeURIComponent(genes[1])}` } : null,
                genes.length >= 2 ? { label: "PubMed fusion", value: genes.join("::"), href: `https://pubmed.ncbi.nlm.nih.gov/?term=${encodeURIComponent(`${genes[0]}::${genes[1]}`)}` } : null,
                genes.length >= 2 ? { label: "Atlas of Genetics and Cytogenetics", value: genes.join(" "), href: `https://pubmed.ncbi.nlm.nih.gov/?term=${encodeURIComponent(`${genes[0]} ${genes[1]} atlasgeneticsoncology.org`)}` } : null,
                { label: "Mitelman Database", value: "Mitelman", href: "https://mitelmandatabase.isb-cgc.org/mb_search" },
              ].filter(Boolean) as any[]}
            />
          </>
        }
      />
    </FindingDetailShell>
  )
}
