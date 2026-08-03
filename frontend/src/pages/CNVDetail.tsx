import { useEffect } from "react"
import { Link, useLocation, useNavigate, useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { VariantActionButtons } from "@/components/detail/VariantActionButtons"
import { ClassificationsCard } from "@/components/detail/FindingDetailCards"
import { CommentsPanel } from "@/components/comments/CommentsPanel"
import {
  DetailDataTable,
  DetailMetricTable,
  ExternalLinksCard,
} from "@/components/detail/DetailEvidenceCards"
import { percentValue } from "@/lib/detail-formatters"
import { ArtefactFrequencyBadges, CallerBadges, StatusBadges } from "@/lib/variant-ui"
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
import { sampleDetailTabPath, sampleFindingPath, sampleUrlKey } from "@/lib/sample-routing"
import { cbioportalOncoprintUrl, igvLoadUrl } from "@/lib/external-links"

function cnvRegion(cnv: any) {
  if (!cnv) return "-"
  return `${cnv.chr || cnv.CHROM}:${cnv.start || cnv.POS}-${cnv.end || cnv.INFO?.END}`
}

function cnvSize(cnv: any) {
  const size = Number(cnv?.size ?? ((cnv?.end || cnv?.INFO?.END) - (cnv?.start || cnv?.POS)))
  return Number.isFinite(size) ? `${Math.abs(size).toLocaleString()} bp` : "-"
}

function copyNumber(cnv: any) {
  const ratio = Number(cnv?.ratio ?? cnv?.log2)
  return Number.isFinite(ratio) ? (2 * Math.pow(2, ratio)).toFixed(2) : "-"
}

function cnvGenes(cnv: any, panelOnly: boolean) {
  const genes = Array.isArray(cnv?.genes) ? cnv.genes : []
  return genes.filter((gene: any) => panelOnly ? Boolean(gene?.class) : !gene?.class)
}

function structuralEvidenceMetrics(cnv: any) {
  return [
    { label: "PR", value: cnv?.PR || cnv?.pr || cnv?.INFO?.PR, monospace: true },
    { label: "SR", value: cnv?.SR || cnv?.sr || cnv?.INFO?.SR, monospace: true },
    { label: "Left region", value: cnv?.left_region || cnv?.INFO?.LEFT_REGION, monospace: true },
    { label: "Right region", value: cnv?.right_region || cnv?.INFO?.RIGHT_REGION, monospace: true },
    { label: "Callers", value: cnv?.callers || cnv?.INFO?.variant_callers },
  ]
}

export function CNVDetail() {
  const { id, varId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['cnv', id, varId],
    queryFn: () => api.get(`/samples/${id}/cnvs/${varId}`).then(res => res.data)
  })
  const routeSample = data?.sample
  useEffect(() => {
    if (routeSample?.name && id && varId && id !== routeSample.name) {
      navigate(sampleFindingPath(routeSample, id, "cnv", varId), {
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
        title="Error loading CNV"
        message={error instanceof Error ? error.message : "Unknown error"}
        backTo={`/samples/${id}`}
      />
    )
  }

  const { cnv, sample, latest_classification } = data
  const primaryGenes = cnv?.genes?.filter((g: any) => g.class).map((g: any) => g.gene) || []
  const region = cnvRegion(cnv)
  const type = String(cnv?.type || cnv?.cnv_type || "").toLowerCase()
  const callers = cnv?.callers || cnv?.INFO?.variant_callers
  const sampleRouteKey = sampleUrlKey(sample, id)
  const sampleHref = sampleDetailTabPath(sample, id, "cnvs")
  const previousSampleHref = typeof location.state === "object" && location.state && "from" in location.state
    ? String((location.state as { from?: string }).from || sampleHref)
    : sampleHref

  return (
    <FindingDetailShell>
      <FindingHero
        backTo={previousSampleHref}
        title={primaryGenes.length > 0 ? primaryGenes.join(', ') : "Intergenic CNV"}
        subtitle={
          <div className="space-y-2">
            <span className="block text-xl font-bold text-muted-foreground">
              {type ? type.toUpperCase() : "CNV"} · {region}
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
            resourceType="cnv"
            variant={cnv}
            onUpdate={() => refetch()}
          />
        }
        statLabel="Copy Number"
        statValue={copyNumber(cnv)}
      />

      <FindingMainGrid
        main={
          <>
            <CommentsPanel
              sampleId={sampleRouteKey}
              title="Add Comment Or Annotation"
              resourceType="cnv"
              resource={cnv}
              comments={[]}
              showList={false}
              assayGroup={data.assay_group}
              subpanel={data.subpanel}
              queryKeys={[["cnv", id, varId]]}
              enableSuggestion={false}
              livePreview={false}
            />

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <CommentsPanel
                sampleId={sampleRouteKey}
                title="Sample-Specific CNV Comments"
                resourceType="cnv"
                resource={cnv}
                comments={cnv?.comments || []}
                showComposer={false}
                queryKeys={[["cnv", id, varId]]}
              />
              <CommentsPanel
                sampleId={sampleRouteKey}
                title="Global CNV Annotations"
                resourceType="cnv"
                resource={cnv}
                comments={data.annotations || []}
                showComposer={false}
                allowHide={false}
                queryKeys={[["cnv", id, varId]]}
              />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <DetailCard title="CNV Properties">
                <DetailFieldGrid>
                  <DetailField label="Region" valueClassName="font-mono">{region}</DetailField>
                  <DetailField label="Size" valueClassName="font-mono text-primary/80">{cnvSize(cnv)}</DetailField>
                  <DetailField label="Type" valueClassName="uppercase">{type || "-"}</DetailField>
                  <DetailField label="Ratio (log2)" valueClassName="font-mono">{Number.isFinite(Number(cnv?.ratio)) ? Number(cnv?.ratio).toFixed(4) : "-"}</DetailField>
                  <DetailField label="Copy Number" valueClassName="font-mono text-tier4">{copyNumber(cnv)}</DetailField>
                  <DetailField label="Status">
                    <StatusBadges finding={cnv} />
                  </DetailField>
                  <DetailField label="Artefact evidence">
                    <ArtefactFrequencyBadges finding={cnv} />
                  </DetailField>
                </DetailFieldGrid>
              </DetailCard>

              <DetailCard title="Structural Evidence" tone="success">
                <DetailMetricTable metrics={structuralEvidenceMetrics(cnv)} dense />
              </DetailCard>
            </div>

            <DetailCard title="Panel Genes">
              <DetailDataTable
                rows={cnvGenes(cnv, true)}
                empty="No panel genes overlap this CNV."
                columns={[
                  { key: "gene", header: "Gene", render: (row: any) => row.gene || row.name || "-" },
                  { key: "class", header: "Class", render: (row: any) => row.class || "-" },
                  { key: "effect", header: "Effect", render: (row: any) => row.effect || type || "-" },
                ]}
              />
            </DetailCard>

            <DetailCard title="Other Overlapping Genes" tone="info">
              <DetailDataTable
                rows={cnvGenes(cnv, false)}
                empty="No other overlapping genes available."
                columns={[
                  { key: "gene", header: "Gene", render: (row: any) => row.gene || row.name || "-" },
                  { key: "effect", header: "Effect", render: (row: any) => row.effect || type || "-" },
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
            />

            <ExternalLinksCard
              links={[
                data.bam_id && region !== "-" && igvLoadUrl(data.bam_id, region)
                  ? { label: "Open CNV in IGV", value: region, href: igvLoadUrl(data.bam_id, region)! }
                  : null,
                primaryGenes[0]
                  ? { label: `cBioPortal ${primaryGenes[0]}`, value: primaryGenes[0], href: cbioportalOncoprintUrl(primaryGenes[0]) }
                  : null,
              ].filter(Boolean) as any[]}
            />

            <DetailCard title="Artefact Signatures" tone="info">
              <div className="space-y-2">
                {Object.keys(cnv || {}).filter(k => k.startsWith('AFRQ_')).map(k => (
                  <div key={k} className="flex justify-between items-center text-sm">
                    <span className="text-muted-foreground uppercase">{k.split('_')[1]}</span>
                    <span className="font-mono font-bold">{percentValue(cnv[k], 1)}</span>
                  </div>
                ))}
                {!Object.keys(cnv || {}).some(k => k.startsWith('AFRQ_')) && (
                  <p className="text-sm text-muted-foreground">No artefact signature fields available.</p>
                )}
              </div>
            </DetailCard>
          </>
        }
      />
    </FindingDetailShell>
  )
}
